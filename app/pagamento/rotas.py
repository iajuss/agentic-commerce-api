"""Aprovação e pagamento: POST /solicitacoes/<id>/autorizacoes, /autorizacoes e /pedidos.

Atenção, front: em POST /solicitacoes/<id>/autorizacoes, o 401 de senha errada traz `detalhes.senha` e não significa
sessão expirada; um 401 sem `detalhes` é sessão inválida (seção 10 do contrato).
"""

from flask import Blueprint, jsonify, url_for
from flask_jwt_extended import jwt_required
from werkzeug.security import check_password_hash

from app.autenticacao.identidade import usuario_atual_id
from app.banco import documento_para_json, para_object_id
from app.erros import ErroApi, ler_json
from app.pagamento import regras, repositorio_autorizacoes, repositorio_contrato, repositorio_pedidos, servicos
from app.pagamento.auditoria import auditar
from app.pagamento.servicos import executar_compra_automatica
from app.pagamento.validacao import validar_aprovacao, validar_pagamento_simulado, validar_pedido
from app.pos_compra.servicos import aplicar_transicoes

bp = Blueprint("pagamento", __name__)
# Gancho da compra automática para o M2 (seção 6.2 do contrato).
bp.record_once(lambda estado: estado.app.extensions.setdefault("compra_automatica", executar_compra_automatica))

SOLICITACAO_NAO_ENCONTRADA = "Solicitação não encontrada."
AUTORIZACAO_NAO_ENCONTRADA = "Autorização não encontrada."
SENHA_INCORRETA = "Senha incorreta."
SESSAO_INVALIDA = "Sessão inválida. Faça login novamente."


@bp.post("/solicitacoes/<solicitacao_id>/autorizacoes")
@jwt_required()
def criar_autorizacao(solicitacao_id):
    senha = validar_aprovacao(ler_json())
    usuario_id = usuario_atual_id()

    solicitacao = repositorio_contrato.obter_solicitacao(usuario_id, para_object_id(solicitacao_id))
    if solicitacao is None:
        raise ErroApi(404, SOLICITACAO_NAO_ENCONTRADA)
    if solicitacao["status"] != servicos.AGUARDANDO_APROVACAO:
        raise ErroApi(409, "Esta solicitação não está aguardando aprovação.")

    senha_hash = repositorio_contrato.senha_hash(usuario_id)
    if not senha_hash:
        raise ErroApi(401, SESSAO_INVALIDA)  # sem detalhes: o front encerra a sessão
    if not check_password_hash(senha_hash, senha):
        auditar(usuario_id, "reautenticacao_recusada", "solicitacao", solicitacao["_id"])
        # Com detalhes.senha o front mantém a sessão e pede a senha de novo.
        raise ErroApi(401, SENHA_INCORRETA, {"senha": "Senha incorreta. Confira e tente de novo."})

    avaliacao = solicitacao["avaliacao"]
    if not avaliacao["permitida"]:
        raise ErroApi(422, "Nenhuma política permite esta compra.", {"motivos": list(avaliacao["motivos"])})

    autorizacao = servicos.emitir_autorizacao(usuario_id, solicitacao, "manual")
    local = url_for(".obter_autorizacao", autorizacao_id=str(autorizacao["_id"]))
    return jsonify(documento_para_json(autorizacao)), 201, {"Location": local}


@bp.get("/autorizacoes")
@jwt_required()
def listar_autorizacoes():
    autorizacoes = repositorio_autorizacoes.listar_ativas(usuario_atual_id(), regras.agora())
    return jsonify([documento_para_json(autorizacao) for autorizacao in autorizacoes])


@bp.get("/autorizacoes/<autorizacao_id>")
@jwt_required()
def obter_autorizacao(autorizacao_id):
    autorizacao = repositorio_autorizacoes.obter(usuario_atual_id(), para_object_id(autorizacao_id))
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
