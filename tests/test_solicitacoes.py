"""Rotas de /solicitacoes com catálogo e ganchos falsos (o M2 é testado sem M1 e M3)."""

import pytest
from bson import ObjectId

from app.erros import ErroApi
from app.solicitacoes.catalogo.fixo import CatalogoFixo
from app.solicitacoes.repositorio import COMPRA_AUTOMATICA_FALHOU


def oferta(id_externo, titulo, preco, categoria, caminho, loja="Mercado Exemplo", **campos):
    padrao = {"id_externo": id_externo, "fonte": "teste", "titulo": titulo, "preco": preco, "categoria": categoria,
              "categorias_caminho": caminho, "loja": loja, "frete": 0.0, "frete_gratis": True, "prazo_dias": 2,
              "avaliacao": 4.5}
    return {**padrao, **campos}


MERCEARIA = ["Alimentos e Bebidas", "Mercearia"]
OFERTAS = [
    oferta("A5", "Arroz Branco 5kg", 27.90, "Arroz", MERCEARIA + ["Arroz"]),
    oferta("A1", "Arroz Branco 1kg", 6.49, "Arroz", MERCEARIA + ["Arroz"]),
    oferta("A5B", "Arroz Parboilizado 5kg", 24.90, "Arroz", MERCEARIA + ["Arroz"], loja="Atacado",
           frete=9.90, frete_gratis=False),
    oferta("L1", "Leite Integral 1L", 5.29, "Leite", ["Alimentos e Bebidas", "Laticínios", "Leite"]),
    oferta("F1", "Feijão Carioca 1kg", 8.99, "Feijão", MERCEARIA + ["Feijão"], loja="Atacado",
           frete=9.90, frete_gratis=False),
    oferta("C1", "Cerveja Pilsen Lata 350ml", 3.49, "Cervejas",
           ["Alimentos e Bebidas", "Bebidas", "Bebidas Alcoólicas", "Cervejas"]),
    oferta("D1", "Detergente Neutro 500ml", 2.49, "Detergente", ["Casa e Limpeza", "Detergente"],
           loja="Super Econômico", frete=None, frete_gratis=False),
]


@pytest.fixture(autouse=True)
def catalogo(app):
    falso = CatalogoFixo(OFERTAS)
    app.extensions["catalogo"] = falso
    return falso


@pytest.fixture(autouse=True)
def sem_ganchos(app):
    """Os testes do M2 não dependem dos ganchos reais do M1 e do M3: quem precisa coloca um falso."""
    app.extensions.pop("registrar_evento", None)
    app.extensions.pop("compra_automatica", None)


@pytest.fixture
def eventos(app):
    registrados = []
    app.extensions["registrar_evento"] = lambda *argumentos: registrados.append(argumentos)
    return registrados


@pytest.fixture
def usuario(app, cabecalho_de):
    """Usuário com perfil gravado direto no banco, como o M1 grava (contrato, seção 3)."""

    def criar(**perfil):
        usuario_id = ObjectId()
        app.extensions["mongo"]["usuarios"].insert_one({"_id": usuario_id, "nome": "Ana", **perfil})
        return usuario_id, cabecalho_de(usuario_id)

    return criar


def solicitar(client, headers, *itens, **corpo):
    if itens:
        corpo["itens"] = [{"descricao": descricao, "quantidade": quantidade} for descricao, quantidade in itens]
    return client.post("/solicitacoes", json=corpo, headers=headers)


def criar_politica(client, headers, **campos):
    corpo = {"nome": "Mercado", "teto_por_compra": 500, **campos}
    assert client.post("/politicas", json=corpo, headers=headers).status_code == 201


def test_criar_responde_201_com_location_e_a_cesta(client, auth):
    resposta = solicitar(client, auth, texto="arroz 5kg, 2 leites")

    assert resposta.status_code == 201
    assert resposta.headers["Location"] == f"/solicitacoes/{resposta.json['id']}"
    assert resposta.json["status"] == "aguardando_aprovacao"
    arroz, leite = resposta.json["itens"]
    assert arroz["recomendada"]["id_externo"] == "A5"
    assert "Embalagem igual à pedida (5 kg)" in arroz["recomendada"]["explicacao"]
    assert leite["quantidade"] == 2
    assert resposta.json["cesta"] == {"subtotal": 38.48, "frete": 0.0, "total": 38.48, "lojas": ["Mercado Exemplo"]}


