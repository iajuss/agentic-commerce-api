"""Interpretação da lista de compras em texto livre (função pura)."""

import pytest

from app.solicitacoes.intencao import interpretar_intencao


def item(descricao, quantidade=1):
    return {"descricao": descricao, "quantidade": quantidade}


@pytest.mark.parametrize("texto, esperado", [
    ("arroz 5kg, 2 leites e detergente", [item("arroz 5kg"), item("leites", 2), item("detergente")]),
    ("2x leite", [item("leite", 2)]),
    ("2 x leite", [item("leite", 2)]),
    ("duas caixas de leite", [item("caixas de leite", 2)]),
    ("três pacotes de café", [item("pacotes de café", 3)]),
    ("Dez ovos", [item("ovos", 10)]),
    ("feijão e arroz", [item("feijão"), item("arroz")]),
    ("feijão", [item("feijão")]),
    ("12 rolos de papel higiênico", [item("12 rolos de papel higiênico")]),
    ("2 kg de feijão", [item("2 kg de feijão")]),
    ("2 quilos de feijão", [item("2 quilos de feijão")]),
    ("2 dúzias de ovos", [item("dúzias de ovos", 2)]),
    ("6 latas de cerveja\n2 refrigerantes", [item("latas de cerveja", 6), item("refrigerantes", 2)]),
    ("leite; Leite, LEITE", [item("leite", 3)]),
    ("café, cafe", [item("café", 2)]),
    ("Café   torrado    500g", [item("Café torrado 500g")]),
    ("60 leites, 50 leites", [item("leites", 99)]),
    ("0 leite", [item("leite")]),
])
def test_interpreta_a_lista_de_compras(texto, esperado):
    assert interpretar_intencao(texto) == esperado


def test_conector_solto_nao_vira_item():
    assert interpretar_intencao("arroz, e") == [item("arroz")]


@pytest.mark.parametrize("texto", ["", "   ", " , ; \n ", ", ; e", None])
def test_texto_sem_itens_devolve_lista_vazia(texto):
    assert interpretar_intencao(texto) == []


def test_descricao_longa_e_cortada_em_80_caracteres():
    (resultado,) = interpretar_intencao("arroz " + "x" * 200)

    assert len(resultado["descricao"]) == 80


def test_nao_corta_o_numero_de_itens():
    texto = ", ".join(f"item {numero}" for numero in range(25))

    assert len(interpretar_intencao(texto)) == 25
