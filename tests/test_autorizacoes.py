"""Autorizações: aprovação com senha, listagem, consulta e revogação."""

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


@pytest.fixture
def usuario_id(app):
    return inserir_usuario(app)


@pytest.fixture
def cabecalho(cabecalho_de, usuario_id):
    return cabecalho_de(usuario_id)


def _aprovar(client, cabecalho, solicitacao, senha=SENHA_PADRAO):
    return client.post(f"/solicitacoes/{solicitacao['_id']}/autorizacoes", json={"senha": senha},
                       headers=cabecalho)


def _solicitacao_no_banco(app, solicitacao):
    return app.extensions["mongo"]["solicitacoes"].find_one({"_id": solicitacao["_id"]})


def _autorizacoes_no_banco(app):
    return list(app.extensions["mongo"]["autorizacoes"].find())


# POST /solicitacoes/<id>/autorizacoes

def test_senha_certa_cria_autorizacao_com_location(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)

    resposta = _aprovar(client, cabecalho, solicitacao)

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert resposta.headers["Location"] == f"/autorizacoes/{corpo['id']}"
    assert corpo["status"] == "ativa"
    assert corpo["origem"] == "manual"
    assert corpo["solicitacao_id"] == str(solicitacao["_id"])
    assert corpo["politica_id"] == str(solicitacao["avaliacao"]["politica_id"])


def test_autorizacao_limita_valor_lojas_e_itens_da_cesta(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)

    corpo = _aprovar(client, cabecalho, solicitacao).get_json()

    assert corpo["valor_maximo"] == 33.8
    assert corpo["lojas"] == ["Loja Exemplo"]
    assert corpo["itens"] == [
        {"id_externo": "MLB1001", "titulo": "Arroz Branco Tipo 1 5kg", "preco": 27.9, "loja": "Loja Exemplo",
         "quantidade": 1},
        {"id_externo": "MLB2002", "titulo": "Leite Integral 1L", "preco": 2.95, "loja": "Loja Exemplo",
         "quantidade": 2},
    ]


def test_item_sem_oferta_fica_fora_da_autorizacao(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)
    sem_oferta = {"descricao": "detergente", "quantidade": 1, "status": "sem_oferta", "recomendada": None,
                  "alternativas": [], "descartadas": 0, "explicacao": ["Nenhuma oferta encontrada para este item"]}
    app.extensions["mongo"]["solicitacoes"].update_one({"_id": solicitacao["_id"]},
                                                       {"$push": {"itens": sem_oferta}})

    corpo = _aprovar(client, cabecalho, solicitacao).get_json()

    assert [item["id_externo"] for item in corpo["itens"]] == ["MLB1001", "MLB2002"]


def test_aprovar_muda_a_solicitacao_para_aprovada(app, client, cabecalho, usuario_id, relogio):
    solicitacao = inserir_solicitacao(app, usuario_id)
    relogio.avancar(minutes=1)

    _aprovar(client, cabecalho, solicitacao)

    gravada = _solicitacao_no_banco(app, solicitacao)
    assert gravada["status"] == "aprovada"
    assert gravada["atualizada_em"] == relogio.momento


def test_autorizacao_vence_em_15_minutos_por_padrao(app, client, cabecalho, usuario_id, relogio):
    solicitacao = inserir_solicitacao(app, usuario_id)

    _aprovar(client, cabecalho, solicitacao)

    autorizacao = _autorizacoes_no_banco(app)[0]
    assert autorizacao["expira_em"] == relogio.momento + timedelta(minutes=15)


def test_validade_da_autorizacao_vem_da_configuracao(app, client, cabecalho, usuario_id, relogio):
    app.config["AUTORIZACAO_VALIDADE_MINUTOS"] = "5"
    solicitacao = inserir_solicitacao(app, usuario_id)

    _aprovar(client, cabecalho, solicitacao)

    assert _autorizacoes_no_banco(app)[0]["expira_em"] == relogio.momento + timedelta(minutes=5)


def test_aprovar_emite_evento_com_origem_manual(app, client, cabecalho, usuario_id, eventos):
    solicitacao = inserir_solicitacao(app, usuario_id)

    corpo = _aprovar(client, cabecalho, solicitacao).get_json()

    assert eventos == [{"usuario_id": usuario_id, "tipo": "autorizacao_emitida", "recurso_tipo": "autorizacao",
                        "recurso_id": ObjectId(corpo["id"]), "dados": {"origem": "manual"}}]


def test_senha_errada_responde_401_sem_criar_autorizacao(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)

    resposta = _aprovar(client, cabecalho, solicitacao, senha="senha-errada")

    assert resposta.status_code == 401
    assert resposta.get_json()["erro"] == "Senha incorreta."
    assert _autorizacoes_no_banco(app) == []
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aguardando_aprovacao"


