"""Cadastro, login e perfil: POST /usuarios, POST /sessoes, GET e PATCH /usuarios/me.

Responsável: Pessoa 2 (cadastro e login) e Pessoa 3 (perfil com ViaCEP).
"""

import re

from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auditoria.registro import registrar_evento
from app.autenticacao import repositorio
from app.erros import ErroApi, ler_json

bp = Blueprint("autenticacao", __name__)

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _usuario_publico(usuario):
    return {"id": str(usuario["_id"]), "nome": usuario["nome"], "email": usuario["email"]}


@bp.post("/usuarios")
def cadastrar_usuario():
    dados = ler_json()
    erros = {}

    nome = dados.get("nome")
    if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > 80:
        erros["nome"] = "Informe um nome de até 80 caracteres."

    email = dados.get("email")
    if not isinstance(email, str) or len(email.strip()) > 254 or not EMAIL.fullmatch(email.strip()):
        erros["email"] = "Informe um e-mail válido."

    senha = dados.get("senha")
    if not isinstance(senha, str) or not 8 <= len(senha) <= 128:
        erros["senha"] = "Use uma senha de 8 a 128 caracteres."

    if erros:
        raise ErroApi(400, "Dados de cadastro inválidos.", erros)

    try:
        usuario = repositorio.criar(nome.strip(), email.strip().lower(), generate_password_hash(senha))
    except DuplicateKeyError:
        raise ErroApi(409, "E-mail já cadastrado.", {"email": "Use outro e-mail."}) from None

    registrar_evento(usuario["_id"], "usuario_cadastrado", "usuario", usuario["_id"])
    return jsonify(_usuario_publico(usuario)), 201, {"Location": "/usuarios/me"}


@bp.post("/sessoes")
def criar_sessao():
    dados = ler_json()
    email = dados.get("email")
    senha = dados.get("senha")
    if not isinstance(email, str) or not isinstance(senha, str):
        raise ErroApi(401, "E-mail ou senha inválidos.")

    usuario = repositorio.buscar_por_email(email.strip().lower())
    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        if usuario is not None:
            registrar_evento(usuario["_id"], "login_recusado", "usuario", usuario["_id"])
        raise ErroApi(401, "E-mail ou senha inválidos.")

    token = create_access_token(identity=str(usuario["_id"]))
    registrar_evento(usuario["_id"], "sessao_iniciada", "usuario", usuario["_id"])
    return jsonify(token=token, usuario=_usuario_publico(usuario))
