"""Aprovação e pagamento: POST /solicitacoes/{id}/autorizacoes, /autorizacoes e /pedidos.

Responsável: Pessoa 2 (autorizações) e Pessoa 5 (pedidos).
"""

from flask import Blueprint

bp = Blueprint("pagamento", __name__)
