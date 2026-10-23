"""CRUD de /politicas."""

import pytest
from bson import ObjectId

POLITICA = {
    "nome": "Eletrônicos do dia a dia",
    "teto_por_compra": 500,
    "categorias": ["Smartphones", " laptops "],
    "lojas": [],
    "nivel_autonomia": "automatica",
}


def criar(client, auth, corpo=POLITICA):
    return client.post("/politicas", json=corpo, headers=auth)


def test_criar_responde_201_com_location(client, auth):
    resposta = criar(client, auth)

    assert resposta.status_code == 201
    assert resposta.headers["Location"] == f"/politicas/{resposta.json['id']}"
    assert resposta.json["categorias"] == ["smartphones", "laptops"]
    assert resposta.json["teto_por_compra"] == 500.0
    assert resposta.json["ativa"] is True


def test_criar_usa_autonomia_manual_por_padrao(client, auth):
    corpo = {"nome": "Mínima", "teto_por_compra": 50}

    resposta = criar(client, auth, corpo)

    assert resposta.status_code == 201
    assert resposta.json["nivel_autonomia"] == "manual"


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("nome", ""),
        ("teto_por_compra", 0),
        ("teto_por_compra", "100"),
        ("teto_por_compra", True),
        ("categorias", "smartphones"),
        ("lojas", [1, 2]),
        ("nivel_autonomia", "total"),
        ("ativa", "sim"),
    ],
)
def test_criar_com_campo_invalido_responde_400(client, auth, campo, valor):
    resposta = criar(client, auth, {**POLITICA, campo: valor})

    assert resposta.status_code == 400
    assert campo in resposta.json["detalhes"]


def test_criar_sem_json_responde_400(client, auth):
    resposta = client.post("/politicas", data="texto", headers=auth)

    assert resposta.status_code == 400


def test_rotas_exigem_login(client):
    resposta = client.get("/politicas")

    assert resposta.status_code == 401
    assert resposta.json == {"erro": "Faça login para continuar."}


def test_listar_mostra_so_as_politicas_do_usuario(client, cabecalho_de):
    ana, beto = cabecalho_de(ObjectId()), cabecalho_de(ObjectId())
    criar(client, ana)
    criar(client, beto)

    resposta = client.get("/politicas", headers=ana)

    assert resposta.status_code == 200
    assert len(resposta.json) == 1


def test_obter_politica(client, auth):
    politica_id = criar(client, auth).json["id"]

    resposta = client.get(f"/politicas/{politica_id}", headers=auth)

    assert resposta.status_code == 200
    assert resposta.json["nome"] == POLITICA["nome"]


def test_politica_de_outro_usuario_responde_404(client, cabecalho_de):
    politica_id = criar(client, cabecalho_de(ObjectId())).json["id"]

    resposta = client.get(f"/politicas/{politica_id}", headers=cabecalho_de(ObjectId()))

    assert resposta.status_code == 404


@pytest.mark.parametrize("politica_id", ["abc", str(ObjectId())])
def test_id_malformado_ou_inexistente_responde_404(client, auth, politica_id):
    assert client.get(f"/politicas/{politica_id}", headers=auth).status_code == 404


def test_substituir_politica(client, auth):
    politica_id = criar(client, auth).json["id"]
    nova = {"nome": "Só livros", "teto_por_compra": 80, "categorias": ["books"]}

    resposta = client.put(f"/politicas/{politica_id}", json=nova, headers=auth)

    assert resposta.status_code == 200
    assert resposta.json["categorias"] == ["books"]
    assert resposta.json["nivel_autonomia"] == "manual"


def test_substituir_inexistente_responde_404(client, auth):
    resposta = client.put(f"/politicas/{ObjectId()}", json=POLITICA, headers=auth)

    assert resposta.status_code == 404


def test_substituir_com_corpo_invalido_responde_400(client, auth):
    politica_id = criar(client, auth).json["id"]

    resposta = client.put(f"/politicas/{politica_id}", json={"nome": "Sem teto"}, headers=auth)

    assert resposta.status_code == 400


def test_remover_politica(client, auth):
    politica_id = criar(client, auth).json["id"]

    resposta = client.delete(f"/politicas/{politica_id}", headers=auth)

    assert resposta.status_code == 204
    assert client.get(f"/politicas/{politica_id}", headers=auth).status_code == 404


def test_remover_inexistente_responde_404(client, auth):
    assert client.delete(f"/politicas/{ObjectId()}", headers=auth).status_code == 404
