"""Acesso à coleção `politicas`.

Toda consulta filtra pelo dono, então um usuário nunca lê nem altera a política de outro.
"""

from datetime import datetime, timezone

from pymongo import ReturnDocument

from app.banco import banco


def _colecao():
    return banco()["politicas"]


def _agora():
    return datetime.now(timezone.utc)


def listar(usuario_id):
    return list(_colecao().find({"usuario_id": usuario_id}).sort("criada_em", 1))


def obter(usuario_id, politica_id):
    return _colecao().find_one({"_id": politica_id, "usuario_id": usuario_id})


def criar(usuario_id, dados):
    agora = _agora()
    politica = {**dados, "usuario_id": usuario_id, "criada_em": agora, "atualizada_em": agora}
    _colecao().insert_one(politica)  # o insert_one preenche politica["_id"]
    return politica


def substituir(usuario_id, politica_id, dados):
    """Troca todos os campos editáveis; devolve a política nova ou None se não existir."""
    return _colecao().find_one_and_update(
        {"_id": politica_id, "usuario_id": usuario_id},
        {"$set": {**dados, "atualizada_em": _agora()}},
        return_document=ReturnDocument.AFTER,
    )


def remover(usuario_id, politica_id):
    """Devolve True se removeu, False se a política não existia."""
    return _colecao().delete_one({"_id": politica_id, "usuario_id": usuario_id}).deleted_count == 1
