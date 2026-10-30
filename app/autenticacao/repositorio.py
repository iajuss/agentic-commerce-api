"""Acesso à coleção de usuários."""

from datetime import datetime, timezone

from pymongo import ReturnDocument

from app.banco import banco


def _colecao():
    return banco()["usuarios"]


def agora():
    return datetime.now(timezone.utc)


def criar(nome, email, senha_hash):
    colecao = _colecao()
    usuario = {
        "nome": nome,
        "email": email,
        "senha_hash": senha_hash,
        "criado_em": agora(),
    }
    colecao.insert_one(usuario)
    return usuario


def buscar_por_email(email):
    return _colecao().find_one({"email": email})


def obter(usuario_id):
    return _colecao().find_one({"_id": usuario_id})


def atualizar(usuario_id, campos):
    """Altera somente os campos recebidos e devolve o perfil atualizado."""
    return _colecao().find_one_and_update(
        {"_id": usuario_id},
        {"$set": {**campos, "atualizado_em": agora()}},
        return_document=ReturnDocument.AFTER,
    )
