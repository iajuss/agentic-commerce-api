"""Acesso à coleção `chamados`. Toda consulta filtra pelo dono e pelo pedido."""

from app.banco import banco


def _colecao():
    return banco()["chamados"]


def criar(chamado):
    _colecao().insert_one(chamado)  # o insert_one preenche chamado["_id"]
    return chamado


def listar(usuario_id, pedido_id):
    """Mais recentes primeiro; o _id desempata os criados no mesmo instante."""
    filtro = {"usuario_id": usuario_id, "pedido_id": pedido_id}
    return list(_colecao().find(filtro).sort([("criado_em", -1), ("_id", -1)]))


def obter(usuario_id, pedido_id, chamado_id):
    return _colecao().find_one({"_id": chamado_id, "usuario_id": usuario_id, "pedido_id": pedido_id})
