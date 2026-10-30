"""Catálogo de ofertas: contrato da oferta, catálogo fixo e escolha do provedor."""

import mongomock
import pytest

from app import create_app
from app.solicitacoes.catalogo import obter_catalogo
from app.solicitacoes.catalogo.base import nova_oferta, palavras_relevantes, validar_oferta
from app.solicitacoes.catalogo.fixo import CatalogoFixo

ITENS_DO_CATALOGO_FIXO = [
    "arroz", "feijão", "leite", "café", "açúcar", "óleo", "macarrão", "detergente", "sabão em pó",
    "papel higiênico", "refrigerante", "cerveja",
]


@pytest.fixture(scope="module")
def catalogo():
    return CatalogoFixo()


@pytest.mark.parametrize("termo", ITENS_DO_CATALOGO_FIXO)
def test_catalogo_fixo_tem_ao_menos_3_ofertas_validas_por_item(catalogo, termo):
    ofertas = catalogo.buscar(termo)

    assert len(ofertas) >= 3
    for oferta in ofertas:
        validar_oferta(oferta)


def test_busca_traz_so_o_item_pedido(catalogo):
    ofertas = catalogo.buscar("arroz")

    assert ofertas
    assert all("Arroz" in oferta["titulo"] for oferta in ofertas)


def test_busca_respeita_o_limite(catalogo):
    assert len(catalogo.buscar("arroz", limite=2)) == 2


def test_busca_ignora_acentos_maiusculas_e_plural(catalogo):
    esperadas = [oferta["id_externo"] for oferta in catalogo.buscar("Feijão")]

    assert [oferta["id_externo"] for oferta in catalogo.buscar("feijao")] == esperadas
    assert [oferta["id_externo"] for oferta in catalogo.buscar("FEIJÕES")] == esperadas


def test_busca_exige_todas_as_palavras_relevantes(catalogo):
    ofertas = catalogo.buscar("leite integral")

    assert ofertas
    assert all("Integral" in oferta["titulo"] for oferta in ofertas)


def test_medidas_nao_restringem_a_busca(catalogo):
    com_medida = {oferta["id_externo"] for oferta in catalogo.buscar("arroz 5kg")}

    assert com_medida == {oferta["id_externo"] for oferta in catalogo.buscar("arroz")}


@pytest.mark.parametrize("termo, produto", [
    ("caixas de leite", "leite"),
    ("pacotes de café", "café"),
    ("garrafas de refrigerante", "refrigerante"),
    ("dúzias de ovos", "ovos"),
    ("meia dúzia de ovos", "ovos"),
    ("2 kg de feijão", "feijão"),
    ("leite 1 litro", "leite"),
    ("café 500 g", "café"),
    ("500 gramas de café", "café"),
    ("refrigerante 6 x 350ml", "refrigerante"),
])
def test_embalagens_e_medidas_separadas_do_numero_nao_restringem_a_busca(catalogo, termo, produto):
    esperadas = [oferta["id_externo"] for oferta in catalogo.buscar(produto)]

    assert esperadas
    assert [oferta["id_externo"] for oferta in catalogo.buscar(termo)] == esperadas


def test_pack_restringe_a_busca_aos_pacotes_com_varios_itens(catalogo):
    assert [oferta["id_externo"] for oferta in catalogo.buscar("pack de água")] == ["FIXO-043"]


@pytest.mark.parametrize("termo", ["xyzw", "5kg", "de com"])
def test_termo_sem_produto_conhecido_devolve_lista_vazia(catalogo, termo):
    assert catalogo.buscar(termo) == []


def test_busca_devolve_copias(catalogo):
    catalogo.buscar("arroz")[0]["preco"] = 0

    assert catalogo.buscar("arroz")[0]["preco"] > 0


def test_catalogo_aceita_ofertas_informadas():
    catalogo = CatalogoFixo([{"id_externo": "T1", "fonte": "teste", "titulo": "Arroz Teste 1kg", "preco": 5.0,
                              "categoria": "Arroz", "categorias_caminho": ["Arroz"], "loja": "Loja"}])

    oferta = catalogo.buscar("arroz")[0]

    assert oferta["id_externo"] == "T1"
    assert oferta["frete"] is None


def test_palavras_relevantes_usa_radical_e_ignora_medidas():
    assert palavras_relevantes("2 Leites Integrais de 1L") == {"leite", "integral"}


def test_palavras_ignoradas_valem_tambem_no_plural():
    assert palavras_relevantes("3 Pacotes de Café 500 g") == {"cafe"}


@pytest.mark.parametrize("campo, valor", [("preco", None), ("preco", 0), ("preco", True), ("loja", ""),
                                          ("categorias_caminho", "Arroz")])
def test_validar_oferta_recusa_oferta_fora_do_contrato(campo, valor):
    oferta = nova_oferta(id_externo="X", fonte="teste", titulo="Arroz", preco=5.0, categoria="Arroz",
                         categorias_caminho=["Arroz"], loja="Loja")
    oferta[campo] = valor

    with pytest.raises(ValueError):
        validar_oferta(oferta)


def test_obter_catalogo_usa_o_catalogo_dos_testes(app):
    falso = CatalogoFixo([])

    with app.app_context():
        app.extensions["catalogo"] = falso
        assert obter_catalogo() is falso


def test_obter_catalogo_usa_o_fixo_por_padrao(app):
    with app.app_context():
        catalogo = obter_catalogo()

        assert isinstance(catalogo, CatalogoFixo)
        assert obter_catalogo() is catalogo


def test_provedor_indisponivel_explica_o_problema(app):
    app.config["CATALOGO_PROVEDOR"] = "inexistente"

    with app.app_context(), pytest.raises(RuntimeError, match="CATALOGO_PROVEDOR=inexistente"):
        obter_catalogo()


def criar_app_com_provedor(provedor):
    config = {"TESTING": True, "JWT_SECRET_KEY": "chave-so-para-testes-com-32-caracteres",
              "CATALOGO_PROVEDOR": provedor}
    return create_app(config, cliente_mongo=mongomock.MongoClient(tz_aware=True))


@pytest.mark.parametrize("provedor", ["mercadolivre", "inexistente"])
def test_provedor_sem_conector_impede_a_api_de_subir(provedor):
    with pytest.raises(RuntimeError, match=f"CATALOGO_PROVEDOR={provedor} não está disponível"):
        criar_app_com_provedor(provedor)


@pytest.mark.parametrize("provedor", ["fixo", "dummyjson", "combinado", ""])
def test_provedor_com_conector_ou_vazio_deixa_a_api_subir(provedor):
    assert "solicitacoes" in criar_app_com_provedor(provedor).blueprints