def test_documento_tem_os_campos_que_o_m3_usa(client, auth):
    corpo = solicitar(client, auth, ("arroz", 1)).json

    assert {"id", "usuario_id", "status", "itens", "cesta", "avaliacao", "compra_automatica"} <= set(corpo)
    item = corpo["itens"][0]
    assert {"quantidade", "status", "recomendada", "alternativas", "descartadas", "explicacao"} <= set(item)
    assert {"id_externo", "titulo", "preco", "frete", "loja"} <= set(item["recomendada"])
    assert {"total", "lojas"} <= set(corpo["cesta"])
    assert set(corpo["avaliacao"]) == {"permitida", "compra_automatica", "politica_id", "motivos"}


def test_texto_e_itens_equivalentes_geram_a_mesma_cesta(client, auth):
    por_texto = solicitar(client, auth, texto="2 arroz 1kg e leite").json
    por_itens = solicitar(client, auth, ("arroz 1kg", 2), ("leite", 1)).json

    assert por_texto["cesta"] == por_itens["cesta"]


def test_texto_com_embalagens_e_medidas_encontra_as_ofertas(client, auth):
    corpo = solicitar(client, auth, texto="duas caixas de leite, 2 kg de feijão e três pacotes de arroz").json

    assert [item["status"] for item in corpo["itens"]] == ["com_oferta"] * 3


def test_nenhum_item_com_oferta_gera_sem_resultado(client, auth):
    resposta = solicitar(client, auth, ("chocolate", 1))

    assert resposta.status_code == 201
    assert resposta.json["status"] == "sem_resultado"
    assert resposta.json["itens"][0]["status"] == "sem_oferta"
    assert resposta.json["itens"][0]["explicacao"] == ["Nenhuma oferta encontrada para este item"]
    assert resposta.json["cesta"]["total"] == 0


def test_item_sem_oferta_fica_fora_da_cesta(client, auth):
    corpo = solicitar(client, auth, ("leite", 1), ("chocolate", 1)).json

    assert corpo["status"] == "aguardando_aprovacao"
    assert corpo["cesta"]["subtotal"] == 5.29


def test_oferta_recusada_pela_politica_e_descartada_com_motivo(client, auth):
    criar_politica(client, auth, lojas=["atacado"])

    item = solicitar(client, auth, ("arroz", 1)).json["itens"][0]

    assert item["recomendada"]["id_externo"] == "A5B"
    assert item["descartadas"] == 2
    assert "2 descartadas: Mercado: loja 'Mercado Exemplo' não permitida" in item["explicacao"]


def test_menor_de_idade_ou_sem_data_nao_recebe_bebida_alcoolica(client, auth, usuario):
    _, menor = usuario(data_nascimento="2015-05-10")

    for headers in (auth, menor):
        item = solicitar(client, headers, ("cerveja", 6)).json["itens"][0]
        assert item["status"] == "sem_oferta"
        assert any("maiores de 18" in frase for frase in item["explicacao"])


def test_maior_de_idade_recebe_bebida_alcoolica(client, usuario):
    _, adulto = usuario(data_nascimento="1990-01-01")

    item = solicitar(client, adulto, ("cerveja", 6)).json["itens"][0]

    assert item["status"] == "com_oferta"
    assert item["recomendada"]["id_externo"] == "C1"


def test_teto_da_cesta_estourado_deixa_a_cesta_nao_permitida(client, auth):
    criar_politica(client, auth, teto_por_compra=10)

    corpo = solicitar(client, auth, ("arroz 1kg", 1), ("leite", 1)).json

    assert corpo["avaliacao"]["permitida"] is False
    assert corpo["avaliacao"]["motivos"] == ["Mercado: total de R$ 11,78 passa do teto de R$ 10,00"]


def test_frete_estimado_quando_a_loja_nao_informa(client, auth):
    assert solicitar(client, auth, ("detergente", 1)).json["cesta"]["frete"] == 15.0


def test_frete_cobrado_uma_vez_por_loja(client, auth):
    criar_politica(client, auth, lojas=["atacado"])

    cesta = solicitar(client, auth, ("arroz", 1), ("feijão", 1)).json["cesta"]

    assert cesta == {"subtotal": 33.89, "frete": 9.9, "total": 43.79, "lojas": ["Atacado"]}


def test_catalogo_fora_do_ar_responde_502_e_nao_grava(app, client, auth):
    class CatalogoForaDoAr:
        def buscar(self, termo, limite=10):
            raise ErroApi(502, "Catálogo indisponível no momento. Tente novamente em instantes.")

    app.extensions["catalogo"] = CatalogoForaDoAr()

    resposta = solicitar(client, auth, ("arroz", 1))

    assert resposta.status_code == 502
    assert app.extensions["mongo"]["solicitacoes"].count_documents({}) == 0


