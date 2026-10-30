"""Pós-compra: GET e PATCH /pedidos/<id> (comprovante, cancelamento e devolução) e /pedidos/<id>/chamados.

Os pedidos são lidos e gravados por `app.pagamento.repositorio_pedidos`, também do M3.
"""

from flask import Blueprint, jsonify, url_for
from flask_jwt_extended import jwt_required

from app.autenticacao.identidade import usuario_atual_id
from app.banco import para_object_id
from app.erros import ErroApi, ler_json
from app.pagamento import repositorio_pedidos
from app.pagamento.auditoria import auditar
from app.pagamento.regras import pedido_para_json
from app.pagamento.validacao import validar_mudanca_pedido
from app.pos_compra import regras, repositorio
from app.pos_compra.servicos import aplicar_transicoes, mudar_status_pelo_usuario
from app.pos_compra.validacao import validar_chamado

bp = Blueprint("pos_compra", __name__)

PEDIDO_NAO_ENCONTRADO = "Pedido não encontrado."


@bp.get("/pedidos/<pedido_id>")
@jwt_required()
def obter_pedido(pedido_id):
    """Comprovante com o status atual; as transições simuladas já devidas são gravadas aqui (seção 1)."""
    usuario_id = usuario_atual_id()
    pedido = repositorio_pedidos.obter(usuario_id, para_object_id(pedido_id))
    if pedido is None:
        raise ErroApi(404, PEDIDO_NAO_ENCONTRADO)
    return jsonify(pedido_para_json(aplicar_transicoes(usuario_id, pedido)))


@bp.patch("/pedidos/<pedido_id>")
@jwt_required()
def mudar_pedido(pedido_id):
    """Cancelamento ou pedido de devolução, conforme a tabela de estados do pedido."""
    novo, motivo = validar_mudanca_pedido(ler_json())
    usuario_id = usuario_atual_id()
    pedido = repositorio_pedidos.obter(usuario_id, para_object_id(pedido_id))
    if pedido is None:
        raise ErroApi(404, PEDIDO_NAO_ENCONTRADO)
    return jsonify(pedido_para_json(mudar_status_pelo_usuario(usuario_id, pedido, novo, motivo)))


@bp.post("/pedidos/<pedido_id>/chamados")
@jwt_required()
def abrir_chamado(pedido_id):
    assunto, mensagem = validar_chamado(ler_json())
    usuario_id = usuario_atual_id()
    pedido = _pedido_do_usuario(usuario_id, pedido_id)
    novo = regras.montar_chamado(usuario_id, pedido["_id"], assunto, mensagem, regras.agora())
    chamado = repositorio.criar(novo)
    auditar(usuario_id, "chamado_aberto", "chamado", chamado["_id"])
    local = url_for(".obter_chamado", pedido_id=str(pedido["_id"]), chamado_id=str(chamado["_id"]))
    return jsonify(regras.chamado_para_json(chamado)), 201, {"Location": local}


@bp.get("/pedidos/<pedido_id>/chamados")
@jwt_required()
def listar_chamados(pedido_id):
    usuario_id = usuario_atual_id()
    pedido = _pedido_do_usuario(usuario_id, pedido_id)
    chamados = repositorio.listar(usuario_id, pedido["_id"])
    return jsonify([regras.chamado_para_json(chamado) for chamado in chamados])


@bp.get("/pedidos/<pedido_id>/chamados/<chamado_id>")
@jwt_required()
def obter_chamado(pedido_id, chamado_id):
    usuario_id = usuario_atual_id()
    pedido = _pedido_do_usuario(usuario_id, pedido_id)
    chamado = repositorio.obter(usuario_id, pedido["_id"], para_object_id(chamado_id))
    if chamado is None:
        raise ErroApi(404, "Chamado não encontrado.")
    return jsonify(regras.chamado_para_json(chamado))


def _pedido_do_usuario(usuario_id, pedido_id):
    pedido = repositorio_pedidos.obter(usuario_id, para_object_id(pedido_id))
    if pedido is None:
        raise ErroApi(404, PEDIDO_NAO_ENCONTRADO)
    return pedido
