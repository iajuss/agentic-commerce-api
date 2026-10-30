"""Ranking explicável das ofertas de um item (função pura)."""

from app.solicitacoes.ranking import ranquear


def oferta(id_externo, titulo, preco, **campos):
    padrao = {"id_externo": id_externo, "titulo": titulo, "preco": preco, "frete": 0.0, "frete_gratis": True,
              "prazo_dias": 2, "avaliacao": 4.5, "marca": None, "loja": "Mercado Exemplo"}
    return {**padrao, **campos}


ARROZ_1KG = oferta("A1", "Arroz Branco 1kg", 6.49)
ARROZ_5KG = oferta("A5", "Arroz Branco 5kg", 27.90)
LEITE_1L = oferta("L1", "Leite Integral 1L", 5.29)
LEITE_CAIXA = oferta("L12", "Leite Integral Caixa 12x1L", 57.90)


def ids(ofertas):
    return [item["id_externo"] for item in ofertas]


def test_embalagem_maior_mais_barata_por_kg_vence():
    primeira, segunda = ranquear([ARROZ_1KG, ARROZ_5KG])

    assert primeira["id_externo"] == "A5"
    assert primeira["preco_por_unidade"] == 5.58
    assert primeira["unidade"] == "kg"
    assert primeira["explicacao"][0] == "Menor preço por kg entre 2 ofertas: R$ 5,58/kg"
    assert segunda["explicacao"][0] == "Preço por kg: R$ 6,49/kg"


def test_frete_gratis_desempata_ofertas_de_mesmo_preco():
    com_frete = oferta("F1", "Feijão 1kg", 8.99, frete=9.90, frete_gratis=False)
    gratis = oferta("F2", "Feijão 1kg", 8.99)

    ranqueadas = ranquear([com_frete, gratis])

    assert ids(ranqueadas) == ["F2", "F1"]
    assert "Frete grátis" in ranqueadas[0]["explicacao"]
    assert "Frete de R$ 9,90" in ranqueadas[1]["explicacao"]


def test_frete_desconhecido_usa_a_estimativa_e_avisa():
    sem_frete = oferta("L1", "Leite 1L", 4.99, frete=None, frete_gratis=False)
    gratis = oferta("L2", "Leite 1L", 4.99)

    ranqueadas = ranquear([sem_frete, gratis])

    assert ids(ranqueadas) == ["L2", "L1"]
    assert "Frete estimado (a loja não informou)" in ranqueadas[1]["explicacao"]


def test_mesma_entrada_gera_a_mesma_ordem_com_desempate_por_id():
    iguais = [oferta("C3", "Café 500g", 19.9), oferta("C1", "Café 500g", 19.9), oferta("C2", "Café 500g", 19.9)]

    assert ids(ranquear(iguais)) == ["C1", "C2", "C3"]
    assert ids(ranquear(list(reversed(iguais)))) == ["C1", "C2", "C3"]


def test_sem_nenhuma_medida_compara_pelo_preco():
    ranqueadas = ranquear([oferta("R2", "Arroz Tipo 1", 6.49), oferta("R1", "Rice", 5.99)])

    assert ids(ranqueadas) == ["R1", "R2"]
    assert ranqueadas[0]["explicacao"][0] == "Menor preço entre 2 ofertas: R$ 5,99"
    assert ranqueadas[0]["preco_por_unidade"] is None


def test_oferta_sem_medida_nao_desliga_o_preco_por_kg_das_outras():
    sem_medida = oferta("DJ", "Rice", 5.99)

    ranqueadas = ranquear([ARROZ_1KG, sem_medida, ARROZ_5KG])

    assert ids(ranqueadas) == ["A5", "A1", "DJ"]
    assert ranqueadas[0]["explicacao"][0] == "Menor preço por kg entre 2 ofertas: R$ 5,58/kg"
    assert ranqueadas[-1]["explicacao"][0] == "Preço: R$ 5,99 (embalagem sem medida em kg)"
    assert ranqueadas[-1]["preco_por_unidade"] is None