def test_falha_parcial_do_catalogo_deixa_o_item_sem_oferta(app, client, auth, catalogo):
    class CatalogoInstavel:
        def buscar(self, termo, limite=10):
            if termo == "feijão":
                raise ErroApi(502, "Catálogo indisponível no momento. Tente novamente em instantes.")
            return catalogo.buscar(termo, limite)

    app.extensions["catalogo"] = CatalogoInstavel()

    corpo = solicitar(client, auth, ("arroz", 1), ("feijão", 1)).json

    assert corpo["itens"][1]["status"] == "sem_oferta"
    assert corpo["itens"][1]["explicacao"] == ["Catálogo indisponível para este item"]


@pytest.mark.parametrize("corpo", [
    {},
    {"texto": "ab"},
    {"texto": ", ; e"},
    {"texto": 123},
    {"texto": "arroz", "itens": [{"descricao": "arroz", "quantidade": 1}]},
    {"itens": []},
    {"itens": "arroz"},
    {"itens": [{"descricao": "", "quantidade": 1}]},
    {"itens": [{"descricao": "arroz", "quantidade": 0}]},
    {"itens": [{"descricao": "arroz", "quantidade": True}]},
    {"itens": [{"descricao": "arroz", "quantidade": 100}]},
    {"itens": ["arroz"]},
    {"itens": [{"descricao": f"item {numero}", "quantidade": 1} for numero in range(21)]},
    {"texto": ", ".join(f"item {numero}" for numero in range(21))},
])
def test_corpo_invalido_responde_400(client, auth, corpo):
    resposta = client.post("/solicitacoes", json=corpo, headers=auth)

    assert resposta.status_code == 400
    assert resposta.json["erro"] == "Solicitação inválida."
    assert resposta.json["detalhes"]


def test_quantidade_padrao_e_1(client, auth):
    resposta = client.post("/solicitacoes", json={"itens": [{"descricao": "leite"}]}, headers=auth)

    assert resposta.json["itens"][0]["quantidade"] == 1


def test_listar_mostra_o_resumo_do_mais_recente_para_o_mais_antigo(client, cabecalho_de):
    ana, beto = cabecalho_de(ObjectId()), cabecalho_de(ObjectId())
    solicitar(client, ana, ("arroz", 1))
    solicitar(client, ana, ("leite", 2))
    solicitar(client, beto, ("feijão", 1))

    resposta = client.get("/solicitacoes", headers=ana)

    assert resposta.status_code == 200
    assert [resumo["itens"] for resumo in resposta.json] == [["leite"], ["arroz"]]
    assert set(resposta.json[0]) == {"id", "texto", "itens", "status", "total", "criada_em"}


def test_obter_solicitacao(client, auth):
    criada = solicitar(client, auth, ("arroz", 1)).json

    resposta = client.get(f"/solicitacoes/{criada['id']}", headers=auth)

    assert resposta.status_code == 200
    assert resposta.json == criada


@pytest.mark.parametrize("solicitacao_id", ["abc", str(ObjectId())])
def test_id_malformado_ou_inexistente_responde_404(client, auth, solicitacao_id):
    assert client.get(f"/solicitacoes/{solicitacao_id}", headers=auth).status_code == 404


def test_solicitacao_de_outro_usuario_responde_404(client, cabecalho_de):
    criada = solicitar(client, cabecalho_de(ObjectId()), ("arroz", 1)).json
    outro = cabecalho_de(ObjectId())

    assert client.get(f"/solicitacoes/{criada['id']}", headers=outro).status_code == 404
    assert client.delete(f"/solicitacoes/{criada['id']}", headers=outro).status_code == 404


def test_cancelar_responde_204_e_depois_404(client, auth, eventos):
    criada = solicitar(client, auth, ("arroz", 1)).json

    resposta = client.delete(f"/solicitacoes/{criada['id']}", headers=auth)

    assert resposta.status_code == 204
    assert client.get(f"/solicitacoes/{criada['id']}", headers=auth).status_code == 404
    assert eventos[-1][1:3] == ("solicitacao_cancelada", "solicitacao")


def test_cancelar_solicitacao_aprovada_responde_409(app, client, auth):
    criada = solicitar(client, auth, ("arroz", 1)).json
    app.extensions["mongo"]["solicitacoes"].update_one({"_id": ObjectId(criada["id"])},
                                                       {"$set": {"status": "aprovada"}})

    resposta = client.delete(f"/solicitacoes/{criada['id']}", headers=auth)

    assert resposta.status_code == 409
    assert resposta.json["erro"] == "Esta solicitação já foi aprovada e não pode ser cancelada."