def test_senha_errada_traz_detalhes_senha_para_o_front_manter_a_sessao(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)

    resposta = _aprovar(client, cabecalho, solicitacao, senha="senha-errada")

    assert resposta.get_json() == {"erro": "Senha incorreta.",
                                   "detalhes": {"senha": "Senha incorreta. Confira e tente de novo."}}


def test_senha_errada_emite_reautenticacao_recusada(app, client, cabecalho, usuario_id, eventos):
    solicitacao = inserir_solicitacao(app, usuario_id)

    _aprovar(client, cabecalho, solicitacao, senha="senha-errada")

    assert eventos == [{"usuario_id": usuario_id, "tipo": "reautenticacao_recusada", "recurso_tipo": "solicitacao",
                        "recurso_id": solicitacao["_id"], "dados": None}]


def test_usuario_sem_cadastro_recebe_sessao_invalida_sem_detalhes(app, client, cabecalho_de, eventos):
    sem_cadastro = ObjectId()  # token válido, mas sem documento em usuarios
    solicitacao = inserir_solicitacao(app, sem_cadastro)

    resposta = _aprovar(client, cabecalho_de(sem_cadastro), solicitacao)

    # Sem detalhes.senha o front encerra a sessão, que é o certo para um usuário que não existe mais.
    assert resposta.status_code == 401
    assert resposta.get_json() == {"erro": "Sessão inválida. Faça login novamente."}
    assert eventos == []


@pytest.mark.parametrize("corpo", [{}, {"senha": ""}, {"senha": 123}, {"senha": None}])
def test_senha_ausente_ou_invalida_responde_400(app, client, cabecalho, usuario_id, corpo):
    solicitacao = inserir_solicitacao(app, usuario_id)

    resposta = client.post(f"/solicitacoes/{solicitacao['_id']}/autorizacoes", json=corpo, headers=cabecalho)

    assert resposta.status_code == 400
    assert resposta.get_json()["detalhes"] == {"senha": "Informe a senha."}


def test_corpo_que_nao_e_objeto_responde_400(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)

    resposta = client.post(f"/solicitacoes/{solicitacao['_id']}/autorizacoes", json=["senha"], headers=cabecalho)

    assert resposta.status_code == 400


def test_politica_que_nao_permite_responde_422_com_motivos(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id, permitida=False)

    resposta = _aprovar(client, cabecalho, solicitacao)

    assert resposta.status_code == 422
    assert resposta.get_json() == {"erro": "Nenhuma política permite esta compra.",
                                   "detalhes": {"motivos": solicitacao["avaliacao"]["motivos"]}}
    assert _autorizacoes_no_banco(app) == []
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aguardando_aprovacao"


def test_segunda_aprovacao_responde_409(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)

    _aprovar(client, cabecalho, solicitacao)
    resposta = _aprovar(client, cabecalho, solicitacao)

    assert resposta.status_code == 409
    assert resposta.get_json()["erro"] == "Esta solicitação não está aguardando aprovação."
    assert len(_autorizacoes_no_banco(app)) == 1


@pytest.mark.parametrize("status", ["sem_resultado", "aprovada", "concluida", "expirada"])
def test_solicitacao_fora_de_aprovacao_responde_409(app, client, cabecalho, usuario_id, status):
    solicitacao = inserir_solicitacao(app, usuario_id, status=status)

    resposta = _aprovar(client, cabecalho, solicitacao)

    assert resposta.status_code == 409


def test_status_conferido_antes_da_senha(app, client, cabecalho, usuario_id, eventos):
    solicitacao = inserir_solicitacao(app, usuario_id, status="aprovada")

    resposta = _aprovar(client, cabecalho, solicitacao, senha="senha-errada")

    assert resposta.status_code == 409
    assert eventos == []


def test_solicitacao_de_outro_usuario_responde_404(app, client, cabecalho):
    solicitacao = inserir_solicitacao(app, inserir_usuario(app))

    resposta = _aprovar(client, cabecalho, solicitacao)

    assert resposta.status_code == 404
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aguardando_aprovacao"


@pytest.mark.parametrize("solicitacao_id", [str(ObjectId()), "id-malformado"])
def test_solicitacao_inexistente_responde_404(client, cabecalho, solicitacao_id):
    resposta = client.post(f"/solicitacoes/{solicitacao_id}/autorizacoes", json={"senha": SENHA_PADRAO},
                           headers=cabecalho)

    assert resposta.status_code == 404


# GET /autorizacoes e GET /autorizacoes/<id>

