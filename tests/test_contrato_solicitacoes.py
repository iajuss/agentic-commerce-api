"""Contrato do M2: as rotas (seção 2) e o documento gravado (seção 4) do contrato de integração."""

import pytest
from bson import ObjectId

ROTAS_DO_M2 = {
    ("POST", "/solicitacoes"),
    ("GET", "/solicitacoes"),
    ("GET", "/solicitacoes/<solicitacao_id>"),
    ("DELETE", "/solicitacoes/<solicitacao_id>"),
}

# Campos da seção 4: o documento gravado tem exatamente estes, nem mais nem menos.
CAMPOS_DA_SOLICITACAO = {"_id", "usuario_id", "texto", "itens", "cesta", "avaliacao", "status", "compra_automatica",
                         "criada_em", "atualizada_em"}
CAMPOS_DO_ITEM = {"descricao", "quantidade", "status", "recomendada", "alternativas", "descartadas", "explicacao"}
CAMPOS_DA_OFERTA = {"id_externo", "fonte", "titulo", "marca", "preco", "frete", "frete_gratis", "prazo_dias",
                    "estoque", "categoria", "categorias_caminho", "loja", "avaliacao", "preco_por_unidade", "unidade",
                    "link", "imagem", "pontuacao", "explicacao"}
CAMPOS_DA_CESTA = {"subtotal", "frete", "total", "lojas"}
CAMPOS_DA_AVALIACAO = {"permitida", "compra_automatica", "politica_id", "motivos"}


def test_rotas_do_m2_existem_com_as_regras_do_contrato(app):
    registradas = {
        (metodo, regra.rule)
        for regra in app.url_map.iter_rules()
        for metodo in regra.methods - {"HEAD", "OPTIONS"}
    }

    assert ROTAS_DO_M2 <= registradas


@pytest.mark.parametrize("metodo, regra", sorted(ROTAS_DO_M2))
def test_rotas_do_m2_exigem_login(client, metodo, regra):
    resposta = client.open(regra.replace("<solicitacao_id>", str(ObjectId())), method=metodo, json={})

    assert resposta.status_code == 401
    assert resposta.json == {"erro": "Faça login para continuar."}


def test_documento_gravado_bate_campo_a_campo_com_a_secao_4(app, client, auth):
    client.post("/solicitacoes", json={"texto": "arroz e leite"}, headers=auth)

    documento = app.extensions["mongo"]["solicitacoes"].find_one()
    assert set(documento) == CAMPOS_DA_SOLICITACAO
    assert set(documento["cesta"]) == CAMPOS_DA_CESTA
    assert set(documento["avaliacao"]) == CAMPOS_DA_AVALIACAO
    for item in documento["itens"]:
        assert set(item) == CAMPOS_DO_ITEM
        for oferta in [item["recomendada"], *item["alternativas"]]:
            assert set(oferta) == CAMPOS_DA_OFERTA
