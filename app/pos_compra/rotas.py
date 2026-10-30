"""Pós-compra: GET e PATCH /pedidos/<id> (comprovante, cancelamento e devolução) e /pedidos/<id>/chamados.

Os pedidos são lidos e gravados por `app.pagamento.repositorio_pedidos`, também do M3.
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.autenticacao.identidade import usuario_atual_id
from app.banco import para_object_id
from app.erros import ErroApi
from app.pagamento import repositorio_pedidos
from app.pagamento.regras import pedido_para_json

bp = Blueprint("pos_compra", __name__)

PEDIDO_NAO_ENCONTRADO = "Pedido não encontrado."


@bp.get("/pedidos/<pedido_id>")
@jwt_required()
def obter_pedido(pedido_id):
    pedido = repositorio_pedidos.obter(usuario_atual_id(), para_object_id(pedido_id))
    if pedido is None:
        raise ErroApi(404, PEDIDO_NAO_ENCONTRADO)
    return jsonify(pedido_para_json(pedido))
