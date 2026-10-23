"""Pós-compra: PATCH /pedidos/{id} (cancelamento e devolução) e /pedidos/{id}/chamados.

Responsável: Pessoa 1.
"""

from flask import Blueprint

bp = Blueprint("pos_compra", __name__)
