"""Validador de regras e autonomia (funções puras, sem banco nem HTTP)."""

from bson import ObjectId

from app.politicas.regras import AUTOMATICA, MANUAL, avaliar_oferta

OFERTA = {"preco": 300.0, "frete": 20.0, "categoria": "Smartphones", "loja": "Apple"}


def politica(**campos):
    padrao = {
        "_id": ObjectId(),
        "nome": "Padrão",
        "teto_por_compra": 1000.0,
        "categorias": [],
        "lojas": [],
        "nivel_autonomia": MANUAL,
        "ativa": True,
    }
    return {**padrao, **campos}


def test_sem_politica_permite_mas_nunca_compra_sozinho():
    avaliacao = avaliar_oferta(OFERTA, [])

    assert avaliacao.permitida
    assert not avaliacao.compra_automatica


def test_politica_inativa_e_ignorada():
    avaliacao = avaliar_oferta(OFERTA, [politica(teto_por_compra=1, ativa=False)])

    assert avaliacao.permitida


def test_teto_considera_o_frete():
    avaliacao = avaliar_oferta(OFERTA, [politica(nome="Barata", teto_por_compra=310)])

    assert not avaliacao.permitida
    assert avaliacao.motivos == ["Barata: total de R$ 320,00 passa do teto de R$ 310,00"]


def test_categoria_e_loja_ignoram_maiusculas():
    regra = politica(categorias=["smartphones"], lojas=["apple"])

    assert avaliar_oferta(OFERTA, [regra]).permitida


def test_categoria_fora_da_lista_e_recusada():
    avaliacao = avaliar_oferta(OFERTA, [politica(categorias=["books"])])

    assert not avaliacao.permitida
    assert "categoria 'Smartphones' não permitida" in avaliacao.motivos[0]


def test_loja_fora_da_lista_e_recusada():
    assert not avaliar_oferta(OFERTA, [politica(lojas=["samsung"])]).permitida


def test_basta_uma_politica_aceitar():
    livros = politica(categorias=["books"])
    celulares = politica(categorias=["smartphones"])

    avaliacao = avaliar_oferta(OFERTA, [livros, celulares])

    assert avaliacao.permitida
    assert avaliacao.politica_id == celulares["_id"]


def test_compra_automatica_quando_politica_automatica_aceita():
    manual = politica()
    automatica = politica(nivel_autonomia=AUTOMATICA)

    avaliacao = avaliar_oferta(OFERTA, [manual, automatica])

    assert avaliacao.compra_automatica
    assert avaliacao.politica_id == automatica["_id"]


def test_politica_automatica_que_recusa_nao_libera_compra_sozinha():
    manual = politica()
    automatica_barata = politica(nivel_autonomia=AUTOMATICA, teto_por_compra=100)

    avaliacao = avaliar_oferta(OFERTA, [manual, automatica_barata])

    assert avaliacao.permitida
    assert not avaliacao.compra_automatica
