"""Gancho compra_automatica (seção 6.2 do contrato), chamado direto como o M2 chama, sem o código do M2."""

import mongomock
import pytest
from bson import ObjectId

from app import create_app
from app.pagamento.servicos import executar_compra_automatica
from tests.apoio_pagamento import eventos, ganchos_isolados, inserir_solicitacao, inserir_usuario  # noqa: F401


@pytest.fixture
def usuario_id(app):
    return inserir_usuario(app)


def _automatica(app, usuario_id, **campos):
    return inserir_solicitacao(app, usuario_id, compra_automatica=True, **campos)


def _executar(app, solicitacao):
    with app.app_context():
        return executar_compra_automatica(solicitacao)


def _colecao(app, nome):
    return app.extensions["mongo"][nome]


def _status_da_solicitacao(app, solicitacao):
    return _colecao(app, "solicitacoes").find_one({"_id": solicitacao["_id"]})["status"]


def _nada_criado(app, solicitacao, status="aguardando_aprovacao"):
    assert _colecao(app, "autorizacoes").count_documents({}) == 0
    assert _colecao(app, "pedidos").count_documents({}) == 0
    assert _status_da_solicitacao(app, solicitacao) == status


def test_gancho_registrado_na_app():
    config = {"TESTING": True, "JWT_SECRET_KEY": "chave-so-para-testes-com-32-caracteres"}
    app = create_app(config, cliente_mongo=mongomock.MongoClient(tz_aware=True))

    assert app.extensions["compra_automatica"] is executar_compra_automatica


def test_compra_automatica_cria_autorizacao_e_pedido(app, usuario_id):
    solicitacao = _automatica(app, usuario_id)

    resultado = _executar(app, solicitacao)

    assert set(resultado) == {"autorizacao_id", "pedido_id"}
    assert all(isinstance(valor, str) for valor in resultado.values())
    autorizacao = _colecao(app, "autorizacoes").find_one({"_id": ObjectId(resultado["autorizacao_id"])})
    pedido = _colecao(app, "pedidos").find_one({"_id": ObjectId(resultado["pedido_id"])})
    assert autorizacao["origem"] == "automatica"
    assert autorizacao["status"] == "usada"
    assert autorizacao["solicitacao_id"] == solicitacao["_id"]
    assert pedido["status"] == "aguardando_pagamento"
    assert pedido["autorizacao_id"] == autorizacao["_id"]
    assert pedido["total"] == 33.8
    assert pedido["pix"]["copia_e_cola"] == f"PIX-SIMULADO-{pedido['pix']['txid']}"
    assert _status_da_solicitacao(app, solicitacao) == "aprovada"


def test_pedido_automatico_pode_ser_pago(app, client, cabecalho_de, usuario_id):
    solicitacao = _automatica(app, usuario_id)
    pedido = _colecao(app, "pedidos").find_one({"_id": ObjectId(_executar(app, solicitacao)["pedido_id"])})

    resposta = client.post("/simulador-pix/pagamentos", json={"txid": pedido["pix"]["txid"]},
                           headers=cabecalho_de(usuario_id))

    assert resposta.get_json()["status"] == "pago"
    assert _status_da_solicitacao(app, solicitacao) == "concluida"


def test_eventos_da_compra_automatica(app, usuario_id, eventos):
    resultado = _executar(app, _automatica(app, usuario_id))

    assert [(evento["tipo"], evento["dados"]) for evento in eventos] == [
        ("autorizacao_emitida", {"origem": "automatica"}),
        ("pedido_criado", {"total": 33.8}),
    ]
    assert eventos[0]["recurso_id"] == ObjectId(resultado["autorizacao_id"])


def test_solicitacao_manual_devolve_none(app, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id, compra_automatica=False)

    assert _executar(app, solicitacao) is None
    _nada_criado(app, solicitacao)


def test_solicitacao_nao_permitida_devolve_none(app, usuario_id):
    solicitacao = _automatica(app, usuario_id, permitida=False)

    assert _executar(app, solicitacao) is None
    _nada_criado(app, solicitacao)


def test_solicitacao_ja_aprovada_devolve_none(app, usuario_id):
    solicitacao = _automatica(app, usuario_id, status="aprovada")

    assert _executar(app, solicitacao) is None
    _nada_criado(app, solicitacao, status="aprovada")


def test_item_sem_oferta_devolve_none(app, usuario_id):
    solicitacao = _automatica(app, usuario_id)
    sem_oferta = {"descricao": "café", "quantidade": 1, "status": "sem_oferta", "recomendada": None,
                  "alternativas": [], "descartadas": 0}
    solicitacao["itens"].append(sem_oferta)

    assert _executar(app, solicitacao) is None
    _nada_criado(app, solicitacao)


def test_status_mudado_no_banco_depois_da_leitura_devolve_none(app, usuario_id, eventos):
    solicitacao = _automatica(app, usuario_id)
    _colecao(app, "solicitacoes").update_one({"_id": solicitacao["_id"]}, {"$set": {"status": "expirada"}})

    assert _executar(app, solicitacao) is None
    _nada_criado(app, solicitacao, status="expirada")
    assert eventos == []


def test_chamar_duas_vezes_cria_um_pedido_so(app, usuario_id):
    solicitacao = _automatica(app, usuario_id)

    assert _executar(app, solicitacao) is not None
    assert _executar(app, solicitacao) is None
    assert _colecao(app, "autorizacoes").count_documents({}) == 1
    assert _colecao(app, "pedidos").count_documents({}) == 1


def test_falha_ao_consumir_devolve_a_solicitacao_para_aprovacao(app, usuario_id, monkeypatch):
    from app.pagamento import repositorio_autorizacoes

    monkeypatch.setattr(repositorio_autorizacoes, "consumir", lambda *argumentos: None)
    solicitacao = _automatica(app, usuario_id)

    assert _executar(app, solicitacao) is None
    assert _colecao(app, "autorizacoes").find_one()["status"] == "revogada"
    assert _colecao(app, "pedidos").count_documents({}) == 0
    assert _status_da_solicitacao(app, solicitacao) == "aguardando_aprovacao"
