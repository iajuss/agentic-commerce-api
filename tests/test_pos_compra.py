"""Estados do pedido: transições simuladas (expiração, envio, entrega, devolução) e comprovante."""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.pos_compra.regras import transicao_permitida, transicoes_devidas
from tests.apoio_pagamento import (  # noqa: F401
    SENHA_PADRAO,
    eventos,
    ganchos_isolados,
    inserir_solicitacao,
    inserir_usuario,
    relogio,
)

INICIO = datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc)


def _min(minutos):
    return INICIO + timedelta(minutes=minutos)


def _pedido(status, historico, pago_em=None):
    return {"status": status, "pix": {"expira_em": _min(30), "pago_em": pago_em},
            "historico": [{"status": s, "em": em} for s, em in historico]}


AGUARDANDO = _pedido("aguardando_pagamento", [("aguardando_pagamento", _min(0))])
PAGO = _pedido("pago", [("aguardando_pagamento", _min(0)), ("pago", _min(10))], pago_em=_min(10))
ENVIADO = _pedido("enviado", [("aguardando_pagamento", _min(0)), ("pago", _min(10)), ("enviado", _min(12))],
                  pago_em=_min(10))
DEVOLUCAO = _pedido("devolucao_solicitada", [("entregue", _min(17)), ("devolucao_solicitada", _min(60))],
                    pago_em=_min(10))


# transicoes_devidas (envio em 2 minutos, entrega em 5)

@pytest.mark.parametrize("pedido, minutos, esperado", [
    (AGUARDANDO, 29, []),
    (AGUARDANDO, 30, [("aguardando_pagamento", "expirado", _min(30))]),
    (PAGO, 11, []),
    (PAGO, 12, [("pago", "enviado", _min(12))]),
    (PAGO, 16, [("pago", "enviado", _min(12))]),
    (PAGO, 17, [("pago", "enviado", _min(12)), ("enviado", "entregue", _min(17))]),
    (PAGO, 600, [("pago", "enviado", _min(12)), ("enviado", "entregue", _min(17))]),
    (ENVIADO, 16, []),
    (ENVIADO, 17, [("enviado", "entregue", _min(17))]),
    (DEVOLUCAO, 64, []),
    (DEVOLUCAO, 65, [("devolucao_solicitada", "devolvido", _min(65))]),
])
def test_transicoes_devidas(pedido, minutos, esperado):
    assert transicoes_devidas(pedido, _min(minutos), 2, 5) == esperado


@pytest.mark.parametrize("status", ["entregue", "expirado", "cancelado", "devolvido"])
def test_status_sem_transicao_automatica(status):
    pedido = {**PAGO, "status": status}

    assert transicoes_devidas(pedido, _min(10_000), 2, 5) == []


def test_minutos_de_envio_e_entrega_sao_parametros():
    assert transicoes_devidas(PAGO, _min(20), 10, 10) == [("pago", "enviado", _min(20))]


# transicao_permitida

@pytest.mark.parametrize("atual, novo", [
    ("aguardando_pagamento", "pago"),
    ("aguardando_pagamento", "expirado"),
    ("aguardando_pagamento", "cancelado"),
    ("pago", "enviado"),
    ("enviado", "entregue"),
    ("pago", "cancelado"),
    ("enviado", "cancelado"),
    ("entregue", "devolucao_solicitada"),
    ("devolucao_solicitada", "devolvido"),
])
def test_transicoes_da_tabela_sao_permitidas(atual, novo):
    assert transicao_permitida(atual, novo)


@pytest.mark.parametrize("atual, novo", [
    ("entregue", "cancelado"),
    ("expirado", "pago"),
    ("cancelado", "pago"),
    ("pago", "devolucao_solicitada"),
    ("devolvido", "devolucao_solicitada"),
    ("aguardando_pagamento", "entregue"),
])
def test_transicoes_fora_da_tabela_sao_recusadas(atual, novo):
    assert not transicao_permitida(atual, novo)


# Pela rota, com o relógio avançando

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
    pedido = client.post("/pedidos", json={"autorizacao_id": autorizacao["id"]}, headers=cabecalho).get_json()
    return solicitacao, pedido


