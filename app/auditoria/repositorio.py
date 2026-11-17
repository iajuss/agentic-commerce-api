"""Acesso de inserção e leitura à coleção de auditoria."""

from pymongo import DESCENDING

from app.banco import banco


def inserir(evento):
    """Grava um evento e devolve o documento com seu _id."""
    banco()["auditoria"].insert_one(evento)
    return evento


def listar(usuario_id, limite, antes_de=None, tipo=None):
    """Lista eventos do usuário em ordem de criação decrescente, opcionalmente só de um tipo."""
    filtro = {"usuario_id": usuario_id}
    if antes_de is not None:
        filtro["_id"] = {"$lt": antes_de}
    if tipo is not None:
        filtro["tipo"] = tipo
    return list(banco()["auditoria"].find(filtro).sort("_id", DESCENDING).limit(limite))
