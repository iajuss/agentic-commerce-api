"""PATCH /solicitacoes/<id>/itens/<indice>: a pessoa troca a oferta recomendada por uma das alternativas."""

from bson import ObjectId

from tests.test_solicitacoes import catalogo, criar_politica, eventos, sem_ganchos, solicitar  # noqa: F401


def trocar(client, headers, solicitacao_id, indice, id_externo):
    return client.patch(f"/solicitacoes/{solicitacao_id}/itens/{indice}", json={"id_externo": id_externo},
                        headers=headers)


def test_troca_poe_a_alternativa_na_cesta_e_recalcula_o_total(client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json
    assert criada["itens"][0]["recomendada"]["id_externo"] == "A5"

    resposta = trocar(client, auth, criada["id"], 0, "A5B")

    assert resposta.status_code == 200
    item = resposta.json["itens"][0]
    assert item["recomendada"]["id_externo"] == "A5B"
    assert item["sugestao_do_agente"] == "A5"
    assert item["alternativas"][0]["id_externo"] == "A5"
    assert "A5B" not in [oferta["id_externo"] for oferta in item["alternativas"]]
    assert resposta.json["cesta"] == {"subtotal": 24.9, "frete": 9.9, "total": 34.8, "lojas": ["Atacado"]}


def test_troca_fica_gravada_e_da_para_voltar_para_a_sugestao(client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json
    trocar(client, auth, criada["id"], 0, "A5B")

    trocar(client, auth, criada["id"], 0, "A5")
    item = client.get(f"/solicitacoes/{criada['id']}", headers=auth).json["itens"][0]

    assert item["recomendada"]["id_externo"] == "A5"
    assert item["sugestao_do_agente"] == "A5"
    assert len(item["alternativas"]) == len(criada["itens"][0]["alternativas"])


def test_troca_recalcula_as_embalagens_pela_quantidade_pedida(client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json
    assert criada["itens"][0]["quantidade"] == 1

    item = trocar(client, auth, criada["id"], 0, "A1").json["itens"][0]

    assert item["recomendada"]["id_externo"] == "A1"
    assert item["quantidade"] == 5
    assert item["quantidade_pedida"] == 1


def test_troca_reavalia_a_cesta_pelas_politicas(client, auth):
    # A política nasce depois da solicitação: a troca avalia a cesta pelas políticas de agora.
    # O arroz parboilizado custa R$ 24,90, mas com o frete de R$ 9,90 a cesta passa do teto de R$ 30.
    criada = solicitar(client, auth, texto="arroz 5kg").json
    criar_politica(client, auth, teto_por_compra=30)

    corpo = trocar(client, auth, criada["id"], 0, "A5B").json

    assert corpo["avaliacao"]["permitida"] is False
    assert corpo["avaliacao"]["motivos"]
    assert corpo["status"] == "aguardando_aprovacao"


def test_escolher_a_oferta_que_ja_esta_na_cesta_nao_muda_nada(client, auth, eventos):  # noqa: F811
    criada = solicitar(client, auth, texto="arroz 5kg").json

    resposta = trocar(client, auth, criada["id"], 0, "A5")

    assert resposta.status_code == 200
    assert resposta.json["atualizada_em"] == criada["atualizada_em"]
    assert [evento[1] for evento in eventos] == ["solicitacao_criada"]


def test_troca_registra_o_evento_na_auditoria(client, auth, eventos):  # noqa: F811
    criada = solicitar(client, auth, texto="arroz 5kg").json

    trocar(client, auth, criada["id"], 0, "A5B")

    tipo, recurso_tipo, dados = eventos[-1][1], eventos[-1][2], eventos[-1][4]
    assert (tipo, recurso_tipo) == ("oferta_trocada", "solicitacao")
    assert dados == {"item": 0, "de": "A5", "para": "A5B", "total": 34.8}


def test_oferta_fora_das_alternativas_responde_400(client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json

    resposta = trocar(client, auth, criada["id"], 0, "L1")

    assert resposta.status_code == 400
    assert resposta.json["detalhes"] == {"id_externo": "Escolha uma das alternativas deste item."}


def test_corpo_sem_oferta_responde_400(client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json

    resposta = client.patch(f"/solicitacoes/{criada['id']}/itens/0", json={}, headers=auth)

    assert resposta.status_code == 400
    assert resposta.json["detalhes"] == {"id_externo": "Informe a oferta escolhida."}


def test_item_sem_oferta_responde_400(client, auth):
    criada = solicitar(client, auth, ("arroz", 1), ("chocolate", 1)).json
    assert criada["itens"][1]["status"] == "sem_oferta"

    resposta = trocar(client, auth, criada["id"], 1, "A5")

    assert resposta.status_code == 400


def test_indice_inexistente_responde_404(client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json

    for indice in ("1", "-1", "abc"):
        assert trocar(client, auth, criada["id"], indice, "A5B").status_code == 404


def test_solicitacao_de_outra_pessoa_responde_404(client, auth, cabecalho_de):
    criada = solicitar(client, auth, texto="arroz 5kg").json

    resposta = trocar(client, cabecalho_de(ObjectId()), criada["id"], 0, "A5B")

    assert resposta.status_code == 404


def test_solicitacao_aprovada_nao_troca_a_oferta(app, client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json
    app.extensions["mongo"]["solicitacoes"].update_one({"_id": ObjectId(criada["id"])},
                                                       {"$set": {"status": "aprovada"}})

    resposta = trocar(client, auth, criada["id"], 0, "A5B")

    assert resposta.status_code == 409
    assert resposta.json["erro"] == "Só dá para trocar a oferta antes de aprovar a compra."


def test_solicitacao_antiga_sem_os_campos_novos_tambem_troca(app, client, auth):
    criada = solicitar(client, auth, texto="arroz 5kg").json
    app.extensions["mongo"]["solicitacoes"].update_one(
        {"_id": ObjectId(criada["id"])},
        {"$unset": {"itens.0.quantidade_pedida": "", "itens.0.sugestao_do_agente": ""}},
    )

    item = trocar(client, auth, criada["id"], 0, "A5B").json["itens"][0]

    assert item["recomendada"]["id_externo"] == "A5B"
    assert item["sugestao_do_agente"] == "A5"
