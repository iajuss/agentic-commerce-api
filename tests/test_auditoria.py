"""Trilha de auditoria, gancho e eventos das rotas do M1."""

import mongomock
import pytest
from bson import ObjectId

from app import create_app
from app.auditoria import repositorio
from app.auditoria.registro import registrar_evento

CADASTRO = {"nome": "Ana Silva", "email": "ana@example.com", "senha": "senha-forte-123"}
POLITICA = {"nome": "Mercado", "teto_por_compra": 100}


def test_gancho_e_registrado_em_cada_aplicacao(app):
    outra = create_app(
        {"TESTING": True, "JWT_SECRET_KEY": "chave-de-teste-com-pelo-menos-32-caracteres"},
        cliente_mongo=mongomock.MongoClient(tz_aware=True),
    )

    assert app.extensions["registrar_evento"] is registrar_evento
    assert outra.extensions["registrar_evento"] is registrar_evento


def test_repositorio_expoe_apenas_insercao_e_leitura():
    assert {"atualizar", "remover", "update", "delete"}.isdisjoint(dir(repositorio))


def test_registro_remove_chaves_sensiveis_inclusive_em_dados_aninhados(app):
    usuario_id = ObjectId()
    recurso_id = ObjectId()
    with app.app_context():
        evento = registrar_evento(
            usuario_id,
            "evento_teste",
            "usuario",
            recurso_id,
            {
                "senha": "segredo",
                "senha_hash": "hash",
                "token": "token",
                "copia_e_cola": "pix",
                "origem": "teste",
                "aninhado": {"token": "outro", "valor": 1},
                "lista": [{"senha": "outra", "valor": 2}],
            },
        )

    assert evento["usuario_id"] == usuario_id
    assert evento["recurso"] == {"tipo": "usuario", "id": str(recurso_id)}
    assert evento["dados"] == {
        "origem": "teste",
        "aninhado": {"valor": 1},
        "lista": [{"valor": 2}],
    }
    assert app.extensions["mongo"]["auditoria"].count_documents({}) == 1


def test_listagem_devolve_eventos_recentes_sem_expor_usuario_id(app, client, cabecalho_de):
    usuario_id = ObjectId()
    with app.app_context():
        ids = [registrar_evento(usuario_id, f"evento_{numero}")["_id"] for numero in range(3)]

    resposta = client.get("/auditoria", headers=cabecalho_de(usuario_id))

    assert resposta.status_code == 200
    assert [evento["id"] for evento in resposta.json["eventos"]] == [str(id_) for id_ in reversed(ids)]
    assert resposta.json["proximo"] is None
    assert all("usuario_id" not in evento and "criado_em" in evento for evento in resposta.json["eventos"])


def test_listagem_isola_eventos_por_usuario(app, client, cabecalho_de):
    primeiro = ObjectId()
    segundo = ObjectId()
    with app.app_context():
        registrar_evento(primeiro, "do_primeiro")
        registrar_evento(segundo, "do_segundo")

    resposta = client.get("/auditoria", headers=cabecalho_de(primeiro))

    assert resposta.status_code == 200
    assert [evento["tipo"] for evento in resposta.json["eventos"]] == ["do_primeiro"]


def test_paginacao_usa_o_ultimo_id_da_pagina(app, client, cabecalho_de):
    usuario_id = ObjectId()
    with app.app_context():
        ids = [registrar_evento(usuario_id, f"evento_{numero}")["_id"] for numero in range(3)]
    cabecalho = cabecalho_de(usuario_id)

    primeira = client.get("/auditoria?limite=2", headers=cabecalho)
    segunda = client.get(f"/auditoria?limite=2&antes_de={primeira.json['proximo']}", headers=cabecalho)

    assert primeira.status_code == 200
    assert [evento["id"] for evento in primeira.json["eventos"]] == [str(ids[2]), str(ids[1])]
    assert primeira.json["proximo"] == str(ids[1])
    assert segunda.status_code == 200
    assert [evento["id"] for evento in segunda.json["eventos"]] == [str(ids[0])]
    assert segunda.json["proximo"] is None


@pytest.mark.parametrize(
    ("consulta", "campo"),
    [
        ("limite=0", "limite"),
        ("limite=101", "limite"),
        ("limite=abc", "limite"),
        ("antes_de=invalido", "antes_de"),
        ("antes_de=", "antes_de"),
    ],
)
def test_parametros_invalidos_respondem_400(client, cabecalho_de, consulta, campo):
    resposta = client.get(f"/auditoria?{consulta}", headers=cabecalho_de(ObjectId()))

    assert resposta.status_code == 400
    assert campo in resposta.json["detalhes"]


def test_auditoria_exige_token(client):
    assert client.get("/auditoria").status_code == 401


def test_cadastro_e_login_geram_eventos_sem_registrar_email_inexistente(app, client):
    cadastro = client.post("/usuarios", json=CADASTRO)
    assert cadastro.status_code == 201
    usuario_id = ObjectId(cadastro.json["id"])

    login = client.post("/sessoes", json={"email": CADASTRO["email"], "senha": CADASTRO["senha"]})
    recusado = client.post("/sessoes", json={"email": CADASTRO["email"], "senha": "incorreta"})
    desconhecido = client.post("/sessoes", json={"email": "outra@example.com", "senha": "incorreta"})

    assert login.status_code == 200
    assert recusado.status_code == 401
    assert desconhecido.status_code == 401
    eventos = app.extensions["mongo"]["auditoria"].find({"usuario_id": usuario_id}).sort("_id", 1)
    assert [evento["tipo"] for evento in eventos] == [
        "usuario_cadastrado",
        "sessao_iniciada",
        "login_recusado",
    ]


def test_operacoes_de_politica_geram_eventos(app, client, cabecalho_de):
    usuario_id = ObjectId()
    cabecalho = cabecalho_de(usuario_id)

    criada = client.post("/politicas", json=POLITICA, headers=cabecalho)
    assert criada.status_code == 201
    politica_id = criada.json["id"]

    substituida = client.put(
        f"/politicas/{politica_id}",
        json={**POLITICA, "nome": "Novo mercado"},
        headers=cabecalho,
    )
    removida = client.delete(f"/politicas/{politica_id}", headers=cabecalho)

    assert substituida.status_code == 200
    assert removida.status_code == 204
    resposta = client.get("/auditoria", headers=cabecalho)
    assert [evento["tipo"] for evento in resposta.json["eventos"]] == [
        "politica_removida",
        "politica_substituida",
        "politica_criada",
    ]
    assert all(evento["recurso"]["id"] == politica_id for evento in resposta.json["eventos"])
