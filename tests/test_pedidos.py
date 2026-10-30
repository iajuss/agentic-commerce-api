"""Pedidos com Pix simulado: criação pela autorização, listagem e simulador de pagamento."""

import re
from datetime import timedelta

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

CHAVES_DO_PEDIDO = {"id", "solicitacao_id", "autorizacao_id", "status", "itens", "total", "pix", "historico",
                    "entrega", "criado_em"}
CHAVES_DO_PIX = {"txid", "copia_e_cola", "qr_code_base64", "expira_em", "pago_em"}


@pytest.fixture
def usuario_id(app):
    return inserir_usuario(app)


@pytest.fixture
def cabecalho(cabecalho_de, usuario_id):
    return cabecalho_de(usuario_id)


def _autorizar(app, client, cabecalho, usuario_id, **opcoes):
    solicitacao = inserir_solicitacao(app, usuario_id, **opcoes)
    resposta = client.post(f"/solicitacoes/{solicitacao['_id']}/autorizacoes", json={"senha": SENHA_PADRAO},
                           headers=cabecalho)
    assert resposta.status_code == 201
    return solicitacao, resposta.get_json()


def _pedir(client, cabecalho, autorizacao_id):
    return client.post("/pedidos", json={"autorizacao_id": autorizacao_id}, headers=cabecalho)


def _criar_pedido(app, client, cabecalho, usuario_id):
    solicitacao, autorizacao = _autorizar(app, client, cabecalho, usuario_id)
    resposta = _pedir(client, cabecalho, autorizacao["id"])
    assert resposta.status_code == 201
    return solicitacao, resposta.get_json()


def _pagar(client, cabecalho, txid):
    return client.post("/simulador-pix/pagamentos", json={"txid": txid}, headers=cabecalho)


def _status_da_solicitacao(app, solicitacao):
    return app.extensions["mongo"]["solicitacoes"].find_one({"_id": solicitacao["_id"]})["status"]


# POST /pedidos

def test_cria_pedido_com_location_e_pix_simulado(app, client, cabecalho, usuario_id, relogio):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)

    resposta = _pedir(client, cabecalho, autorizacao["id"])

    assert resposta.status_code == 201
    pedido = resposta.get_json()
    assert resposta.headers["Location"] == f"/pedidos/{pedido['id']}"
    pix = pedido["pix"]
    assert set(pix) == CHAVES_DO_PIX
    assert re.fullmatch(r"[0-9a-f]{32}", pix["txid"])
    assert pix["copia_e_cola"] == f"PIX-SIMULADO-{pix['txid']}"
    assert pix["qr_code_base64"] is None
    assert pix["pago_em"] is None
    assert pix["expira_em"] == (relogio.momento + timedelta(minutes=30)).isoformat()


def test_pedido_tem_o_formato_do_contrato(app, client, cabecalho, usuario_id, relogio):
    solicitacao, autorizacao = _autorizar(app, client, cabecalho, usuario_id)

    pedido = _pedir(client, cabecalho, autorizacao["id"]).get_json()

    assert set(pedido) == CHAVES_DO_PEDIDO
    assert pedido["solicitacao_id"] == str(solicitacao["_id"])
    assert pedido["autorizacao_id"] == autorizacao["id"]
    assert pedido["status"] == "aguardando_pagamento"
    assert pedido["itens"] == autorizacao["itens"]
    assert pedido["total"] == 33.8
    assert pedido["entrega"] == {"simulada": True}
    assert pedido["historico"] == [{"status": "aguardando_pagamento", "em": relogio.momento.isoformat()}]
    assert pedido["criado_em"] == relogio.momento.isoformat()


def test_location_do_pedido_responde_200(app, client, cabecalho, usuario_id):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)
    resposta = _pedir(client, cabecalho, autorizacao["id"])

    obtido = client.get(resposta.headers["Location"], headers=cabecalho)

    assert obtido.status_code == 200
    assert obtido.get_json() == resposta.get_json()


def test_pedido_consome_a_autorizacao(app, client, cabecalho, usuario_id):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)

    _pedir(client, cabecalho, autorizacao["id"])

    obtida = client.get(f"/autorizacoes/{autorizacao['id']}", headers=cabecalho).get_json()
    assert obtida["status"] == "usada"
    assert obtida["usada_em"] is not None
    assert client.get("/autorizacoes", headers=cabecalho).get_json() == []


def test_validade_do_pix_vem_da_configuracao(app, client, cabecalho, usuario_id, relogio):
    app.config["PIX_EXPIRACAO_MINUTOS"] = "10"

    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    assert pedido["pix"]["expira_em"] == (relogio.momento + timedelta(minutes=10)).isoformat()


def test_criar_pedido_emite_evento(app, client, cabecalho, usuario_id, eventos):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)
    eventos.clear()

    pedido = _pedir(client, cabecalho, autorizacao["id"]).get_json()

    assert eventos == [{"usuario_id": usuario_id, "tipo": "pedido_criado", "recurso_tipo": "pedido",
                        "recurso_id": ObjectId(pedido["id"]), "dados": {"total": 33.8}}]


def test_reusar_a_autorizacao_responde_409(app, client, cabecalho, usuario_id):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)
    _pedir(client, cabecalho, autorizacao["id"])

    resposta = _pedir(client, cabecalho, autorizacao["id"])

    assert resposta.status_code == 409
    assert resposta.get_json() == {"erro": "Autorização expirada, revogada ou já usada."}
    assert app.extensions["mongo"]["pedidos"].count_documents({}) == 1


def test_autorizacao_vencida_responde_409(app, client, cabecalho, usuario_id, relogio):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=15)

    resposta = _pedir(client, cabecalho, autorizacao["id"])

    assert resposta.status_code == 409
    assert app.extensions["mongo"]["pedidos"].count_documents({}) == 0