def test_lista_so_as_ativas_mais_recentes_primeiro(app, client, cabecalho, usuario_id, relogio):
    primeira = _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id)).get_json()
    relogio.avancar(minutes=1)
    segunda = _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id)).get_json()
    revogada = _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id)).get_json()
    client.delete(f"/autorizacoes/{revogada['id']}", headers=cabecalho)

    resposta = client.get("/autorizacoes", headers=cabecalho)

    assert resposta.status_code == 200
    assert [autorizacao["id"] for autorizacao in resposta.get_json()] == [segunda["id"], primeira["id"]]


def test_autorizacao_vencida_some_da_lista(app, client, cabecalho, usuario_id, relogio):
    _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id))

    relogio.avancar(minutes=14)
    assert len(client.get("/autorizacoes", headers=cabecalho).get_json()) == 1
    relogio.avancar(minutes=1)
    assert client.get("/autorizacoes", headers=cabecalho).get_json() == []


def test_lista_nao_mostra_autorizacoes_de_outro_usuario(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    _aprovar(client, cabecalho_de(outro_id), inserir_solicitacao(app, outro_id))

    assert client.get("/autorizacoes", headers=cabecalho).get_json() == []


def test_obter_devolve_autorizacao_em_qualquer_status(app, client, cabecalho, usuario_id):
    criada = _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id)).get_json()
    client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    resposta = client.get(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 200
    assert resposta.get_json()["status"] == "revogada"


def test_obter_autorizacao_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    criada = _aprovar(client, cabecalho_de(outro_id), inserir_solicitacao(app, outro_id)).get_json()

    resposta = client.get(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 404
    assert resposta.get_json() == {"erro": "Autorização não encontrada."}


# DELETE /autorizacoes/<id>

def test_revogar_responde_204_e_solicitacao_volta_a_aguardar(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)
    criada = _aprovar(client, cabecalho, solicitacao).get_json()

    resposta = client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 204
    assert resposta.data == b""
    assert _autorizacoes_no_banco(app)[0]["status"] == "revogada"
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aguardando_aprovacao"


def test_revogar_permite_aprovar_de_novo(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)
    criada = _aprovar(client, cabecalho, solicitacao).get_json()
    client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert _aprovar(client, cabecalho, solicitacao).status_code == 201


def test_revogar_emite_evento(app, client, cabecalho, usuario_id, eventos):
    criada = _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id)).get_json()
    eventos.clear()

    client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert eventos == [{"usuario_id": usuario_id, "tipo": "autorizacao_revogada", "recurso_tipo": "autorizacao",
                        "recurso_id": ObjectId(criada["id"]), "dados": None}]


def test_revogar_de_novo_responde_204_sem_novo_evento(app, client, cabecalho, usuario_id, eventos):
    criada = _aprovar(client, cabecalho, inserir_solicitacao(app, usuario_id)).get_json()
    client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)
    eventos.clear()

    resposta = client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 204
    assert eventos == []


def test_revogar_autorizacao_vencida_devolve_a_solicitacao(app, client, cabecalho, usuario_id, relogio):
    solicitacao = inserir_solicitacao(app, usuario_id)
    criada = _aprovar(client, cabecalho, solicitacao).get_json()
    relogio.avancar(minutes=30)

    resposta = client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 204
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aguardando_aprovacao"


def test_revogar_autorizacao_usada_responde_409(app, client, cabecalho, usuario_id):
    solicitacao = inserir_solicitacao(app, usuario_id)
    criada = _aprovar(client, cabecalho, solicitacao).get_json()
    # Os pedidos (M3-03) ainda não existem: marca o uso direto no banco.
    app.extensions["mongo"]["autorizacoes"].update_one({"_id": ObjectId(criada["id"])},
                                                       {"$set": {"status": "usada"}})

    resposta = client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 409
    assert resposta.get_json() == {"erro": "Esta autorização já foi usada em um pedido."}
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aprovada"


def test_revogar_autorizacao_de_outro_usuario_responde_404(app, client, cabecalho, cabecalho_de):
    outro_id = inserir_usuario(app)
    solicitacao = inserir_solicitacao(app, outro_id)
    criada = _aprovar(client, cabecalho_de(outro_id), solicitacao).get_json()

    resposta = client.delete(f"/autorizacoes/{criada['id']}", headers=cabecalho)

    assert resposta.status_code == 404
    assert _autorizacoes_no_banco(app)[0]["status"] == "ativa"
    assert _solicitacao_no_banco(app, solicitacao)["status"] == "aprovada"


def test_revogar_inexistente_responde_404(client, cabecalho):
    assert client.delete(f"/autorizacoes/{ObjectId()}", headers=cabecalho).status_code == 404
