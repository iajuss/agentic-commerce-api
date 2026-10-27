"""Políticas aplicadas à cesta de supermercado e ao caminho de categorias (funções puras)."""

from bson import ObjectId

from app.politicas.regras import AUTOMATICA, MANUAL, avaliar_cesta, avaliar_oferta

CERVEJA = {"preco": 3.5, "frete": None, "categoria": "Cervejas", "loja": "Mercado Exemplo",
           "categorias_caminho": ["Alimentos e Bebidas", "Bebidas", "Bebidas Alcoólicas", "Cervejas"]}
ARROZ = {"preco": 27.9, "frete": 0.0, "categoria": "Arroz", "loja": "Mercado Exemplo",
         "categorias_caminho": ["Alimentos e Bebidas", "Mercearia", "Arroz"]}


def politica(**campos):
    padrao = {
        "_id": ObjectId(),
        "nome": "Mercado",
        "teto_por_compra": 500.0,
        "categorias": [],
        "lojas": [],
        "nivel_autonomia": MANUAL,
        "ativa": True,
    }
    return {**padrao, **campos}


def cesta(*ofertas_e_quantidades):
    return [{"oferta": oferta, "quantidade": quantidade} for oferta, quantidade in ofertas_e_quantidades]


def test_categoria_da_politica_aceita_subcategoria_pelo_caminho():
    assert avaliar_oferta(CERVEJA, [politica(categorias=["bebidas"])]).permitida


def test_comparacao_de_categoria_ignora_acentos():
    assert avaliar_oferta(CERVEJA, [politica(categorias=["bebidas alcoolicas"])]).permitida


def test_categoria_fora_do_caminho_e_recusada():
    avaliacao = avaliar_oferta(CERVEJA, [politica(categorias=["mercearia"])])

    assert not avaliacao.permitida
    assert avaliacao.motivos == ["Mercado: categoria 'Cervejas' não permitida"]


def test_oferta_sem_caminho_usa_a_categoria():
    oferta = {"preco": 10.0, "categoria": "Arroz", "loja": "Loja"}

    assert avaliar_oferta(oferta, [politica(categorias=["arroz"])]).permitida


def test_frete_desconhecido_conta_como_zero_na_oferta():
    assert avaliar_oferta(CERVEJA, [politica(teto_por_compra=3.5)]).permitida


def test_cesta_dentro_do_teto_e_permitida():
    avaliacao = avaliar_cesta(cesta((ARROZ, 2), (CERVEJA, 6)), 0.0, [politica(teto_por_compra=100)])

    assert avaliacao.permitida
    assert not avaliacao.compra_automatica


def test_cesta_acima_do_teto_explica_o_total_com_frete():
    avaliacao = avaliar_cesta(cesta((ARROZ, 2)), 15.0, [politica(teto_por_compra=60)])

    assert not avaliacao.permitida
    assert avaliacao.motivos == ["Mercado: total de R$ 70,80 passa do teto de R$ 60,00"]


def test_cesta_com_loja_nao_permitida_e_recusada():
    avaliacao = avaliar_cesta(cesta((ARROZ, 1)), 0.0, [politica(lojas=["atacado bom preço"])])

    assert not avaliacao.permitida
    assert avaliacao.motivos == ["Mercado: loja 'Mercado Exemplo' não permitida"]


def test_mesma_politica_precisa_aceitar_a_cesta_inteira():
    so_bebidas = politica(nome="Bebidas", categorias=["bebidas"])
    so_mercearia = politica(nome="Mercearia", categorias=["mercearia"])

    avaliacao = avaliar_cesta(cesta((ARROZ, 1), (CERVEJA, 1)), 0.0, [so_bebidas, so_mercearia])

    assert not avaliacao.permitida
    assert avaliacao.motivos == [
        "Bebidas: categoria 'Arroz' não permitida",
        "Mercearia: categoria 'Cervejas' não permitida",
    ]


def test_motivo_repetido_de_dois_itens_aparece_uma_vez():
    avaliacao = avaliar_cesta(cesta((ARROZ, 1), (ARROZ, 3)), 0.0, [politica(lojas=["outra loja"])])

    assert avaliacao.motivos == ["Mercado: loja 'Mercado Exemplo' não permitida"]


def test_compra_automatica_quando_a_politica_automatica_aceita_a_cesta():
    manual = politica(categorias=["bebidas"])
    automatica = politica(nivel_autonomia=AUTOMATICA)

    avaliacao = avaliar_cesta(cesta((ARROZ, 1), (CERVEJA, 2)), 0.0, [manual, automatica])

    assert avaliacao.compra_automatica
    assert avaliacao.politica_id == automatica["_id"]


def test_cesta_sem_politica_ativa_e_permitida_e_manual():
    avaliacao = avaliar_cesta(cesta((ARROZ, 1)), 0.0, [politica(ativa=False, teto_por_compra=1)])

    assert avaliacao.permitida
    assert not avaliacao.compra_automatica
    assert avaliacao.politica_id is None
