"""Aprovação e pagamento: POST /solicitacoes/<id>/autorizacoes, /autorizacoes e /pedidos.

Atenção, front: em POST /solicitacoes/<id>/autorizacoes, 401 significa senha errada, não sessão expirada.
"""

from flask import Blueprint, jsonify, url_for
from flask_jwt_extended import jwt_required
from werkzeug.security import check_password_hash

from app.autenticacao.identidade import usuario_atual_id
from app.banco import documento_para_json, para_object_id
from app.erros import ErroApi, ler_json
from app.pagamento import regras, repositorio_autorizacoes, repositorio_contrato, repositorio_pedidos, servicos
from app.pagamento.auditoria import auditar
from app.pagamento.servicos import executar_compra_automatica, expirar_autorizacoes_vencidas
from app.pagamento.validacao import validar_aprovacao, validar_pagamento_simulado, validar_pedido
from app.pos_compra.servicos import aplicar_transicoes

bp = Blueprint("pagamento", __name__)
# Gancho da compra automática para o M2 (seção 6.2 do contrato).
bp.record_once(lambda estado: estado.app.extensions.setdefault("compra_automatica", executar_compra_automatica))
# Gancho que expira autorizações vencidas sem pedido; o M2 chama antes de ler solicitações (seção 6.3).
bp.record_once(
    lambda estado: estado.app.extensions.setdefault("expirar_autorizacoes", expirar_autorizacoes_vencidas)
)

SOLICITACAO_NAO_ENCONTRADA = "Solicitação não encontrada."
AUTORIZACAO_NAO_ENCONTRADA = "Autorização não encontrada."


@bp.post("/solicitacoes/<solicitacao_id>/autorizacoes")
@jwt_required()
def criar_autorizacao(solicitacao_id):
    senha = validar_aprovacao(ler_json())
    usuario_id = usuario_atual_id()
    solicitacao_id = para_object_id(solicitacao_id)

    expirar_autorizacoes_vencidas(usuario_id, solicitacao_id)  # a vencida libera nova aprovação
    solicitacao = repositorio_contrato.obter_solicitacao(usuario_id, solicitacao_id)
    if solicitacao is None:
        raise ErroApi(404, SOLICITACAO_NAO_ENCONTRADA)
    if solicitacao["status"] != servicos.AGUARDANDO_APROVACAO:
        raise ErroApi(409, "Esta solicitação não está aguardando aprovação.")

    senha_hash = repositorio_contrato.senha_hash(usuario_id)
    if not senha_hash or not check_password_hash(senha_hash, senha):
        auditar(usuario_id, "reautenticacao_recusada", "solicitacao", solicitacao["_id"])
        raise ErroApi(401, "Senha incorreta.")

    avaliacao = solicitacao["avaliacao"]
    if not avaliacao["permitida"]:
        raise ErroApi(422, "Nenhuma política permite esta compra.", {"motivos": list(avaliacao["motivos"])})

    autorizacao = servicos.emitir_autorizacao(usuario_id, solicitacao, "manual")
    local = url_for(".obter_autorizacao", autorizacao_id=str(autorizacao["_id"]))
    return jsonify(documento_para_json(autorizacao)), 201, {"Location": local}


@bp.get("/autorizacoes")
@jwt_required()
def listar_autorizacoes():
    usuario_id = usuario_atual_id()
    expirar_autorizacoes_vencidas(usuario_id)
    autorizacoes = repositorio_autorizacoes.listar_ativas(usuario_id, regras.agora())
    return jsonify([documento_para_json(autorizacao) for autorizacao in autorizacoes])


@bp.get("/autorizacoes/<autorizacao_id>")
@jwt_required()
def obter_autorizacao(autorizacao_id):
    usuario_id = usuario_atual_id()
    autorizacao_id = para_object_id(autorizacao_id)
    expirar_autorizacoes_vencidas(usuario_id)  # mostra `expirada` em vez de uma `ativa` vencida
    autorizacao = repositorio_autorizacoes.obter(usuario_id, autorizacao_id)
    if autorizacao is None:
        raise ErroApi(404, AUTORIZACAO_NAO_ENCONTRADA)
    return jsonify(documento_para_json(autorizacao))


@bp.delete("/autorizacoes/<autorizacao_id>")
@jwt_required()
def revogar_autorizacao(autorizacao_id):
    servicos.revogar_autorizacao(usuario_atual_id(), para_object_id(autorizacao_id))
    return "", 204


@bp.post("/pedidos")
@jwt_required()
def criar_pedido():
    autorizacao_id = para_object_id(validar_pedido(ler_json()))
    usuario_id = usuario_atual_id()
    autorizacao = servicos.consumir_autorizacao(usuario_id, autorizacao_id)
    pedido = servicos.criar_pedido(usuario_id, autorizacao)
    local = url_for("pos_compra.obter_pedido", pedido_id=str(pedido["_id"]))
    return jsonify(regras.pedido_para_json(pedido)), 201, {"Location": local}


@bp.get("/pedidos")
@jwt_required()
def listar_pedidos():
    usuario_id = usuario_atual_id()
    pedidos = [aplicar_transicoes(usuario_id, pedido) for pedido in repositorio_pedidos.listar(usuario_id)]
    return jsonify([regras.resumo_do_pedido(pedido) for pedido in pedidos])


@bp.post("/simulador-pix/pagamentos")
@jwt_required()
def simular_pagamento_pix():
    txid = validar_pagamento_simulado(ler_json())
    pedido = servicos.confirmar_pagamento(usuario_atual_id(), txid)
    return jsonify(regras.pedido_para_json(pedido))
