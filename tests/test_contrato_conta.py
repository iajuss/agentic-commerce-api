"""Contrato das rotas de conta e proteção contra chamadas HTTP reais nos testes."""

import pytest
import requests

from app import ENDPOINTS_PUBLICOS


ROTAS_M1 = (
    ("GET", "/health"),
    ("POST", "/usuarios"),
    ("POST", "/sessoes"),
    ("GET", "/usuarios/me"),
    ("PATCH", "/usuarios/me"),
    ("GET", "/politicas"),
    ("POST", "/politicas"),
    ("GET", "/politicas/<politica_id>"),
    ("PUT", "/politicas/<politica_id>"),
    ("DELETE", "/politicas/<politica_id>"),
    ("GET", "/auditoria"),
)
ROTAS_PROTEGIDAS = (
    ("GET", "/usuarios/me"),
    ("PATCH", "/usuarios/me"),
    ("GET", "/politicas"),
    ("POST", "/politicas"),
    ("GET", "/politicas/507f1f77bcf86cd799439011"),
    ("PUT", "/politicas/507f1f77bcf86cd799439011"),
    ("DELETE", "/politicas/507f1f77bcf86cd799439011"),
    ("GET", "/auditoria"),
)


@pytest.mark.parametrize("metodo, regra", ROTAS_M1)
def test_rota_m1_consta_no_mapa(app, metodo, regra):
    assert any(
        rota.rule == regra and metodo in rota.methods
        for rota in app.url_map.iter_rules()
    )


def test_endpoints_publicos_sao_exatamente_os_do_contrato(app):
    esperados = frozenset({
        "saude.health",
        "autenticacao.cadastrar_usuario",
        "autenticacao.criar_sessao",
    })
    assert ENDPOINTS_PUBLICOS == esperados
    assert {
        rota.endpoint for rota in app.url_map.iter_rules() if rota.endpoint in ENDPOINTS_PUBLICOS
    } == esperados


@pytest.mark.parametrize("metodo, caminho", ROTAS_PROTEGIDAS)
def test_rota_m1_protegida_exige_token(client, metodo, caminho):
    resposta = client.open(caminho, method=metodo)

    assert resposta.status_code == 401
    assert resposta.json == {"erro": "Faça login para continuar."}


def test_chamada_http_real_e_bloqueada():
    with pytest.raises(RuntimeError, match=r"^Chamada HTTP real em teste: mocke o adaptador\.$"):
        requests.get("https://exemplo.invalid/")
