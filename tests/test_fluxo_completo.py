"""Fluxos HTTP completos com banco em memória, catálogo fixo e ViaCEP simulado."""

import pytest

from app.autenticacao import viacep
from app.pagamento import regras as regras_pagamento
from app.pos_compra import regras as regras_pos_compra
from app.solicitacoes.catalogo.fixo import CatalogoFixo
from tests.apoio_pagamento import Relogio

CADASTRO = {"nome": "Ana Silva", "email": "ana@example.com", "senha": "senha-forte-123"}
POLITICA = {"nome": "Mercado", "teto_por_compra": 500}
ITEM = {"itens": [{"descricao": "arroz 5kg", "quantidade": 1}]}


@pytest.fixture
def relogio(monkeypatch):
    relogio = Relogio()
    monkeypatch.setattr(regras_pagamento, "agora", relogio)
    monkeypatch.setattr(regras_pos_compra, "agora", relogio)
    return relogio


@pytest.fixture
def catalogo_fixo(app):
    app.extensions["catalogo"] = CatalogoFixo()


def _conta_autenticada(client):
    cadastro = client.post("/usuarios", json=CADASTRO)
    assert cadastro.status_code == 201

    login = client.post("/sessoes", json={"email": CADASTRO["email"], "senha": CADASTRO["senha"]})
    assert login.status_code == 200
    assert login.json["usuario"]["id"] == cadastro.json["id"]
    return {"Authorization": f"Bearer {login.json['token']}"}


def _criar_politica(client, cabecalho, autonomia):
    resposta = client.post(
        "/politicas",
        json={**POLITICA, "nivel_autonomia": autonomia},
        headers=cabecalho,
    )
    assert resposta.status_code == 201
    assert resposta.headers["Location"] == f"/politicas/{resposta.json['id']}"
    return resposta.json


def _solicitar(client, cabecalho):
    resposta = client.post("/solicitacoes", json=ITEM, headers=cabecalho)
    assert resposta.status_code == 201
    assert resposta.headers["Location"] == f"/solicitacoes/{resposta.json['id']}"
    return resposta.json


def _simular_pagamento(client, cabecalho, pedido):
    resposta = client.post(
        "/simulador-pix/pagamentos",
        json={"txid": pedido["pix"]["txid"]},
        headers=cabecalho,
    )
    assert resposta.status_code == 200
    assert resposta.json["status"] == "pago"


def test_fluxo_automatico_ate_entrega_chamado_e_auditoria(
    app, client, catalogo_fixo, relogio, monkeypatch
):
    class RespostaViaCep:
        status_code = 200

        def json(self):
            return {
                "logradouro": "Praça da Sé",
                "bairro": "Sé",
                "localidade": "São Paulo",
                "uf": "SP",
            }

    chamadas = []

    def consultar(url, timeout):
        chamadas.append(url)
        return RespostaViaCep()

    monkeypatch.setattr(viacep.requests, "get", consultar)
    cabecalho = _conta_autenticada(client)

    perfil = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "01001-000", "numero": "10"}},
        headers=cabecalho,
    )
    assert perfil.status_code == 200
    assert perfil.json["endereco"]["cidade"] == "São Paulo"
    assert chamadas == ["https://viacep.com.br/ws/01001000/json/"]

    _criar_politica(client, cabecalho, "automatica")
    solicitacao = _solicitar(client, cabecalho)
    assert solicitacao["status"] == "aprovada"
    assert solicitacao["avaliacao"]["compra_automatica"] is True
    assert set(solicitacao["compra_automatica"]) == {"autorizacao_id", "pedido_id"}

    pedido_id = solicitacao["compra_automatica"]["pedido_id"]
    pedido = client.get(f"/pedidos/{pedido_id}", headers=cabecalho).json
    assert pedido["status"] == "aguardando_pagamento"
    _simular_pagamento(client, cabecalho, pedido)

    relogio.avancar(minutes=7)
    entregue = client.get(f"/pedidos/{pedido_id}", headers=cabecalho)
    assert entregue.status_code == 200
    assert entregue.json["status"] == "entregue"

    chamado = client.post(
        f"/pedidos/{pedido_id}/chamados",
        json={"assunto": "Entrega", "mensagem": "Gostaria de confirmar os itens recebidos."},
        headers=cabecalho,
    )
    assert chamado.status_code == 201
    assert chamado.json["status"] == "aberto"

    auditoria = client.get("/auditoria", headers=cabecalho)
    assert auditoria.status_code == 200
    assert [evento["tipo"] for evento in auditoria.json["eventos"]] == [
        "chamado_aberto",
        "pedido_entregue",
        "pagamento_confirmado",
        "pedido_criado",
        "autorizacao_emitida",
        "solicitacao_criada",
        "politica_criada",
        "perfil_atualizado",
        "sessao_iniciada",
        "usuario_cadastrado",
    ]


def test_fluxo_manual_ate_cancelamento_com_reembolso(app, client, catalogo_fixo, relogio):
    cabecalho = _conta_autenticada(client)
    _criar_politica(client, cabecalho, "manual")

    solicitacao = _solicitar(client, cabecalho)
    assert solicitacao["status"] == "aguardando_aprovacao"
    assert solicitacao["compra_automatica"] is None

    resposta = client.post(
        f"/solicitacoes/{solicitacao['id']}/autorizacoes",
        json={"senha": CADASTRO["senha"]},
        headers=cabecalho,
    )
    assert resposta.status_code == 201
    autorizacao = resposta.json
    assert autorizacao["origem"] == "manual"

    resposta = client.post(
        "/pedidos", json={"autorizacao_id": autorizacao["id"]}, headers=cabecalho
    )
    assert resposta.status_code == 201
    pedido = resposta.json
    assert pedido["status"] == "aguardando_pagamento"
    _simular_pagamento(client, cabecalho, pedido)

    cancelado = client.patch(
        f"/pedidos/{pedido['id']}",
        json={"status": "cancelado"},
        headers=cabecalho,
    )
    assert cancelado.status_code == 200
    assert cancelado.json["status"] == "cancelado"
    assert cancelado.json["reembolso"]["status"] == "simulado"
    assert cancelado.json["reembolso"]["valor"] == pedido["total"]