def _pagar(client, cabecalho, pedido):
    resposta = client.post("/simulador-pix/pagamentos", json={"txid": pedido["pix"]["txid"]}, headers=cabecalho)
    assert resposta.status_code == 200
    return resposta.get_json()


def _ler(client, cabecalho, pedido):
    resposta = client.get(f"/pedidos/{pedido['id']}", headers=cabecalho)
    assert resposta.status_code == 200
    return resposta.get_json()


def _patch(client, cabecalho, pedido, corpo):
    return client.patch(f"/pedidos/{pedido['id']}", json=corpo, headers=cabecalho)


def _status_da_solicitacao(app, solicitacao):
    return app.extensions["mongo"]["solicitacoes"].find_one({"_id": solicitacao["_id"]})["status"]


def _historico(pedido):
    return [(registro["status"], registro["em"]) for registro in pedido["historico"]]


def _tipos(eventos):
    return [evento["tipo"] for evento in eventos]


def test_pedido_pago_e_enviado_e_depois_entregue(app, client, cabecalho, usuario_id, relogio):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    pago_em = relogio.momento
    _pagar(client, cabecalho, pedido)

    relogio.avancar(minutes=1)
    assert _ler(client, cabecalho, pedido)["status"] == "pago"
    relogio.avancar(minutes=1)
    assert _ler(client, cabecalho, pedido)["status"] == "enviado"
    relogio.avancar(minutes=5)
    lido = _ler(client, cabecalho, pedido)

    assert lido["status"] == "entregue"
    assert _historico(lido) == [
        ("aguardando_pagamento", pago_em.isoformat()),
        ("pago", pago_em.isoformat()),
        ("enviado", (pago_em + timedelta(minutes=2)).isoformat()),
        ("entregue", (pago_em + timedelta(minutes=7)).isoformat()),
    ]


def test_leitura_tardia_aplica_envio_e_entrega_de_uma_vez(app, client, cabecalho, usuario_id, relogio):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)
    relogio.avancar(days=2)

    lido = _ler(client, cabecalho, pedido)

    assert lido["status"] == "entregue"
    assert [status for status, _ in _historico(lido)] == ["aguardando_pagamento", "pago", "enviado", "entregue"]


def test_duas_leituras_nao_duplicam_historico_nem_eventos(app, client, cabecalho, usuario_id, relogio, eventos):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)
    relogio.avancar(minutes=10)
    eventos.clear()

    primeira = _ler(client, cabecalho, pedido)
    segunda = _ler(client, cabecalho, pedido)

    assert primeira == segunda
    assert len(segunda["historico"]) == 4
    assert eventos == [{"usuario_id": usuario_id, "tipo": "pedido_entregue", "recurso_tipo": "pedido",
                        "recurso_id": ObjectId(pedido["id"]), "dados": None}]


def test_pedido_nao_pago_expira_e_a_solicitacao_tambem(app, client, cabecalho, usuario_id, relogio, eventos):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=29)
    assert _ler(client, cabecalho, pedido)["status"] == "aguardando_pagamento"
    eventos.clear()

    relogio.avancar(minutes=1)
    lido = _ler(client, cabecalho, pedido)
    _ler(client, cabecalho, pedido)

    assert lido["status"] == "expirado"
    assert _historico(lido)[-1] == ("expirado", pedido["pix"]["expira_em"])
    assert _status_da_solicitacao(app, solicitacao) == "expirada"
    assert _tipos(eventos) == ["pedido_expirado"]


def test_comprovante_mostra_copia_e_cola_so_enquanto_aguarda(app, client, cabecalho, usuario_id, relogio):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    assert _ler(client, cabecalho, pedido)["pix"]["copia_e_cola"] == f"PIX-SIMULADO-{pedido['pix']['txid']}"

    pago = _pagar(client, cabecalho, pedido)

    assert pago["pix"] == {"txid": pedido["pix"]["txid"], "pago_em": relogio.momento.isoformat()}
    assert _ler(client, cabecalho, pedido)["pix"] == pago["pix"]


