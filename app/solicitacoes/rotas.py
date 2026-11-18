"""Orquestrador: POST, GET, PATCH e DELETE /solicitacoes, com busca no catálogo e ranking explicável.

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
from app.solicitacoes.orquestrador import (
    processar_solicitacao,
    regularizar_aprovacoes,
    tentar_compra_automatica,
    trocar_oferta,
)
from app.solicitacoes.repositorio import AGUARDANDO_APROVACAO
from app.solicitacoes.validacao import validar_solicitacao, validar_troca

bp = Blueprint("solicitacoes", __name__)
# Confere CATALOGO_PROVEDOR ao registrar o blueprint: um provedor sem conector impede a API de subir, em vez de
# quebrar cada POST /solicitacoes.
bp.record_once(lambda estado: fabrica_do_provedor(estado.app.config))

NAO_ENCONTRADA = "Solicitação não encontrada."
NAO_CANCELAVEL = "Esta solicitação já foi aprovada e não pode ser cancelada."
ITEM_NAO_ENCONTRADO = "Item não encontrado."
NAO_TROCAVEL = "Só dá para trocar a oferta antes de aprovar a compra."


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
    usuario_id = usuario_atual_id()
    regularizar_aprovacoes(usuario_id)
    return jsonify([_resumo(solicitacao) for solicitacao in repositorio.listar(usuario_id)])


@bp.get("/solicitacoes/<solicitacao_id>")
def obter_solicitacao(solicitacao_id):
    usuario_id = usuario_atual_id()
    solicitacao_id = para_object_id(solicitacao_id)

    regularizar_aprovacoes(usuario_id, solicitacao_id)
    solicitacao = repositorio.obter(usuario_id, solicitacao_id)
    if solicitacao is None:
        raise ErroApi(404, NAO_ENCONTRADA)
    return jsonify(documento_para_json(solicitacao))


@bp.delete("/solicitacoes/<solicitacao_id>")
def cancelar_solicitacao(solicitacao_id):
    usuario_id = usuario_atual_id()
    solicitacao_id = para_object_id(solicitacao_id)

    regularizar_aprovacoes(usuario_id, solicitacao_id)  # a autorização vencida libera o cancelamento
    resultado = repositorio.remover_se_cancelavel(usuario_id, solicitacao_id)
    if resultado == "inexistente":
        raise ErroApi(404, NAO_ENCONTRADA)
    if resultado == "nao_cancelavel":
        raise ErroApi(409, NAO_CANCELAVEL)

    auditar(usuario_id, "solicitacao_cancelada", "solicitacao", solicitacao_id)
    return "", 204


@bp.patch("/solicitacoes/<solicitacao_id>/itens/<indice>")
def trocar_oferta_do_item(solicitacao_id, indice):
    """Troca a oferta de um item por uma das alternativas: {"id_externo": "..."}."""
    usuario_id = usuario_atual_id()
    solicitacao_id = para_object_id(solicitacao_id)
    id_externo = validar_troca(ler_json())

    regularizar_aprovacoes(usuario_id, solicitacao_id)
    solicitacao = repositorio.obter(usuario_id, solicitacao_id)
    if solicitacao is None:
        raise ErroApi(404, NAO_ENCONTRADA)
    # O índice vem da URL como texto; "-1" ou "abc" não são um item.
    if not indice.isdigit() or int(indice) >= len(solicitacao["itens"]):
        raise ErroApi(404, ITEM_NAO_ENCONTRADO)
    if solicitacao["status"] != AGUARDANDO_APROVACAO:
        raise ErroApi(409, NAO_TROCAVEL)

    indice = int(indice)
    troca = trocar_oferta(
        solicitacao,
        indice,
        id_externo,
        repositorio_politicas.listar(usuario_id),
        repositorio.perfil_do_usuario(usuario_id),
    )
    if troca is not None:
        itens, cesta, avaliacao = troca
        if not repositorio.trocar_cesta(usuario_id, solicitacao_id, itens, cesta, avaliacao):
            raise ErroApi(409, NAO_TROCAVEL)  # foi aprovada entre a leitura e a gravação
        anterior = solicitacao["itens"][indice]["recomendada"]["id_externo"]
        dados = {"item": indice, "de": anterior, "para": id_externo, "total": cesta["total"]}
        auditar(usuario_id, "oferta_trocada", "solicitacao", solicitacao_id, dados)
        solicitacao = repositorio.obter(usuario_id, solicitacao_id)

    return jsonify(documento_para_json(solicitacao))


def _resumo(solicitacao):
    return {
        "id": solicitacao["_id"],
        "texto": solicitacao["texto"],
        "itens": [item["descricao"] for item in solicitacao["itens"]],
        "status": solicitacao["status"],
        "total": solicitacao["cesta"]["total"],
        "criada_em": solicitacao["criada_em"],
    }
