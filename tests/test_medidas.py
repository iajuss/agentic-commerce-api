"""Medida da embalagem no título da oferta e embalagens que atendem ao pedido (funções puras)."""

import pytest

from app.solicitacoes.medidas import (embalagens_necessarias, extrair_medida, formatar_medida,
                                      quantidade_aproveitada)


def medida(quantidade, unidade):
    return {"quantidade": quantidade, "unidade": unidade}


@pytest.mark.parametrize("titulo, esperada", [
    ("Arroz Branco Tipo 1 5kg", medida(5.0, "kg")),
    ("Café Torrado e Moído 500g", medida(0.5, "kg")),
    ("Sabão em Pó Multiação 1,6kg", medida(1.6, "kg")),
    ("Leite Integral UHT 1L", medida(1.0, "l")),
    ("Leite Integral UHT Caixa 12x1L", medida(12.0, "l")),
    ("Detergente Líquido Neutro 6x500ml", medida(3.0, "l")),
    ("Refrigerante Cola Lata 6 x 350ml", medida(2.1, "l")),
    ("Água Mineral Sem Gás Pack 6x1,5L", medida(9.0, "l")),
    ("Cerveja Pack 12 Latas 350ml", medida(4.2, "l")),
    ("Cerveja 6 garrafas de 600ml", medida(3.6, "l")),
    ("Papel Higiênico Folha Dupla 12 Rolos", medida(12.0, "un")),
    ("Ovos Brancos Grandes 12 Unidades", medida(12.0, "un")),
    ("Óleo de Soja 900 ml", medida(0.9, "l")),
    ("Suco Integral 1 litro", medida(1.0, "l")),
    ("Feijão Carioca 2 quilos", medida(2.0, "kg")),
    ("Café Tradicional 500 gramas", medida(0.5, "kg")),
    ("Ovos Caipira Dúzia", medida(12.0, "un")),
    ("2 dúzias de ovos", medida(24.0, "un")),
    ("meia dúzia de ovos", medida(6.0, "un")),
])
def test_extrai_a_medida_total_da_embalagem(titulo, esperada):
    assert extrair_medida(titulo) == esperada


@pytest.mark.parametrize("titulo", ["Rice", "Café em Grãos Especial", "Arroz Tipo 1", "", None, "Leite 0ml"])
def test_titulo_sem_medida_devolve_none(titulo):
    assert extrair_medida(titulo) is None


@pytest.mark.parametrize("valor, texto", [
    (medida(5.0, "kg"), "5 kg"), (medida(1.5, "l"), "1,5 L"), (medida(12.0, "un"), "12 un"),
])
def test_formata_a_medida_para_a_explicacao(valor, texto):
    assert formatar_medida(valor) == texto


@pytest.mark.parametrize("quantidade, descricao, titulo, esperadas", [
    # com medida no pedido: completa quantidade x medida
    (1, "2 kg de feijão", "Feijão Carioca 1kg", 2),
    (1, "1 quilo de feijão", "Feijão Carioca 500g", 2),
    (1, "arroz 5kg", "Arroz Branco 5kg", 1),
    (1, "arroz 5kg", "Arroz Branco 1kg", 5),
    (2, "arroz 1kg", "Arroz Branco 5kg", 1),
    (1, "detergente 500ml", "Detergente Neutro 6x500ml", 1),
    (1, "12 rolos de papel higiênico", "Papel Higiênico 4 Rolos", 3),
    (2, "dúzias de ovos", "Ovos Brancos 12 Unidades", 2),
    (1, "dúzia de ovos", "Ovos Brancos 6 Unidades", 2),
    (1, "meia dúzia de ovos", "Ovos Brancos 12 Unidades", 1),
    # sem medida: a quantidade conta os itens de uma embalagem com vários
    (10, "ovos", "Ovos Brancos 12 Unidades", 1),
    (30, "ovos", "Ovos Brancos 12 Unidades", 3),
    (2, "detergentes", "Detergente Neutro 6x500ml", 1),
    (2, "caixas de leite", "Leite Integral Caixa 12x1L", 1),
    # ... a não ser que o pedido fale da embalagem
    (2, "caixas de ovos", "Ovos Brancos 12 Unidades", 2),
    (2, "fardos de água", "Água Mineral Fardo 6x1,5L", 2),
    # nos demais casos, a quantidade pedida é o número de embalagens
    (2, "leites", "Leite Integral 1L", 2),
    (3, "arroz", "Arroz Branco 5kg", 3),
    (2, "leite 1kg", "Leite Integral 1L", 2),
    (2, "pão de forma", "Pão de Forma Tradicional", 2),
])
def test_embalagens_necessarias_atendem_ao_pedido(quantidade, descricao, titulo, esperadas):
    assert embalagens_necessarias(quantidade, descricao, titulo)[0] == esperadas


@pytest.mark.parametrize("quantidade, descricao, titulo, frase", [
    (1, "2 kg de feijão", "Feijão Carioca 1kg", "Você pediu 2 kg: 2 embalagens de 1 kg"),
    (2, "arroz 1kg", "Arroz Branco 5kg", "Você pediu 2 kg: 1 embalagem de 5 kg"),
    (10, "ovos", "Ovos Brancos 12 Unidades", "Você pediu 10: 1 embalagem com 12 unidades"),
    (30, "ovos", "Ovos Brancos 12 Unidades", "Você pediu 30: 3 embalagens com 12 unidades"),
])
def test_ajuste_da_quantidade_vem_explicado(quantidade, descricao, titulo, frase):
    assert embalagens_necessarias(quantidade, descricao, titulo)[1] == frase


def test_quantidade_que_nao_muda_nao_gera_explicacao():
    assert embalagens_necessarias(1, "arroz 5kg", "Arroz Branco 5kg") == (1, None)


@pytest.mark.parametrize("quantidade, descricao, titulo, aproveitada", [
    # num multipack, contam só os itens pedidos, a não ser que o pedido seja de embalagens
    (2, "leites", "Leite Integral Caixa 12x1L", 2.0),
    (12, "leites", "Leite Integral Caixa 12x1L", 12.0),
    (2, "fardos de água", "Água Mineral Fardo 6x1,5L", 18.0),
    # com medida no pedido, conta só a quantidade pedida
    (2, "arroz 1kg", "Arroz Branco 5kg", 2.0),
    (1, "arroz 5kg", "Arroz Branco 1kg", 5.0),
    # nos demais casos, a embalagem inteira
    (1, "arroz", "Arroz Branco 5kg", 5.0),
    (10, "ovos", "Ovos Brancos 12 Unidades", 12.0),
    (1, "pão de forma", "Pão de Forma Tradicional", None),
])
def test_quantidade_aproveitada_conta_so_o_que_atende_ao_pedido(quantidade, descricao, titulo, aproveitada):
    assert quantidade_aproveitada(quantidade, descricao, titulo) == aproveitada