def test_comprovante_de_pedido_expirado_nao_tem_copia_e_cola(app, client, cabecalho, usuario_id, relogio):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=30)

    assert _ler(client, cabecalho, pedido)["pix"] == {"txid": pedido["pix"]["txid"], "pago_em": None}


def test_lista_de_pedidos_mostra_o_status_atualizado(app, client, cabecalho, usuario_id, relogio):
    _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=30)

    assert [resumo["status"] for resumo in client.get("/pedidos", headers=cabecalho).get_json()] == ["expirado"]


def test_ritmo_da_simulacao_vem_da_configuracao(app, client, cabecalho, usuario_id, relogio):
    app.config.update(SIMULACAO_ENVIO_MINUTOS="10", SIMULACAO_ENTREGA_MINUTOS="20")
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)

    relogio.avancar(minutes=9)
    assert _ler(client, cabecalho, pedido)["status"] == "pago"
    relogio.avancar(minutes=1)
    assert _ler(client, cabecalho, pedido)["status"] == "enviado"
    relogio.avancar(minutes=20)
    assert _ler(client, cabecalho, pedido)["status"] == "entregue"


def test_devolucao_solicitada_vira_devolvido_com_reembolso(app, client, cabecalho, usuario_id, relogio):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)
    relogio.avancar(minutes=10)
    _patch(client, cabecalho, pedido, {"status": "devolucao_solicitada", "motivo": "Veio errado"})

    relogio.avancar(minutes=4)
    assert "reembolso" not in _ler(client, cabecalho, pedido)
    relogio.avancar(minutes=1)
    lido = _ler(client, cabecalho, pedido)

    assert lido["status"] == "devolvido"
    assert lido["reembolso"] == {"valor": 33.8, "status": "simulado", "em": relogio.momento.isoformat()}
    assert len(_ler(client, cabecalho, pedido)["historico"]) == 6


def test_pedido_de_outro_usuario_responde_404_sem_aplicar_transicoes(app, client, cabecalho, cabecalho_de,
                                                                      relogio):
    outro_id = inserir_usuario(app)
    solicitacao, pedido = _criar_pedido(app, client, cabecalho_de(outro_id), outro_id)
    relogio.avancar(minutes=30)

    assert client.get(f"/pedidos/{pedido['id']}", headers=cabecalho).status_code == 404
    assert _status_da_solicitacao(app, solicitacao) == "aprovada"


# PATCH /pedidos/<id>: cancelamento e devolução

CANCELAR = {"status": "cancelado"}
DEVOLVER = {"status": "devolucao_solicitada", "motivo": "Veio errado"}


def _entregue(app, client, cabecalho, usuario_id, relogio):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)
    relogio.avancar(minutes=7)
    return solicitacao, pedido


def test_cancelar_pedido_aguardando_pagamento_expira_a_solicitacao(app, client, cabecalho, usuario_id, eventos):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    eventos.clear()

    resposta = _patch(client, cabecalho, pedido, CANCELAR)

    assert resposta.status_code == 200
    assert resposta.get_json()["status"] == "cancelado"
    assert "reembolso" not in resposta.get_json()
    assert _status_da_solicitacao(app, solicitacao) == "expirada"
    assert _tipos(eventos) == ["pedido_cancelado"]


@pytest.mark.parametrize("minutos, status_antes", [(1, "pago"), (3, "enviado")])
def test_cancelar_pedido_pago_ou_enviado_grava_reembolso(app, client, cabecalho, usuario_id, relogio, minutos,
                                                         status_antes):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)
    relogio.avancar(minutes=minutos)

    corpo = _patch(client, cabecalho, pedido, CANCELAR).get_json()

    assert corpo["status"] == "cancelado"
    assert [status for status, _ in _historico(corpo)][-2:] == [status_antes, "cancelado"]
    assert corpo["reembolso"] == {"valor": 33.8, "status": "simulado", "em": relogio.momento.isoformat()}
    assert _status_da_solicitacao(app, solicitacao) == "concluida"


