"""Catálogo externo de reserva (opção C do spike): produtos de mercado da DummyJSON, sem chave.

Os títulos da DummyJSON estão em inglês, então o termo em português é traduzido palavra por palavra antes da
busca. Os preços são fictícios e tratados como reais; o frete não é informado e fica para a estimativa da
cesta.
"""

import re
import time

import requests

from app.erros import ErroApi
from app.solicitacoes.catalogo.base import Catalogo, nova_oferta, palavras_relevantes

URL_PRODUTOS = "https://dummyjson.com/products/category/groceries"
VALIDADE_CACHE_SEGUNDOS = 600
# Depois de uma falha, a DummyJSON só é consultada de novo após esta pausa. Sem ela, cada item da lista
# esperaria o timeout outra vez (20 itens x 8 s passam do timeout do gunicorn).
PAUSA_APOS_FALHA_SEGUNDOS = 60
INDISPONIVEL = "Catálogo indisponível no momento. Tente novamente em instantes."
LOJA_PADRAO = "DummyJSON"
CATEGORIA = "Mercearia"

# Radical em português (sem acento) -> palavras em inglês que precisam aparecer no título. "papel" fica de fora:
# "papel higiênico" casaria com a caixa de lenço ("Tissue Paper Box"), que é o que "lenço" encontra.
TRADUCOES = {
    "arroz": "rice", "leite": "milk", "ovo": "eggs", "cafe": "coffee", "agua": "water", "suco": "juice",
    "maca": "apple", "carne": "beef", "bife": "steak", "frango": "chicken", "peixe": "fish", "oleo": "oil",
    "batata": "potatoes", "cebola": "onions", "pepino": "cucumber", "pimentao": "bell pepper",
    "pimenta": "chili pepper", "mel": "honey", "sorvete": "ice cream", "kiwi": "kiwi", "limao": "lemon",
    "amora": "mulberry", "morango": "strawberry", "refrigerante": "soft drinks", "lenco": "tissue",
    "racao": "food", "gato": "cat", "cachorro": "dog", "proteina": "protein",
}

PRAZO = re.compile(r"(\d+)(?:-(\d+))?\s*(business day|day|week|month)")
DIAS_POR_UNIDADE = {"business day": 1, "day": 1, "week": 7, "month": 30}


class CatalogoDummyJson(Catalogo):
    """Baixa a categoria groceries uma vez a cada 10 minutos e busca localmente.

    Se a renovação falhar, continua usando as ofertas já baixadas; sem nenhuma, responde 502.
    """

    def __init__(self, timeout=8, relogio=time.monotonic):
        self._timeout = timeout
        self._relogio = relogio
        self._ofertas = None
        self._baixado_em = None
        self._falhou_em = None

    def buscar(self, termo, limite=10):
        procuradas = _traduzir(palavras_relevantes(termo))
        if not procuradas:
            return []
        encontradas = [dict(oferta) for palavras, oferta in self._indice() if procuradas <= palavras]
        return encontradas[:limite]

    def _indice(self):
        agora = self._relogio()
        if self._precisa_baixar(agora):
            try:
                self._ofertas = self._baixar()
                self._baixado_em = agora
                self._falhou_em = None
            except ErroApi:
                self._falhou_em = agora
        if self._ofertas is None:
            raise ErroApi(502, INDISPONIVEL)
        return self._ofertas

    def _precisa_baixar(self, agora):
        if self._falhou_em is not None and agora - self._falhou_em < PAUSA_APOS_FALHA_SEGUNDOS:
            return False
        return self._ofertas is None or agora - self._baixado_em > VALIDADE_CACHE_SEGUNDOS

    def _baixar(self):
        """Pares (palavras em inglês, oferta) dos produtos em estoque; qualquer falha vira 502."""
        try:
            resposta = requests.get(URL_PRODUTOS, params={"limit": 100}, timeout=self._timeout)
            resposta.raise_for_status()
            return [(_palavras_em_ingles(produto["title"]), _normalizar(produto))
                    for produto in resposta.json()["products"] if produto.get("stock")]
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
            raise ErroApi(502, INDISPONIVEL) from None


def _traduzir(radicais):
    """Palavras em inglês do termo.

    Qualificadores sem tradução ("integral") são ignorados; sem nenhuma tradução, o produto não existe neste
    catálogo e o resultado é vazio.
    """
    traduzidas = set()
    for palavra in radicais:
        if palavra in TRADUCOES:
            traduzidas |= _palavras_em_ingles(TRADUCOES[palavra])
    return traduzidas


def _palavras_em_ingles(texto):
    return {_radical_ingles(palavra) for palavra in re.findall(r"[a-z]+", texto.lower())}


def _radical_ingles(palavra):
    if palavra.endswith("oes"):
        return palavra[:-2]
    if palavra.endswith("ies") and len(palavra) > 4:
        return palavra[:-3] + "y"
    if palavra.endswith("s") and not palavra.endswith("ss") and len(palavra) > 3:
        return palavra[:-1]
    return palavra


def _prazo_em_dias(informacao):
    """ "Ships overnight" -> 1, "Ships in 1-2 business days" -> 2, "Ships in 2 weeks" -> 14."""
    texto = (informacao or "").lower()
    if "overnight" in texto:
        return 1
    encontrado = PRAZO.search(texto)
    if encontrado is None:
        return None
    quantidade = int(encontrado.group(2) or encontrado.group(1))
    return quantidade * DIAS_POR_UNIDADE[encontrado.group(3)]


def _normalizar(produto):
    marca = produto.get("brand")
    return nova_oferta(
        id_externo=f"DJ-{produto['id']}",
        fonte="dummyjson",
        titulo=produto["title"],
        marca=marca,
        preco=round(float(produto["price"]), 2),
        frete=None,
        frete_gratis=False,
        prazo_dias=_prazo_em_dias(produto.get("shippingInformation")),
        avaliacao=produto.get("rating"),
        estoque=produto.get("stock"),
        categoria=CATEGORIA,
        categorias_caminho=[CATEGORIA],
        loja=marca or LOJA_PADRAO,
        imagem=produto.get("thumbnail"),
    )
