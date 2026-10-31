"""Acesso à coleção `autorizacoes`.

Toda consulta filtra pelo dono, então um usuário nunca lê nem revoga a autorização de outro.
"""

from pymongo import ReturnDocument

from app.banco import banco

ATIVA = "ativa"
EXPIRADA = "expirada"
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


def listar_vencidas(usuario_id, agora, solicitacao_id=None):
    """Ativas cujo prazo já passou, ou seja, que venceram sem virar pedido."""
    filtro = {"usuario_id": usuario_id, "status": ATIVA, "expira_em": {"$lte": agora}}
    if solicitacao_id is not None:
        filtro["solicitacao_id"] = solicitacao_id
    return list(_colecao().find(filtro))


def expirar(usuario_id, autorizacao, agora):
    """Marca como expirada só se ainda estiver ativa e vencida. Devolve a autorização ou None se nada mudou.

    `expirada_em` é o fim do prazo (`expira_em`), não a hora em que a expiração foi aplicada.
    """
    return _colecao().find_one_and_update(
        {"_id": autorizacao["_id"], "usuario_id": usuario_id, "status": ATIVA, "expira_em": {"$lte": agora}},
        {"$set": {"status": EXPIRADA, "expirada_em": autorizacao["expira_em"], "atualizada_em": agora}},
        return_document=ReturnDocument.AFTER,
    )


def consumir(usuario_id, autorizacao_id, agora):
    """Uso único: marca como usada só se estiver ativa e no prazo. Devolve a autorização ou None."""
    return _colecao().find_one_and_update(
        {"_id": autorizacao_id, "usuario_id": usuario_id, "status": ATIVA, "expira_em": {"$gt": agora}},
        {"$set": {"status": USADA, "usada_em": agora, "atualizada_em": agora}},
        return_document=ReturnDocument.AFTER,
    )


def revogar(usuario_id, autorizacao_id, agora):
    """Revoga só se estiver ativa. Devolve a autorização revogada ou None se nada mudou."""
    return _colecao().find_one_and_update(
        {"_id": autorizacao_id, "usuario_id": usuario_id, "status": ATIVA},
        {"$set": {"status": REVOGADA, "revogada_em": agora, "atualizada_em": agora}},
        return_document=ReturnDocument.AFTER,
    )
