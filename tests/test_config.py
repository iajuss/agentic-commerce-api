"""Configuração do MVP, validade do JWT e URLs atrás do proxy."""

import mongomock
import pytest
from bson import ObjectId
from flask_jwt_extended import create_access_token, decode_token

from app import create_app

CADASTRO = {"nome": "Ana Silva", "email": "ana@example.com", "senha": "senha-forte-123"}
CHAVES_DO_CONTRATO = {
    "MONGO_URI",
    "MONGO_DB_NAME",
    "JWT_SECRET_KEY",
    "JWT_EXPIRA_HORAS",
    "CORS_ORIGINS",
    "HTTP_TIMEOUT_SEGUNDOS",
    "PROXY_FIX",
    "CATALOGO_PROVEDOR",
    "ML_CLIENT_ID",
    "ML_CLIENT_SECRET",
    "ML_REDIRECT_URI",
    "ML_REFRESH_TOKEN",
    "ML_VENDEDORES",
    "PIX_EXPIRACAO_MINUTOS",
    "AUTORIZACAO_VALIDADE_MINUTOS",
    "SIMULACAO_ENVIO_MINUTOS",
    "SIMULACAO_ENTREGA_MINUTOS",
}
CHAVES_NUMERICAS = {
    "JWT_EXPIRA_HORAS",
    "HTTP_TIMEOUT_SEGUNDOS",
    "PROXY_FIX",
    "PIX_EXPIRACAO_MINUTOS",
    "AUTORIZACAO_VALIDADE_MINUTOS",
    "SIMULACAO_ENVIO_MINUTOS",
    "SIMULACAO_ENTREGA_MINUTOS",
}


def test_config_carrega_todas_as_chaves_do_contrato(app):
    assert CHAVES_DO_CONTRATO <= app.config.keys()
    assert all(isinstance(app.config[chave], int) for chave in CHAVES_NUMERICAS)


def test_token_de_login_expira_em_oito_horas(app, client):
    assert client.post("/usuarios", json=CADASTRO).status_code == 201

    resposta = client.post("/sessoes", json={"email": CADASTRO["email"], "senha": CADASTRO["senha"]})

    assert resposta.status_code == 200
    with app.app_context():
        token = decode_token(resposta.json["token"])
    assert token["exp"] - token["iat"] == 8 * 60 * 60


def test_proxy_fix_inclui_prefixo_no_location():
    app = create_app(
        {"TESTING": True, "JWT_SECRET_KEY": "chave-de-teste-com-pelo-menos-32-caracteres", "PROXY_FIX": 1},
        cliente_mongo=mongomock.MongoClient(tz_aware=True),
    )
    with app.app_context():
        token = create_access_token(identity=str(ObjectId()))

    resposta = app.test_client().post(
        "/politicas",
        json={"nome": "Mercado", "teto_por_compra": 100},
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-Prefix": "/api"},
    )

    assert resposta.status_code == 201
    assert resposta.headers["Location"] == f"/api/politicas/{resposta.json['id']}"


def test_provedor_combinado_permite_inicializacao():
    app = create_app(
        {
            "TESTING": True,
            "JWT_SECRET_KEY": "chave-de-teste-com-pelo-menos-32-caracteres",
            "CATALOGO_PROVEDOR": "combinado",
        },
        cliente_mongo=mongomock.MongoClient(tz_aware=True),
    )

    assert app.config["CATALOGO_PROVEDOR"] == "combinado"


@pytest.mark.parametrize("provedor", ["desconhecido", "mercadolivre"])
def test_provedor_sem_suporte_impede_inicializacao(provedor):
    with pytest.raises(RuntimeError, match="CATALOGO_PROVEDOR"):
        create_app(
            {
                "TESTING": True,
                "JWT_SECRET_KEY": "chave-de-teste-com-pelo-menos-32-caracteres",
                "CATALOGO_PROVEDOR": provedor,
            },
            cliente_mongo=mongomock.MongoClient(tz_aware=True),
        )
