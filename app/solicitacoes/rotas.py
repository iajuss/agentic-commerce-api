"""Orquestrador: POST, GET e DELETE /solicitacoes, com busca no catálogo e ranking explicável.

Responsável: Dev 2 (módulo M2 de docs/plano-backend).
"""

from flask import Blueprint, jsonify, url_for

from app.autenticacao.identidade import usuario_atual_id
from app.banco import documento_para_json, para_object_id
from app.erros import ErroApi, ler_json
from app.politicas import repositorio as repositorio_politicas
from app.solicitacoes import repositorio
from app.solicitacoes.auditoria import auditar
from app.solicitacoes.catalogo import fabrica_do_provedor, obter_catalogo
from app.solicitacoes.orquestrador import processar_solicitacao, tentar_compra_automatica
from app.solicitacoes.validacao import validar_solicitacao

bp = Blueprint("solicitacoes", __name__)
# Confere CATALOGO_PROVEDOR ao registrar o blueprint: um provedor sem conector impede a API de subir, em vez de
# quebrar cada POST /solicitacoes.
bp.record_once(lambda estado: fabrica_do_provedor(estado.app.config))

NAO_ENCONTRADA = "Solicitação não encontrada."
NAO_CANCELAVEL = "Esta solicitação já foi aprovada e não pode ser cancelada."


@bp.post("/solicitacoes")
def criar_solicitacao():
    usuario_id = usuario_atual_id()
    pedido = validar_solicitacao(ler_json())
    documento = processar_solicitacao(
        usuario_id,
        pedido,
        obter_catalogo(),
        repositorio_politicas.listar(usuario_id),
        repositorio.perfil_do_usuario(usuario_id),
    )
    solicitacao = repositorio.criar(documento)
    dados = {"itens": len(solicitacao["itens"]), "status": solicitacao["status"]}
    auditar(usuario_id, "solicitacao_criada", "solicitacao", solicitacao["_id"], dados)

    tentou, resultado = tentar_compra_automatica(solicitacao)
    if tentou:
        repositorio.registrar_compra_automatica(usuario_id, solicitacao["_id"], resultado)
    solicitacao = repositorio.obter(usuario_id, solicitacao["_id"])  # relê: o M3 pode ter mudado o status

    local = url_for(".obter_solicitacao", solicitacao_id=str(solicitacao["_id"]))
    return jsonify(documento_para_json(solicitacao)), 201, {"Location": local}


@bp.get("/solicitacoes")
def listar_solicitacoes():
    return jsonify([_resumo(solicitacao) for solicitacao in repositorio.listar(usuario_atual_id())])


@bp.get("/solicitacoes/<solicitacao_id>")
def obter_solicitacao(solicitacao_id):
    solicitacao = repositorio.obter(usuario_atual_id(), para_object_id(solicitacao_id))
    if solicitacao is None:
        raise ErroApi(404, NAO_ENCONTRADA)
    return jsonify(documento_para_json(solicitacao))


@bp.delete("/solicitacoes/<solicitacao_id>")
def cancelar_solicitacao(solicitacao_id):
    usuario_id = usuario_atual_id()
    solicitacao_id = para_object_id(solicitacao_id)

    resultado = repositorio.remover_se_cancelavel(usuario_id, solicitacao_id)
    if resultado == "inexistente":
        raise ErroApi(404, NAO_ENCONTRADA)
    if resultado == "nao_cancelavel":
        raise ErroApi(409, NAO_CANCELAVEL)

    auditar(usuario_id, "solicitacao_cancelada", "solicitacao", solicitacao_id)
    return "", 204


def _resumo(solicitacao):
    return {
        "id": solicitacao["_id"],
        "texto": solicitacao["texto"],
        "itens": [item["descricao"] for item in solicitacao["itens"]],
        "status": solicitacao["status"],
        "total": solicitacao["cesta"]["total"],
        "criada_em": solicitacao["criada_em"],
    }