def test_oferta_em_outra_unidade_fica_com_a_nota_neutra_no_preco():
    ranqueadas = ranquear([oferta("C1", "Café 500g", 19.90), oferta("C2", "Café 1kg", 34.90),
                           oferta("C3", "Café Gelado 1L", 9.90)])

    assert ids(ranqueadas) == ["C2", "C1", "C3"]
    assert ranqueadas[-1]["explicacao"][0] == "Preço: R$ 9,90 (embalagem sem medida em kg)"


def test_empate_de_unidades_compara_na_primeira_em_ordem_alfabetica():
    ranqueadas = ranquear([oferta("L1", "Leite 1L", 5.29), oferta("K1", "Leite em Pó 400g", 18.90)])

    assert ranqueadas[0]["explicacao"][0] == "Preço por kg: R$ 47,25/kg"
    assert ranqueadas[1]["explicacao"][0] == "Preço: R$ 5,29 (embalagem sem medida em kg)"


def test_criterio_ausente_recebe_nota_neutra_e_fica_fora_da_explicacao():
    sem_dados = oferta("X1", "Açúcar 1kg", 4.99, prazo_dias=None, avaliacao=None)

    (ranqueada,) = ranquear([sem_dados])

    assert ranqueada["explicacao"] == ["Preço por kg: R$ 4,99/kg", "Frete grátis"]


def test_explicacao_traz_prazo_e_avaliacao():
    (ranqueada,) = ranquear([oferta("O1", "Óleo de Soja 900ml", 7.99, prazo_dias=1, avaliacao=4.75)])

    assert "Entrega estimada em 1 dia" in ranqueada["explicacao"]
    assert "Avaliação 4,8" in ranqueada["explicacao"]


def test_marca_preferida_sobe_e_marca_evitada_desce():
    preferida = oferta("M1", "Macarrão 500g", 4.49, marca="Nonna")
    neutra = oferta("M2", "Macarrão 500g", 4.29, marca="Massa Boa")
    evitada = oferta("M3", "Macarrão 500g", 3.99, marca="Barata")
    preferencias = {"marcas_preferidas": ["nonna"], "marcas_evitadas": ["barata"]}

    ranqueadas = ranquear([neutra, evitada, preferida], preferencias)

    assert ids(ranqueadas)[0] == "M1"
    assert ids(ranqueadas)[-1] == "M3"
    assert "Marca preferida" in ranqueadas[0]["explicacao"]
    assert "Marca que você prefere evitar" in ranqueadas[-1]["explicacao"]


def test_embalagem_igual_a_pedida_ganha_bonus():
    meio_pacote = oferta("A25", "Arroz Branco 2,5kg", 13.95)  # mesmo preço por kg do pacote de 5 kg

    ranqueadas = ranquear([meio_pacote, ARROZ_5KG], descricao="arroz 5kg")

    assert ids(ranqueadas) == ["A5", "A25"]
    assert "Embalagem igual à pedida (5 kg)" in ranqueadas[0]["explicacao"]


def test_com_medida_no_pedido_o_que_sobra_nao_barateia_o_preco():
    ranqueadas = ranquear([ARROZ_5KG, ARROZ_1KG], quantidade=2, descricao="arroz 1kg")

    assert ids(ranqueadas) == ["A1", "A5"]
    assert ranqueadas[1]["explicacao"][0] == "Preço por kg: R$ 13,95/kg (o pedido usa 2 kg de 5 kg)"


def test_multipack_conta_so_os_itens_pedidos():
    ranqueadas = ranquear([LEITE_CAIXA, LEITE_1L], quantidade=2, descricao="leites")

    assert ids(ranqueadas) == ["L1", "L12"]
    assert ranqueadas[1]["explicacao"][0] == "Preço por L: R$ 28,95/L (o pedido usa 2 L de 12 L)"
    assert ranqueadas[1]["preco_por_unidade"] == round(57.90 / 12, 2)


def test_multipack_vale_quando_o_pedido_usa_a_caixa_inteira():
    ranqueadas = ranquear([LEITE_1L, LEITE_CAIXA], quantidade=12, descricao="leites")

    assert ids(ranqueadas) == ["L12", "L1"]


def test_nao_altera_as_ofertas_recebidas():
    original = dict(ARROZ_5KG)

    ranquear([ARROZ_5KG, ARROZ_1KG])

    assert ARROZ_5KG == original


def test_lista_vazia_devolve_lista_vazia():
    assert ranquear([]) == []