def test_autorizacao_revogada_responde_409(app, client, cabecalho, usuario_id):
    _, autorizacao = _autorizar(app, client, cabecalho, usuario_id)
    client.delete(f"/autorizacoes/{autorizacao['id']}", headers=cabecalho)

    assert _pedir(client, cabecalho, autorizacao["id"]).status_code == 409


def test_autorizacao_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    _, autorizacao = _autorizar(app, client, cabecalho_de(outro_id), outro_id)

    resposta = _pedir(client, cabecalho, autorizacao["id"])

    assert resposta.status_code == 404
    assert client.get(f"/autorizacoes/{autorizacao['id']}", headers=cabecalho_de(outro_id)).get_json()[
        "status"] == "ativa"


@pytest.mark.parametrize("autorizacao_id", [str(ObjectId()), "id-malformado"])
def test_autorizacao_inexistente_responde_404(client, cabecalho, autorizacao_id):
    assert _pedir(client, cabecalho, autorizacao_id).status_code == 404


@pytest.mark.parametrize("corpo", [{}, {"autorizacao_id": ""}, {"autorizacao_id": 123}])
def test_corpo_invalido_do_pedido_responde_400(client, cabecalho, corpo):
    resposta = client.post("/pedidos", json=corpo, headers=cabecalho)

    assert resposta.status_code == 400
    assert resposta.get_json()["detalhes"] == {"autorizacao_id": "Informe a autorização."}


# GET /pedidos

def test_lista_resumos_mais_recentes_primeiro(app, client, cabecalho, usuario_id, relogio):
    _, primeiro = _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=1)
    _, segundo = _criar_pedido(app, client, cabecalho, usuario_id)

    resposta = client.get("/pedidos", headers=cabecalho)

    assert resposta.status_code == 200
    assert resposta.get_json() == [
        {"id": segundo["id"], "status": "aguardando_pagamento", "total": 33.8, "quantidade_itens": 3,
         "criado_em": segundo["criado_em"]},
        {"id": primeiro["id"], "status": "aguardando_pagamento", "total": 33.8, "quantidade_itens": 3,
         "criado_em": primeiro["criado_em"]},
    ]


def test_lista_nao_mostra_pedidos_de_outro_usuario(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    _criar_pedido(app, client, cabecalho_de(outro_id), outro_id)

    assert client.get("/pedidos", headers=cabecalho).get_json() == []


# POST /simulador-pix/pagamentos

def test_simulador_confirma_e_conclui_a_solicitacao(app, client, cabecalho, usuario_id, relogio):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=3)

    resposta = _pagar(client, cabecalho, pedido["pix"]["txid"])

    assert resposta.status_code == 200
    pago = resposta.get_json()
    assert pago["status"] == "pago"
    assert pago["pix"]["pago_em"] == relogio.momento.isoformat()
    assert [registro["status"] for registro in pago["historico"]] == ["aguardando_pagamento", "pago"]
    assert _status_da_solicitacao(app, solicitacao) == "concluida"


def test_simulador_emite_pagamento_confirmado(app, client, cabecalho, usuario_id, eventos):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    eventos.clear()

    _pagar(client, cabecalho, pedido["pix"]["txid"])

    assert eventos == [{"usuario_id": usuario_id, "tipo": "pagamento_confirmado", "recurso_tipo": "pedido",
                        "recurso_id": ObjectId(pedido["id"]), "dados": {"total": 33.8}}]


def test_simular_de_novo_responde_409(app, client, cabecalho, usuario_id, eventos):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido["pix"]["txid"])
    eventos.clear()

    resposta = _pagar(client, cabecalho, pedido["pix"]["txid"])

    assert resposta.status_code == 409
    assert resposta.get_json() == {"erro": "Este pedido não está aguardando pagamento."}
    assert eventos == []
    historico = client.get(f"/pedidos/{pedido['id']}", headers=cabecalho).get_json()["historico"]
    assert len(historico) == 2


def test_pix_vencido_nao_pode_ser_pago(app, client, cabecalho, usuario_id, relogio):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=30)

    resposta = _pagar(client, cabecalho, pedido["pix"]["txid"])

    assert resposta.status_code == 409
    assert resposta.get_json() == {"erro": "Esta cobrança Pix expirou."}
    assert _status_da_solicitacao(app, solicitacao) == "aprovada"


def test_txid_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    _, pedido = _criar_pedido(app, client, cabecalho_de(outro_id), outro_id)

    resposta = _pagar(client, cabecalho, pedido["pix"]["txid"])

    assert resposta.status_code == 404
    assert client.get(f"/pedidos/{pedido['id']}", headers=cabecalho_de(outro_id)).get_json()[
        "status"] == "aguardando_pagamento"


def test_txid_inexistente_responde_404(client, cabecalho):
    assert _pagar(client, cabecalho, "0" * 32).status_code == 404


@pytest.mark.parametrize("corpo", [{}, {"txid": ""}, {"txid": 42}])
def test_corpo_invalido_do_simulador_responde_400(client, cabecalho, corpo):
    resposta = client.post("/simulador-pix/pagamentos", json=corpo, headers=cabecalho)

    assert resposta.status_code == 400
    assert resposta.get_json()["detalhes"] == {"txid": "Informe o txid da cobrança Pix."}


# GET /pedidos/<id> (mínimo; as transições chegam no M3-04)

def test_pedido_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    _, pedido = _criar_pedido(app, client, cabecalho_de(outro_id), outro_id)

    resposta = client.get(f"/pedidos/{pedido['id']}", headers=cabecalho)

    assert resposta.status_code == 404
    assert resposta.get_json() == {"erro": "Pedido não encontrado."}
