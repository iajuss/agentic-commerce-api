"""Ensina o jsonify a serializar os tipos que o MongoDB devolve."""

from datetime import datetime

from bson import ObjectId
from flask.json.provider import DefaultJSONProvider


class ProvedorJson(DefaultJSONProvider):
    @staticmethod
    def default(valor):
        if isinstance(valor, ObjectId):
            return str(valor)
        if isinstance(valor, datetime):
            return valor.isoformat()
        return DefaultJSONProvider.default(valor)
