"""Cadastro, login e perfil: POST /usuarios, POST /sessoes, GET e PATCH /usuarios/me.

Responsável: Pessoa 2 (cadastro e login) e Pessoa 3 (perfil com ViaCEP).
"""

from flask import Blueprint

bp = Blueprint("autenticacao", __name__)
