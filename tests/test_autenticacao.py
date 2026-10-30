"""Cadastro, login e proteção das rotas da API."""

from unittest.mock import Mock

from flask import jsonify
from flask_jwt_extended import decode_token
from werkzeug.security import check_password_hash

from app.autenticacao.rotas import HASH_SENHA_FICTICIA

CADASTRO = {"nome": "  Ana Silva  ", "email": "  ANA@Exemplo.com  ", "senha": "senha-forte-123"}


def test_cadastro_cria_usuario_sem_expor_senha(client, app):
    resposta = client.post("/usuarios", json=CADASTRO)

    assert resposta.status_code == 201
    assert resposta.headers["Location"] == "/usuarios/me"
    assert resposta.json == {"id": resposta.json["id"], "nome": "Ana Silva", "email": "ana@exemplo.com"}

    with app.app_context():
        usuario = app.extensions["mongo"]["usuarios"].find_one({"email": "ana@exemplo.com"})
    assert usuario is not None
    assert "senha" not in usuario
    assert usuario["senha_hash"] != CADASTRO["senha"]
    assert check_password_hash(usuario["senha_hash"], CADASTRO["senha"])


def test_cadastro_duplicado_ignora_maiusculas(client):
    client.post("/usuarios", json=CADASTRO)

    resposta = client.post("/usuarios", json={**CADASTRO, "email": "ana@EXEMPLO.com"})

    assert resposta.status_code == 409
    assert resposta.json["detalhes"]["email"]


def test_cadastro_rejeita_campos_invalidos(client):
    resposta = client.post("/usuarios", json={"nome": " ", "email": "inválido", "senha": "curta"})

    assert resposta.status_code == 400
    assert set(resposta.json["detalhes"]) == {"nome", "email", "senha"}


def test_cadastro_rejeita_corpo_nao_json(client):
    resposta = client.post("/usuarios", data="texto")

    assert resposta.status_code == 400
    assert "erro" in resposta.json


def test_login_devolve_token_e_usuario_compativeis_com_o_front(client, app):
    usuario_id = client.post("/usuarios", json=CADASTRO).json["id"]

    resposta = client.post("/sessoes", json={"email": "ANA@EXEMPLO.COM", "senha": CADASTRO["senha"]})

    assert resposta.status_code == 200
    assert resposta.json["usuario"] == {"id": usuario_id, "nome": "Ana Silva", "email": "ana@exemplo.com"}
    with app.app_context():
        assert decode_token(resposta.json["token"])["sub"] == usuario_id
    assert client.get(
        "/politicas", headers={"Authorization": f"Bearer {resposta.json['token']}"}
    ).status_code == 200


def test_login_rejeita_email_ou_senha_incorretos(client):
    client.post("/usuarios", json=CADASTRO)

    for email, senha in (("ana@exemplo.com", "incorreta"), ("outra@exemplo.com", CADASTRO["senha"])):
        resposta = client.post("/sessoes", json={"email": email, "senha": senha})
        assert resposta.status_code == 401
        assert resposta.json == {"erro": "E-mail ou senha inválidos."}


def test_login_verifica_senha_com_email_inexistente(client, monkeypatch):
    verificar_senha = Mock(return_value=False)
    monkeypatch.setattr("app.autenticacao.rotas.check_password_hash", verificar_senha)

    resposta = client.post(
        "/sessoes", json={"email": "inexistente@exemplo.com", "senha": "senha-incorreta"}
    )

    assert resposta.status_code == 401
    assert resposta.json == {"erro": "E-mail ou senha inválidos."}
    verificar_senha.assert_called_once_with(HASH_SENHA_FICTICIA, "senha-incorreta")


def test_login_rejeita_campos_ausentes(client):
    assert client.post("/sessoes", json={"email": "ana@exemplo.com"}).status_code == 401


def test_nova_rota_exige_token_sem_precisar_de_decorador(app, client):
    @app.get("/rota-de-teste")
    def rota_de_teste():
        return jsonify(ok=True)

    resposta = client.get("/rota-de-teste")
    assert resposta.status_code == 401
    assert resposta.json == {"erro": "Faça login para continuar."}

    token = client.post("/sessoes", json={"email": CADASTRO["email"], "senha": CADASTRO["senha"]})
    assert token.status_code == 401

    client.post("/usuarios", json=CADASTRO)
    token = client.post(
        "/sessoes", json={"email": CADASTRO["email"], "senha": CADASTRO["senha"]}
    ).json["token"]
    assert client.get("/rota-de-teste", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_token_invalido_responde_401_em_json(client):
    resposta = client.get("/politicas", headers={"Authorization": "Bearer invalido"})

    assert resposta.status_code == 401
    assert "erro" in resposta.json


def test_health_e_preflight_continuam_publicos(client):
    assert client.get("/health").status_code == 200
    resposta = client.options(
        "/politicas",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert resposta.status_code == 200
