"""Conector DummyJSON (catálogo externo da opção C), sempre com a resposta HTTP gravada, sem rede."""

import json
from pathlib import Path

import pytest
import requests

from app.erros import ErroApi
from app.solicitacoes.catalogo import obter_catalogo
from app.solicitacoes.catalogo import dummyjson
from app.solicitacoes.catalogo.base import validar_oferta
from app.solicitacoes.catalogo.dummyjson import CatalogoDummyJson

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "dummyjson_groceries.json").read_text(encoding="utf-8"))


class RespostaFalsa:
    def __init__(self, corpo=FIXTURE, status=200):
        self.corpo = corpo
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if isinstance(self.corpo, Exception):
            raise self.corpo
        return self.corpo


@pytest.fixture
def chamadas(monkeypatch):
    """Troca o requests.get do conector por uma versão que devolve a fixture e registra as chamadas."""
    registro = []

    def get_falso(url, **kwargs):
        registro.append((url, kwargs))
        return RespostaFalsa()

    monkeypatch.setattr(dummyjson.requests, "get", get_falso)
    return registro


@pytest.mark.parametrize("termo, titulo", [
    ("arroz", "Rice"), ("ovos", "Eggs"), ("café", "Nescafe Coffee"), ("batatas", "Potatoes"),
    ("refrigerante", "Soft Drinks"), ("2 leites integrais", "Milk"), ("óleo de cozinha", "Cooking Oil"),
])
def test_traduz_o_termo_e_encontra_o_produto(chamadas, termo, titulo):
    ofertas = CatalogoDummyJson().buscar(termo)

    assert [oferta["titulo"] for oferta in ofertas] == [titulo]
    validar_oferta(ofertas[0])
    assert ofertas[0]["fonte"] == "dummyjson"


def test_termo_sem_nenhuma_traducao_devolve_lista_vazia(chamadas):
    assert CatalogoDummyJson().buscar("detergente") == []


def test_normaliza_preco_prazo_e_frete(chamadas):
    arroz = CatalogoDummyJson().buscar("arroz")[0]

    assert arroz["id_externo"] == "DJ-38"
    assert arroz["preco"] == 5.99
    assert arroz["prazo_dias"] == 1
    assert arroz["frete"] is None
    assert arroz["frete_gratis"] is False
    assert arroz["categorias_caminho"] == ["Mercearia"]


@pytest.mark.parametrize("informacao, dias", [
    ("Ships overnight", 1), ("Ships in 1-2 business days", 2), ("Ships in 3-5 business days", 5),
    ("Ships in 1 week", 7), ("Ships in 2 weeks", 14), ("Ships in 1 month", 30), (None, None), ("Em breve", None),
])
def test_prazo_em_dias(informacao, dias):
    assert dummyjson._prazo_em_dias(informacao) == dias


def test_baixa_uma_vez_e_usa_o_cache(chamadas):
    catalogo = CatalogoDummyJson()

    catalogo.buscar("arroz")
    catalogo.buscar("leite")

    assert len(chamadas) == 1
    assert chamadas[0][1]["timeout"] == 8


def test_cache_vence_depois_de_10_minutos(chamadas):
    instante = [0.0]
    catalogo = CatalogoDummyJson(relogio=lambda: instante[0])

    catalogo.buscar("arroz")
    instante[0] = dummyjson.VALIDADE_CACHE_SEGUNDOS + 1
    catalogo.buscar("arroz")

    assert len(chamadas) == 2


def test_produto_sem_estoque_fica_de_fora(monkeypatch):
    sem_estoque = {"products": [{**FIXTURE["products"][0], "stock": 0}]}
    monkeypatch.setattr(dummyjson.requests, "get", lambda url, **kwargs: RespostaFalsa(sem_estoque))

    assert CatalogoDummyJson().buscar("óleo") == []


@pytest.mark.parametrize("falha", [
    requests.Timeout("lento"), requests.ConnectionError("sem rede"), RespostaFalsa(status=500),
    RespostaFalsa(status=429), RespostaFalsa(corpo=ValueError("json inválido")),
    RespostaFalsa(corpo={"outra": 1}),
])
def test_falha_da_dummyjson_vira_502(monkeypatch, falha):
    def get_falso(url, **kwargs):
        if isinstance(falha, Exception):
            raise falha
        return falha

    monkeypatch.setattr(dummyjson.requests, "get", get_falso)

    with pytest.raises(ErroApi) as erro:
        CatalogoDummyJson().buscar("arroz")

    assert erro.value.status == 502
    assert erro.value.mensagem == dummyjson.INDISPONIVEL


def test_provedor_dummyjson_usa_o_timeout_da_configuracao(app, chamadas):
    app.config.update(CATALOGO_PROVEDOR="dummyjson", HTTP_TIMEOUT_SEGUNDOS=3)

    with app.app_context():
        catalogo = obter_catalogo()
        catalogo.buscar("arroz")

    assert isinstance(catalogo, CatalogoDummyJson)
    assert chamadas[0][1]["timeout"] == 3
