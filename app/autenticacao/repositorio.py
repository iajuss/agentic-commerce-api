"""Acesso à coleção de usuários."""

from datetime import datetime, timezone

from app.banco import banco


def _colecao():
    return banco()["usuarios"]


def criar(nome, email, senha_hash):
    colecao = _colecao()
    usuario = {
        "nome": nome,
        "email": email,
        "senha_hash": senha_hash,
        "criado_em": datetime.now(timezone.utc),
    }
    colecao.insert_one(usuario)
    return usuario


def buscar_por_email(email):
    return _colecao().find_one({"email": email})
