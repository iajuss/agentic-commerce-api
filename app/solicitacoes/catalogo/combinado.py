"""Catálogo que junta outros no mesmo ranking: no MVP, o fixo e a DummyJSON (opção C do spike M2-01).

O catálogo fixo traz a variedade de supermercado em português (lojas, embalagens, frete); a DummyJSON é o catálogo
externo, que alimenta o mesmo ranking. Se um deles estiver fora do ar, a busca segue com os outros.
"""

import logging
from itertools import zip_longest

from app.erros import ErroApi
from app.solicitacoes.catalogo.base import Catalogo

INDISPONIVEL = "Catálogo indisponível no momento. Tente novamente em instantes."

registro = logging.getLogger(__name__)


class CatalogoCombinado(Catalogo):
    """Busca em todos os catálogos e intercala as ofertas, para que cada um apareça entre as primeiras."""

    def __init__(self, catalogos):
        self._catalogos = list(catalogos)

    def buscar(self, termo, limite=10):
        resultados = []
        for catalogo in self._catalogos:
            try:
                resultados.append(catalogo.buscar(termo, limite))
            except ErroApi as erro:
                if erro.status != 502:
                    raise
                registro.warning("%s fora do ar; a busca segue com os outros catálogos.", type(catalogo).__name__)

        if not resultados:
            raise ErroApi(502, INDISPONIVEL)
        intercaladas = [oferta for grupo in zip_longest(*resultados) for oferta in grupo if oferta is not None]
        return intercaladas[:limite]
