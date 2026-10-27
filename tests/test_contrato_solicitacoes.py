"""Contrato das rotas do M2 (seção 2 de docs/plano-backend/00-contrato-de-integracao.md)."""

import pytest
from bson import ObjectId

ROTAS_DO_M2 = {
    ("POST", "/solicitacoes"),
    ("GET", "/solicitacoes"),
    ("GET", "/solicitacoes/<solicitacao_id>"),
    ("DELETE", "/solicitacoes/<solicitacao_id>"),
}


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
