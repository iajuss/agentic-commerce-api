"""Leitura da medida da embalagem no título da oferta (função pura)."""

import pytest

from app.solicitacoes.medidas import extrair_medida, formatar_medida


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
