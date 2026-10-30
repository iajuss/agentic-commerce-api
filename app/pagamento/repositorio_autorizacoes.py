"""Acesso à coleção `autorizacoes`.

Toda consulta filtra pelo dono, então um usuário nunca lê nem revoga a autorização de outro.
"""

from pymongo import ReturnDocument

from app.banco import banco

ATIVA = "ativa"
REVOGADA = "revogada"
USADA = "usada"


def _colecao():
    return banco()["autorizacoes"]


def criar(autorizacao):
    _colecao().insert_one(autorizacao)  # o insert_one preenche autorizacao["_id"]
    return autorizacao


def obter(usuario_id, autorizacao_id):
    return _colecao().find_one({"_id": autorizacao_id, "usuario_id": usuario_id})


def listar_ativas(usuario_id, agora):
    """Ativas e ainda no prazo, mais recentes primeiro; o _id desempata as criadas no mesmo instante."""
    filtro = {"usuario_id": usuario_id, "status": ATIVA, "expira_em": {"$gt": agora}}
    return list(_colecao().find(filtro).sort([("criada_em", -1), ("_id", -1)]))


def revogar(usuario_id, autorizacao_id, agora):
    """Revoga só se estiver ativa. Devolve a autorização revogada ou None se nada mudou."""
    return _colecao().find_one_and_update(
        {"_id": autorizacao_id, "usuario_id": usuario_id, "status": ATIVA},
        {"$set": {"status": REVOGADA, "revogada_em": agora, "atualizada_em": agora}},
        return_document=ReturnDocument.AFTER,
    )
