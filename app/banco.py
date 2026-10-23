"""Conexão com o MongoDB Atlas e utilitários para trabalhar com os documentos."""

from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app
from pymongo import MongoClient

from app.erros import ErroApi


def iniciar_banco(app, cliente=None):
    """Guarda o banco no app. Os testes passam um cliente falso (mongomock) em `cliente`."""
    if cliente is None:
        if not app.config["MONGO_URI"]:
            raise RuntimeError("MONGO_URI não definida. Copie .env.example para .env e preencha.")
        cliente = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000, tz_aware=True)
    app.extensions["mongo"] = cliente[app.config["MONGO_DB_NAME"]]


def banco():
    """Banco da aplicação atual. Uso: banco()["politicas"].find(...)."""
    return current_app.extensions["mongo"]


def para_object_id(id_texto):
    """Converte o id vindo da URL. Um id malformado não existe no banco, então vira 404."""
    try:
        return ObjectId(id_texto)
    except InvalidId:
        raise ErroApi(404, "Recurso não encontrado.") from None


def documento_para_json(documento):
    """Renomeia o _id do Mongo para id, o nome que a API expõe."""
    documento = dict(documento)
    documento["id"] = documento.pop("_id")
    return documento