def test_pedir_devolucao_de_pedido_entregue(app, client, cabecalho, usuario_id, relogio, eventos):
    _, pedido = _entregue(app, client, cabecalho, usuario_id, relogio)
    _ler(client, cabecalho, pedido)
    relogio.avancar(days=7)
    eventos.clear()

    resposta = _patch(client, cabecalho, pedido, {**DEVOLVER, "motivo": "  Veio errado  "})

    assert resposta.status_code == 200
    assert resposta.get_json()["status"] == "devolucao_solicitada"
    assert resposta.get_json()["devolucao"] == {"motivo": "Veio errado"}
    assert _ler(client, cabecalho, pedido)["devolucao"] == {"motivo": "Veio errado"}
    assert _tipos(eventos) == ["devolucao_solicitada"]


def test_devolucao_no_oitavo_dia_responde_409(app, client, cabecalho, usuario_id, relogio):
    _, pedido = _entregue(app, client, cabecalho, usuario_id, relogio)
    relogio.avancar(days=7, minutes=1)

    resposta = _patch(client, cabecalho, pedido, DEVOLVER)

    assert resposta.status_code == 409
    assert resposta.get_json()["erro"] == "O prazo de 7 dias para devolução terminou."
    assert _ler(client, cabecalho, pedido)["status"] == "entregue"


def test_cancelar_pedido_entregue_responde_409_com_status_atual(app, client, cabecalho, usuario_id, relogio,
                                                                eventos):
    _, pedido = _entregue(app, client, cabecalho, usuario_id, relogio)
    _ler(client, cabecalho, pedido)
    eventos.clear()

    resposta = _patch(client, cabecalho, pedido, CANCELAR)

    assert resposta.status_code == 409
    assert "entregue" in resposta.get_json()["erro"]
    assert eventos == []


def test_patch_aplica_transicoes_antes_de_decidir(app, client, cabecalho, usuario_id, relogio, eventos):
    solicitacao, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    relogio.avancar(minutes=30)
    eventos.clear()

    resposta = _patch(client, cabecalho, pedido, CANCELAR)

    assert resposta.status_code == 409
    assert "expirado" in resposta.get_json()["erro"]
    assert _tipos(eventos) == ["pedido_expirado"]
    assert _status_da_solicitacao(app, solicitacao) == "expirada"


@pytest.mark.parametrize("corpo", [CANCELAR, DEVOLVER])
def test_pedido_em_estado_final_nao_muda(app, client, cabecalho, usuario_id, corpo):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    assert _patch(client, cabecalho, pedido, CANCELAR).status_code == 200

    resposta = _patch(client, cabecalho, pedido, corpo)

    assert resposta.status_code == 409
    assert len(_ler(client, cabecalho, pedido)["historico"]) == 2


def test_devolucao_de_pedido_pago_responde_409(app, client, cabecalho, usuario_id):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)
    _pagar(client, cabecalho, pedido)

    assert _patch(client, cabecalho, pedido, DEVOLVER).status_code == 409


@pytest.mark.parametrize("corpo, campo", [
    ({}, "status"),
    ({"status": "pago"}, "status"),
    ({"status": "entregue"}, "status"),
    ({"status": "devolucao_solicitada"}, "motivo"),
    ({"status": "devolucao_solicitada", "motivo": " ab "}, "motivo"),
    ({"status": "devolucao_solicitada", "motivo": "x" * 301}, "motivo"),
    ({"status": "devolucao_solicitada", "motivo": 123}, "motivo"),
])
def test_corpo_invalido_responde_400(app, client, cabecalho, usuario_id, corpo, campo):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    resposta = _patch(client, cabecalho, pedido, corpo)

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["detalhes"]
    assert _ler(client, cabecalho, pedido)["status"] == "aguardando_pagamento"


def test_patch_sem_corpo_json_responde_400(app, client, cabecalho, usuario_id):
    _, pedido = _criar_pedido(app, client, cabecalho, usuario_id)

    assert client.patch(f"/pedidos/{pedido['id']}", headers=cabecalho).status_code == 400


def test_patch_em_pedido_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    solicitacao, pedido = _criar_pedido(app, client, cabecalho_de(outro_id), outro_id)

    assert _patch(client, cabecalho, pedido, CANCELAR).status_code == 404
    assert _status_da_solicitacao(app, solicitacao) == "aprovada"
