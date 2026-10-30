"""Perfil autenticado e consulta ao ViaCEP com respostas simuladas."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from bson import ObjectId

from app.autenticacao import viacep

CADASTRO = {"nome": "Ana Silva", "email": "ana@example.com", "senha": "senha-forte-123"}


class RespostaFalsa:
    def __init__(self, dados, status=200):
        self.dados = dados
        self.status_code = status

    def json(self):
        return self.dados


def carregar_fixture(nome):
    caminho = Path(__file__).parent / "fixtures" / nome
    return json.loads(caminho.read_text(encoding="utf-8"))


def simular_viacep(monkeypatch, dados, status=200):
    monkeypatch.setattr(viacep.requests, "get", lambda url, timeout: RespostaFalsa(dados, status))


def proibir_viacep(monkeypatch):
    def get_proibido(*args, **kwargs):
        pytest.fail("ViaCEP não deveria ser chamado")

    monkeypatch.setattr(viacep.requests, "get", get_proibido)

@pytest.fixture
def conta(client):
    cadastro = client.post("/usuarios", json=CADASTRO)
    assert cadastro.status_code == 201
    login = client.post("/sessoes", json={"email": CADASTRO["email"], "senha": CADASTRO["senha"]})
    assert login.status_code == 200
    return {
        "id": cadastro.json["id"],
        "cadastro": cadastro,
        "cabecalho": {"Authorization": f"Bearer {login.json['token']}"},
    }


def test_perfil_de_usuario_recente_tem_campos_vazios(client, conta):
    resposta = client.get("/usuarios/me", headers=conta["cabecalho"])

    assert resposta.status_code == 200
    assert set(resposta.json) == {
        "id", "nome", "email", "data_nascimento", "endereco",
        "preferencias", "orcamento_mensal", "criado_em",
    }
    assert resposta.json["id"] == conta["id"]
    assert resposta.json["data_nascimento"] is None
    assert resposta.json["endereco"] is None
    assert resposta.json["orcamento_mensal"] is None
    assert resposta.json["preferencias"] == {"marcas_preferidas": [], "marcas_evitadas": []}
    assert "senha_hash" not in resposta.json


def test_location_do_cadastro_abre_perfil_com_token(client, conta):
    resposta = client.get(conta["cadastro"].headers["Location"], headers=conta["cabecalho"])

    assert resposta.status_code == 200
    assert resposta.json["id"] == conta["id"]


def test_patch_de_endereco_completa_cidade_pelo_viacep(app, client, conta, monkeypatch):
    chamadas = []
    app.config["HTTP_TIMEOUT_SEGUNDOS"] = 3

    def get_falso(url, timeout):
        chamadas.append((url, timeout))
        return RespostaFalsa(carregar_fixture("viacep_valido.json"))

    monkeypatch.setattr(viacep.requests, "get", get_falso)
    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "01001-000", "numero": " 10 ", "complemento": " Apto 2 "}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 200
    assert chamadas == [("https://viacep.com.br/ws/01001000/json/", 3)]
    assert resposta.json["endereco"] == {
        "cep": "01001000",
        "logradouro": "Praça da Sé",
        "bairro": "Sé",
        "cidade": "São Paulo",
        "uf": "SP",
        "numero": "10",
        "complemento": "Apto 2",
    }
    usuario = app.extensions["mongo"]["usuarios"].find_one({"_id": ObjectId(conta["id"])})
    assert usuario["endereco"]["cidade"] == "São Paulo"
    assert "atualizado_em" in usuario


def test_patch_somente_nome_preserva_endereco(client, conta, monkeypatch):
    simular_viacep(monkeypatch, carregar_fixture("viacep_valido.json"))
    inicial = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "01001000", "numero": "10"}},
        headers=conta["cabecalho"],
    )
    assert inicial.status_code == 200
    proibir_viacep(monkeypatch)

    resposta = client.patch("/usuarios/me", json={"nome": " Ana Nova "}, headers=conta["cabecalho"])

    assert resposta.status_code == 200
    assert resposta.json["nome"] == "Ana Nova"
    assert resposta.json["endereco"] == inicial.json["endereco"]


def test_patch_somente_numero_preserva_dados_do_cep(client, conta, monkeypatch):
    simular_viacep(monkeypatch, carregar_fixture("viacep_valido.json"))
    inicial = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "01001000", "numero": "10"}},
        headers=conta["cabecalho"],
    )
    assert inicial.status_code == 200
    proibir_viacep(monkeypatch)

    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"numero": "20"}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 200
    assert resposta.json["endereco"] == {**inicial.json["endereco"], "numero": "20"}


@pytest.mark.parametrize("erro", [carregar_fixture("viacep_inexistente.json"), {"erro": True}])
def test_cep_inexistente_responde_400_sem_atualizar(client, conta, monkeypatch, erro, app):
    simular_viacep(monkeypatch, erro)

    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "00000000", "numero": "1"}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 400
    assert resposta.json == {"erro": "CEP não encontrado.", "detalhes": {"cep": "Confira o CEP."}}
    usuario = app.extensions["mongo"]["usuarios"].find_one({"_id": ObjectId(conta["id"])})
    assert "endereco" not in usuario
    assert app.extensions["mongo"]["auditoria"].count_documents({"tipo": "perfil_atualizado"}) == 0


def test_cep_malformado_e_rejeitado_sem_chamar_viacep(client, conta, monkeypatch):
    proibir_viacep(monkeypatch)

    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "123", "numero": "1"}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 400
    assert resposta.json["erro"] == "Perfil inválido."
    assert "endereco.cep" in resposta.json["detalhes"]


def test_viacep_responde_400_para_cep_invalido(client, conta, monkeypatch):
    simular_viacep(monkeypatch, {}, status=400)

    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "00000000"}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 400
    assert resposta.json["erro"] == "CEP não encontrado."


@pytest.mark.parametrize("falha", [requests.Timeout("lento"), requests.ConnectionError("sem rede")])
def test_falha_de_rede_do_viacep_responde_502(client, conta, monkeypatch, falha):
    def get_falso(url, timeout):
        raise falha

    monkeypatch.setattr(viacep.requests, "get", get_falso)
    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "01001000"}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 502
    assert resposta.json["erro"] == "Serviço de CEP indisponível no momento. Tente novamente em instantes."


def test_viacep_5xx_responde_502(client, conta, monkeypatch):
    simular_viacep(monkeypatch, {}, status=500)

    resposta = client.patch(
        "/usuarios/me",
        json={"endereco": {"cep": "01001000"}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 502


def test_data_de_nascimento_futura_responde_400(client, conta):
    futura = (date.today() + timedelta(days=1)).isoformat()

    resposta = client.patch(
        "/usuarios/me",
        json={"data_nascimento": futura},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 400
    assert "data_nascimento" in resposta.json["detalhes"]


def test_preferencias_e_orcamento_sao_normalizados_e_atualizados_em_parte(client, conta):
    primeira = client.patch(
        "/usuarios/me",
        json={
            "preferencias": {
                "marcas_preferidas": [" Nestlé ", "NESTLÉ", " "],
                "marcas_evitadas": ["Marca X"],
            },
            "orcamento_mensal": 150.123,
        },
        headers=conta["cabecalho"],
    )
    segunda = client.patch(
        "/usuarios/me",
        json={"preferencias": {"marcas_preferidas": ["Outra"]}, "orcamento_mensal": None},
        headers=conta["cabecalho"],
    )

    assert primeira.status_code == 200
    assert primeira.json["preferencias"] == {
        "marcas_preferidas": ["nestlé"], "marcas_evitadas": ["marca x"],
    }
    assert primeira.json["orcamento_mensal"] == 150.12
    assert segunda.status_code == 200
    assert segunda.json["preferencias"] == {
        "marcas_preferidas": ["outra"], "marcas_evitadas": ["marca x"],
    }
    assert segunda.json["orcamento_mensal"] is None


def test_campos_invalidos_retorna_todos_os_detalhes(client, conta):
    resposta = client.patch(
        "/usuarios/me",
        json={
            "nome": " ",
            "endereco": {"numero": ""},
            "preferencias": {"marcas_evitadas": "texto"},
            "orcamento_mensal": True,
        },
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 400
    assert resposta.json["erro"] == "Perfil inválido."
    assert set(resposta.json["detalhes"]) == {
        "nome", "endereco.numero", "preferencias.marcas_evitadas", "orcamento_mensal",
    }


def test_orcamento_excessivo_retorna_400_sem_alterar_perfil(client, conta):
    resposta = client.patch(
        "/usuarios/me",
        json={"orcamento_mensal": 10**400},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 400
    assert resposta.json == {
        "erro": "Perfil inválido.",
        "detalhes": {"orcamento_mensal": "Informe um valor maior que zero ou null."},
    }
    perfil = client.get("/usuarios/me", headers=conta["cabecalho"])
    assert perfil.json["orcamento_mensal"] is None


def test_perfil_e_sempre_do_usuario_do_token(client, conta):
    outro = client.post(
        "/usuarios",
        json={"nome": "Bruna", "email": "bruna@example.com", "senha": "senha-forte-456"},
    )
    assert outro.status_code == 201

    resposta = client.patch(
        "/usuarios/me",
        json={"nome": "Ana Atualizada"},
        headers=conta["cabecalho"],
    )
    assert resposta.status_code == 200
    assert resposta.json["id"] == conta["id"]
    assert resposta.json["id"] != outro.json["id"]


def test_token_de_usuario_inexistente_responde_401(client, cabecalho_de):
    cabecalho = cabecalho_de(ObjectId())

    assert client.get("/usuarios/me", headers=cabecalho).status_code == 401
    assert client.patch("/usuarios/me", json={"nome": "Alguém"}, headers=cabecalho).status_code == 401


def test_perfil_atualizado_fica_na_auditoria_real(app, client, conta):
    resposta = client.patch(
        "/usuarios/me",
        json={"nome": "Ana Nova", "orcamento_mensal": 120},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 200
    evento = app.extensions["mongo"]["auditoria"].find_one({"tipo": "perfil_atualizado"})
    assert evento["usuario_id"] == ObjectId(conta["id"])
    assert evento["recurso"] == {"tipo": "usuario", "id": conta["id"]}
    assert evento["dados"] == {"campos": ["nome", "orcamento_mensal"]}


def test_data_de_nascimento_passada_e_aceita(client, conta):
    passada = (date.today() - timedelta(days=1)).isoformat()

    resposta = client.patch(
        "/usuarios/me",
        json={"data_nascimento": passada},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 200
    assert resposta.json["data_nascimento"] == passada


def test_campos_desconhecidos_sao_ignorados_sem_gravar(app, client, conta):
    resposta = client.patch(
        "/usuarios/me",
        json={"apelido": "Aninha", "preferencias": {"desconhecida": ["x"]}},
        headers=conta["cabecalho"],
    )

    assert resposta.status_code == 200
    usuario = app.extensions["mongo"]["usuarios"].find_one({"_id": ObjectId(conta["id"])})
    assert "apelido" not in usuario
    assert "preferencias" not in usuario
    assert "atualizado_em" not in usuario
    assert app.extensions["mongo"]["auditoria"].count_documents({"tipo": "perfil_atualizado"}) == 0
