"""Quem está logado, a partir do JWT da requisição."""

from bson import ObjectId
from bson.errors import InvalidId
from flask_jwt_extended import get_jwt_identity

from app.erros import ErroApi


def usuario_atual_id():
    """ObjectId do dono do token. Use dentro de rotas protegidas por @jwt_required()."""
    try:
        return ObjectId(get_jwt_identity())
    except (InvalidId, TypeError):
        raise ErroApi(401, "Sessão inválida. Faça login novamente.") from None