def test_criar_registra_evento_de_auditoria(client, auth, eventos):
    criada = solicitar(client, auth, ("arroz", 1)).json

    (evento,) = eventos
    assert evento[1:4] == ("solicitacao_criada", "solicitacao", ObjectId(criada["id"]))
    assert evento[4] == {"itens": 1, "status": "aguardando_aprovacao"}


def test_funciona_sem_os_ganchos_do_m1_e_do_m3(client, auth):
    assert solicitar(client, auth, ("arroz", 1)).status_code == 201


def test_politica_automatica_chama_o_gancho_e_grava_o_resultado(app, client, auth):
    recebidas = []

    def comprar_sozinho(solicitacao):
        recebidas.append(solicitacao)
        app.extensions["mongo"]["solicitacoes"].update_one({"_id": solicitacao["_id"]},
                                                           {"$set": {"status": "aprovada"}})
        return {"autorizacao_id": "aut-1", "pedido_id": "ped-1"}

    app.extensions["compra_automatica"] = comprar_sozinho
    criar_politica(client, auth, nivel_autonomia="automatica")

    corpo = solicitar(client, auth, ("arroz", 1)).json

    (recebida,) = recebidas
    assert recebida["status"] == "aguardando_aprovacao"
    assert recebida["avaliacao"]["compra_automatica"] is True
    assert corpo["status"] == "aprovada"
    assert corpo["compra_automatica"] == {"autorizacao_id": "aut-1", "pedido_id": "ped-1"}


def test_sem_o_gancho_a_solicitacao_automatica_aguarda_aprovacao(client, auth):
    criar_politica(client, auth, nivel_autonomia="automatica")

    corpo = solicitar(client, auth, ("arroz", 1)).json

    assert corpo["status"] == "aguardando_aprovacao"
    assert corpo["avaliacao"]["compra_automatica"] is True
    assert corpo["compra_automatica"] is None


@pytest.mark.parametrize("comportamento", ["devolve_none", "lanca_excecao"])
def test_gancho_que_nao_conclui_vira_motivo(app, client, auth, comportamento):
    def comprar_sozinho(solicitacao):
        if comportamento == "lanca_excecao":
            raise RuntimeError("falha no M3")
        return None

    app.extensions["compra_automatica"] = comprar_sozinho
    criar_politica(client, auth, nivel_autonomia="automatica")

    resposta = solicitar(client, auth, ("arroz", 1))

    assert resposta.status_code == 201
    assert resposta.json["compra_automatica"] is None
    assert resposta.json["avaliacao"]["motivos"][-1] == COMPRA_AUTOMATICA_FALHOU


def test_gancho_nao_e_chamado_com_politica_manual_ou_item_sem_oferta(app, client, auth):
    chamadas = []
    app.extensions["compra_automatica"] = lambda solicitacao: chamadas.append(solicitacao)

    solicitar(client, auth, ("arroz", 1))
    criar_politica(client, auth, nivel_autonomia="automatica")
    solicitar(client, auth, ("arroz", 1), ("chocolate", 1))

    assert chamadas == []


def test_orcamento_mensal_estourado_desliga_a_compra_automatica(app, client, usuario):
    chamadas = []
    app.extensions["compra_automatica"] = lambda solicitacao: chamadas.append(solicitacao)
    _, headers = usuario(orcamento_mensal=20)
    criar_politica(client, headers, nivel_autonomia="automatica")

    avaliacao = solicitar(client, headers, ("arroz 5kg", 1)).json["avaliacao"]

    assert chamadas == []
    assert avaliacao["compra_automatica"] is False
    assert "passa do seu orçamento mensal de R$ 20,00" in avaliacao["motivos"][-1]


def test_marca_evitada_no_perfil_muda_a_recomendacao(app, client, usuario):
    app.extensions["catalogo"] = CatalogoFixo([
        oferta("M1", "Macarrão 500g", 3.99, "Massas", MERCEARIA, marca="Barata"),
        oferta("M2", "Macarrão 500g", 4.29, "Massas", MERCEARIA, marca="Nonna"),
    ])
    _, headers = usuario(preferencias={"marcas_preferidas": ["nonna"], "marcas_evitadas": ["barata"]})

    item = solicitar(client, headers, ("macarrão", 1)).json["itens"][0]

    assert item["recomendada"]["id_externo"] == "M2"
    assert "Marca preferida" in item["recomendada"]["explicacao"]
