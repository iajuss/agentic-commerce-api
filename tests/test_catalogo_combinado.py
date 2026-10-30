"""Catálogo combinado: o fixo e a DummyJSON no mesmo ranking (opção C do spike M2-01), sem rede."""

import json
from pathlib import Path

import pytest
import requests

from app.erros import ErroApi
from app.solicitacoes.catalogo import dummyjson, obter_catalogo
from app.solicitacoes.catalogo.base import validar_oferta
from app.solicitacoes.catalogo.combinado import CatalogoCombinado

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "dummyjson_groceries.json").read_text(encoding="utf-8"))


class CatalogoFalso:
    def __init__(self, *ids, erro=None):
        self.ofertas = [{"id_externo": id_externo} for id_externo in ids]
        self.erro = erro

    def buscar(self, termo, limite=10):
        if self.erro:
            raise self.erro
        return self.ofertas[:limite]


def ids(ofertas):
    return [oferta["id_externo"] for oferta in ofertas]


class RespostaFalsa:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return FIXTURE


@pytest.fixture
def dummyjson_no_ar(monkeypatch):
    monkeypatch.setattr(dummyjson.requests, "get", lambda url, **kwargs: RespostaFalsa())


@pytest.fixture
def dummyjson_fora_do_ar(monkeypatch):
    def get_falso(url, **kwargs):
        raise requests.ConnectionError("sem rede")

    monkeypatch.setattr(dummyjson.requests, "get", get_falso)


def test_intercala_as_ofertas_dos_catalogos():
    catalogo = CatalogoCombinado([CatalogoFalso("F1", "F2", "F3"), CatalogoFalso("D1")])

    assert ids(catalogo.buscar("arroz")) == ["F1", "D1", "F2", "F3"]


def test_respeita_o_limite_sem_perder_o_segundo_catalogo():
    catalogo = CatalogoCombinado([CatalogoFalso("F1", "F2", "F3"), CatalogoFalso("D1")])

    assert ids(catalogo.buscar("arroz", limite=2)) == ["F1", "D1"]


def test_catalogo_fora_do_ar_nao_derruba_a_busca():
    fora_do_ar = CatalogoFalso(erro=ErroApi(502, "Catálogo indisponível."))
    catalogo = CatalogoCombinado([CatalogoFalso("F1", "F2"), fora_do_ar])

    assert ids(catalogo.buscar("arroz")) == ["F1", "F2"]


def test_todos_fora_do_ar_respondem_502():
    fora_do_ar = CatalogoFalso(erro=ErroApi(502, "Catálogo indisponível."))
    catalogo = CatalogoCombinado([fora_do_ar, fora_do_ar])

    with pytest.raises(ErroApi) as erro:
        catalogo.buscar("arroz")

    assert erro.value.status == 502


def test_erro_que_nao_e_de_indisponibilidade_continua_subindo():
    catalogo = CatalogoCombinado([CatalogoFalso("F1"), CatalogoFalso(erro=ValueError("bug"))])

    with pytest.raises(ValueError):
        catalogo.buscar("arroz")


def test_provedor_combinado_traz_ofertas_validas_das_duas_fontes(app, dummyjson_no_ar):
    app.config["CATALOGO_PROVEDOR"] = "combinado"

    with app.app_context():
        ofertas = obter_catalogo().buscar("arroz")

    assert {oferta["fonte"] for oferta in ofertas} == {"fixo", "dummyjson"}
    for oferta in ofertas:
        validar_oferta(oferta)


def test_solicitacao_combinada_ranqueia_as_duas_fontes(app, client, auth, dummyjson_no_ar):
    app.config["CATALOGO_PROVEDOR"] = "combinado"

    arroz, batatas = client.post("/solicitacoes", json={"texto": "arroz 5kg e batatas"}, headers=auth).json["itens"]

    assert arroz["recomendada"]["id_externo"] == "FIXO-001"
    assert "dummyjson" in {oferta["fonte"] for oferta in arroz["alternativas"]}
    assert batatas["recomendada"]["fonte"] == "dummyjson"


def test_solicitacao_combinada_nao_troca_2_leites_por_uma_caixa_com_12(app, client, auth, dummyjson_no_ar):
    app.config["CATALOGO_PROVEDOR"] = "combinado"

    (leite,) = client.post("/solicitacoes", json={"texto": "2 leites integrais"}, headers=auth).json["itens"]

    assert leite["recomendada"]["id_externo"] == "FIXO-008"
    assert leite["quantidade"] == 2


def test_solicitacao_combinada_segue_com_o_fixo_se_a_dummyjson_cair(app, client, auth, dummyjson_fora_do_ar):
    app.config["CATALOGO_PROVEDOR"] = "combinado"

    resposta = client.post("/solicitacoes", json={"texto": "arroz 5kg"}, headers=auth)

    assert resposta.status_code == 201
    assert resposta.json["itens"][0]["recomendada"]["id_externo"] == "FIXO-001"
