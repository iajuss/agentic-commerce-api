"""Índices MongoDB criados na inicialização da API."""

import pytest
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.banco import criar_indices

INDICES_ESPERADOS = [
    ("usuarios", [("email", ASCENDING)], True),
    ("politicas", [("usuario_id", ASCENDING), ("criada_em", ASCENDING)], False),
    ("solicitacoes", [("usuario_id", ASCENDING), ("criada_em", DESCENDING)], False),
    ("autorizacoes", [("usuario_id", ASCENDING), ("status", ASCENDING)], False),
    ("pedidos", [("usuario_id", ASCENDING), ("criado_em", DESCENDING)], False),
    ("pedidos", [("autorizacao_id", ASCENDING)], True),
    ("chamados", [("pedido_id", ASCENDING), ("criado_em", ASCENDING)], False),
    ("auditoria", [("usuario_id", ASCENDING), ("criado_em", DESCENDING)], False),
]


@pytest.mark.parametrize(("colecao", "chaves", "unico"), INDICES_ESPERADOS)
def test_indice_do_contrato_e_criado_no_boot(app, colecao, chaves, unico):
    informacoes = app.extensions["mongo"][colecao].index_information().values()
    indice = next((item for item in informacoes if item["key"] == chaves), None)

    assert indice is not None
    assert indice.get("unique", False) is unico


def test_criar_indices_pode_ser_chamado_repetidas_vezes(app):
    db = app.extensions["mongo"]
    colecoes = {colecao for colecao, _, _ in INDICES_ESPERADOS}
    antes = {colecao: db[colecao].index_information() for colecao in colecoes}

    criar_indices(db)
    criar_indices(db)

    depois = {colecao: db[colecao].index_information() for colecao in colecoes}
    assert depois == antes


def test_email_duplicado_e_rejeitado_pelo_indice_do_boot(app):
    usuarios = app.extensions["mongo"]["usuarios"]
    usuarios.insert_one({"email": "ana@example.com"})

    with pytest.raises(DuplicateKeyError):
        usuarios.insert_one({"email": "ana@example.com"})
