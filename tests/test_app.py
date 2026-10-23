"""Esqueleto da API: /health, padrão de erros JSON e CORS."""

from pymongo.errors import ServerSelectionTimeoutError


def test_health_com_banco_no_ar(client):
    resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json == {"status": "ok", "banco": "ok"}


def test_health_sem_banco_responde_503(app, client, monkeypatch):
    def ping_falha(*args, **kwargs):
        raise ServerSelectionTimeoutError("sem conexão")

    monkeypatch.setattr(app.extensions["mongo"], "command", ping_falha)

    assert client.get("/health").status_code == 503


def test_rota_inexistente_responde_404_em_json(client):
    resposta = client.get("/nao-existe")

    assert resposta.status_code == 404
    assert resposta.json == {"erro": "Recurso não encontrado."}


def test_metodo_nao_permitido_responde_405_em_json(client):
    resposta = client.post("/health")

    assert resposta.status_code == 405
    assert "erro" in resposta.json


def test_erro_inesperado_responde_500_sem_vazar_detalhes(app, client):
    @app.get("/explode")
    def explode():
        raise ValueError("detalhe interno")

    resposta = client.get("/explode")

    assert resposta.status_code == 500
    assert resposta.json == {"erro": "Erro interno do servidor."}


def test_cors_libera_o_front_e_expoe_location(client):
    resposta = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert resposta.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Location" in resposta.headers["Access-Control-Expose-Headers"]


def test_cors_nao_libera_origem_desconhecida(client):
    resposta = client.get("/health", headers={"Origin": "https://site-qualquer.com"})

    assert "Access-Control-Allow-Origin" not in resposta.headers
