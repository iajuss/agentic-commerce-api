"""Chamados de pós-venda: POST e GET /pedidos/<pedido_id>/chamados e GET de um chamado."""

import pytest
from bson import ObjectId

from tests.apoio_pagamento import (  # noqa: F401
    SENHA_PADRAO,
    eventos,
    ganchos_isolados,
    inserir_solicitacao,
    inserir_usuario,
    relogio,
)

CHAMADO = {"assunto": "Produto faltando", "mensagem": "O leite não veio na entrega."}


@pytest.fixture
def usuario_id(app):
    return inserir_usuario(app)


@pytest.fixture
def cabecalho(cabecalho_de, usuario_id):
    return cabecalho_de(usuario_id)


def _criar_pedido(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)
    autorizacao = client.post(f"/solicitacoes/{solicitacao['_id']}/autorizacoes", json={"senha": SENHA_PADRAO},
                              headers=cabecalho).get_json()
    return client.post("/pedidos", json={"autorizacao_id": autorizacao["id"]}, headers=cabecalho).get_json()


def _abrir(client, cabecalho, pedido, corpo=CHAMADO):
    return client.post(f"/pedidos/{pedido['id']}/chamados", json=corpo, headers=cabecalho)


def test_abre_chamado_com_location_que_responde(app, client, cabecalho, usuario_id, relogio, eventos):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    eventos.clear()

    resposta = _abrir(client, cabecalho, pedido, {**CHAMADO, "assunto": "  Produto faltando "})

    assert resposta.status_code == 201
    chamado = resposta.get_json()
    assert resposta.headers["Location"] == f"/pedidos/{pedido['id']}/chamados/{chamado['id']}"
    assert chamado == {"id": chamado["id"], "pedido_id": pedido["id"], "assunto": "Produto faltando",
                       "mensagem": CHAMADO["mensagem"], "status": "aberto",
                       "criado_em": relogio.momento.isoformat(), "atualizado_em": relogio.momento.isoformat()}
    lido = client.get(resposta.headers["Location"], headers=cabecalho)
    assert lido.status_code == 200
    assert lido.get_json() == chamado
    assert eventos == [{"usuario_id": usuario_id, "tipo": "chamado_aberto", "recurso_tipo": "chamado",
                        "recurso_id": ObjectId(chamado["id"]), "dados": None}]


def test_lista_os_chamados_do_pedido_mais_recentes_primeiro(app, client, cabecalho, usuario_id, relogio):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    outro_pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    primeiro = _abrir(client, cabecalho, pedido).get_json()
    relogio.avancar(minutes=1)
    segundo = _abrir(client, cabecalho, pedido, {**CHAMADO, "assunto": "Entrega atrasada"}).get_json()
    _abrir(client, cabecalho, outro_pedido)

    resposta = client.get(f"/pedidos/{pedido['id']}/chamados", headers=cabecalho)

    assert resposta.status_code == 200
    assert [chamado["id"] for chamado in resposta.get_json()] == [segundo["id"], primeiro["id"]]


def test_pedido_sem_chamados_lista_vazia(app, client, cabecalho, usuario_id):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    assert client.get(f"/pedidos/{pedido['id']}/chamados", headers=cabecalho).get_json() == []


@pytest.mark.parametrize("corpo, campos", [
    ({}, {"assunto", "mensagem"}),
    ({**CHAMADO, "assunto": "ab"}, {"assunto"}),
    ({**CHAMADO, "assunto": "  ab  "}, {"assunto"}),
    ({**CHAMADO, "assunto": "x" * 81}, {"assunto"}),
    ({**CHAMADO, "assunto": 123}, {"assunto"}),
    ({**CHAMADO, "mensagem": "curta"}, {"mensagem"}),
    ({**CHAMADO, "mensagem": "x" * 1001}, {"mensagem"}),
    ({**CHAMADO, "mensagem": None}, {"mensagem"}),
])
def test_corpo_invalido_responde_400(app, client, cabecalho, usuario_id, corpo, campos):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    resposta = _abrir(client, cabecalho, pedido, corpo)

    assert resposta.status_code == 400
    assert set(resposta.get_json()["detalhes"]) == campos
    assert client.get(f"/pedidos/{pedido['id']}/chamados", headers=cabecalho).get_json() == []


def test_limites_do_corpo_sao_aceitos(app, client, cabecalho, usuario_id):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    assert _abrir(client, cabecalho, pedido, {"assunto": "abc", "mensagem": "x" * 10}).status_code == 201
    assert _abrir(client, cabecalho, pedido, {"assunto": "x" * 80, "mensagem": "x" * 1000}).status_code == 201


def test_corpo_que_nao_e_json_responde_400(app, client, cabecalho, usuario_id):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    assert client.post(f"/pedidos/{pedido['id']}/chamados", headers=cabecalho).status_code == 400


def test_pedido_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    pedido = _criar_pedido(app, client, cabecalho_de(outro_id), outro_id)
    chamado = _abrir(client, cabecalho_de(outro_id), pedido).get_json()

    assert _abrir(client, cabecalho, pedido).status_code == 404
    assert client.get(f"/pedidos/{pedido['id']}/chamados", headers=cabecalho).status_code == 404
    assert client.get(f"/pedidos/{pedido['id']}/chamados/{chamado['id']}", headers=cabecalho).status_code == 404


def test_pedido_inexistente_responde_404(client, cabecalho):
    assert client.get(f"/pedidos/{ObjectId()}/chamados", headers=cabecalho).status_code == 404
    assert client.post(f"/pedidos/{ObjectId()}/chamados", json=CHAMADO, headers=cabecalho).status_code == 404


def test_chamado_de_outro_pedido_responde_404(app, client, cabecalho, usuario_id):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    outro_pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    chamado = _abrir(client, cabecalho, outro_pedido).get_json()

    resposta = client.get(f"/pedidos/{pedido['id']}/chamados/{chamado['id']}", headers=cabecalho)

    assert resposta.status_code == 404
    assert resposta.get_json()["erro"] == "Chamado não encontrado."


def test_chamado_inexistente_responde_404(app, client, cabecalho, usuario_id):
    pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    assert client.get(f"/pedidos/{pedido['id']}/chamados/{ObjectId()}", headers=cabecalho).status_code == 404
