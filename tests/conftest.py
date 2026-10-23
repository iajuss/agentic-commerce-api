"""Fixtures compartilhadas: app com banco em memória (mongomock) e tokens de teste."""

import mongomock
import pytest
from bson import ObjectId
from flask_jwt_extended import create_access_token

from app import create_app


@pytest.fixture
def app():
    config = {"TESTING": True, "JWT_SECRET_KEY": "chave-so-para-testes-com-32-caracteres"}
    return create_app(config, cliente_mongo=mongomock.MongoClient(tz_aware=True))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def cabecalho_de(app):
    """Gera o cabeçalho Authorization de um usuário: cabecalho_de(usuario_id)."""

    def gerar(usuario_id):
        with app.app_context():
            token = create_access_token(identity=str(usuario_id))
        return {"Authorization": f"Bearer {token}"}

    return gerar


@pytest.fixture
def auth(cabecalho_de):
    """Cabeçalho de um usuário qualquer, para testes com um só usuário."""
    return cabecalho_de(ObjectId())
