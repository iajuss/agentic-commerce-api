"""Contrato HTTP global dos módulos integrados M1, M2 e M3."""

import re

from bson import ObjectId

from app import ENDPOINTS_PUBLICOS

ROTAS_DO_CONTRATO = frozenset({
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
    ("POST", "/solicitacoes"),
    ("GET", "/solicitacoes"),
    ("GET", "/solicitacoes/<solicitacao_id>"),
    ("DELETE", "/solicitacoes/<solicitacao_id>"),
    ("POST", "/solicitacoes/<solicitacao_id>/autorizacoes"),
    ("GET", "/autorizacoes"),
    ("GET", "/autorizacoes/<autorizacao_id>"),
    ("DELETE", "/autorizacoes/<autorizacao_id>"),
    ("POST", "/pedidos"),
    ("GET", "/pedidos"),
    ("POST", "/simulador-pix/pagamentos"),
    ("GET", "/pedidos/<pedido_id>"),
    ("PATCH", "/pedidos/<pedido_id>"),
    ("POST", "/pedidos/<pedido_id>/chamados"),
    ("GET", "/pedidos/<pedido_id>/chamados"),
    ("GET", "/pedidos/<pedido_id>/chamados/<chamado_id>"),
})
ENDPOINTS_ESPERADOS = frozenset({
    "saude.health",
    "autenticacao.cadastrar_usuario",
    "autenticacao.criar_sessao",
})
VERBOS_NA_URI = frozenset({
    "criar", "listar", "deletar", "remover", "atualizar",
    "cancelar", "pagar", "aprovar", "buscar", "obter",
})
PARAMETRO = re.compile(r"<(?:[^:>]+:)?[^>]+>")


def _rotas_da_api(app):
    """Ignora a rota static, criada pelo Flask fora do contrato da API."""
    for regra in app.url_map.iter_rules():
        if regra.endpoint == "static":
            continue
        for metodo in regra.methods - {"HEAD", "OPTIONS"}:
            yield metodo, regra.rule, regra.endpoint


def test_ganchos_dos_modulos_estao_ativos(app):
    assert callable(app.extensions["registrar_evento"])
    assert callable(app.extensions["compra_automatica"])
    assert callable(app.extensions["expirar_autorizacoes"])


def test_mapa_da_api_tem_exatamente_as_27_rotas_do_contrato(app):
    obtidas = {(metodo, regra) for metodo, regra, _ in _rotas_da_api(app)}

    assert len(ROTAS_DO_CONTRATO) == 27
    assert obtidas == ROTAS_DO_CONTRATO


def test_so_os_tres_endpoints_do_contrato_sao_publicos(app):
    assert ENDPOINTS_PUBLICOS == ENDPOINTS_ESPERADOS
    assert {
        endpoint for _, _, endpoint in _rotas_da_api(app) if endpoint in ENDPOINTS_PUBLICOS
    } == ENDPOINTS_ESPERADOS


def test_todas_as_outras_rotas_exigem_token(app, client):
    for metodo, regra, endpoint in _rotas_da_api(app):
        if endpoint in ENDPOINTS_PUBLICOS:
            continue
        caminho = PARAMETRO.sub(lambda _: str(ObjectId()), regra)
        resposta = client.open(caminho, method=metodo)
        assert resposta.status_code == 401, (metodo, regra, resposta.get_json())
        assert resposta.get_json() == {"erro": "Faça login para continuar."}


def test_nenhum_segmento_de_uri_e_verbo(app):
    for _, regra, _ in _rotas_da_api(app):
        for segmento in regra.strip("/").split("/"):
            assert segmento not in VERBOS_NA_URI, regra
