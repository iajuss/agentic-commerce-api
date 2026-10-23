"""GET /health: verifica se a API está no ar e se o Atlas responde."""

from flask import Blueprint, jsonify
from pymongo.errors import PyMongoError

from app.banco import banco

bp = Blueprint("saude", __name__)


@bp.get("/health")
def health():
    try:
        banco().command("ping")
    except PyMongoError:
        return jsonify(status="indisponivel", banco="sem conexão"), 503
    return jsonify(status="ok", banco="ok")
