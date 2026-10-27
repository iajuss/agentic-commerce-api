"""Catálogo local de supermercado, sem rede: padrão em desenvolvimento, nos testes e na demonstração."""

import json
from pathlib import Path

from app.solicitacoes.catalogo.base import Catalogo, nova_oferta, palavras_relevantes

ARQUIVO_DADOS = Path(__file__).with_name("dados_fixos.json")


class CatalogoFixo(Catalogo):
    """Busca nas ofertas de dados_fixos.json ou nas informadas no construtor (útil nos testes)."""

    def __init__(self, ofertas=None):
        if ofertas is None:
            ofertas = json.loads(ARQUIVO_DADOS.read_text(encoding="utf-8"))
        self._indice = [(_palavras_da_oferta(oferta), nova_oferta(**oferta)) for oferta in ofertas]

    def buscar(self, termo, limite=10):
        """Ofertas cujo título ou categoria contém todas as palavras relevantes do termo."""
        procuradas = palavras_relevantes(termo)
        if not procuradas:
            return []
        encontradas = [dict(oferta) for palavras, oferta in self._indice if procuradas <= palavras]
        return encontradas[:limite]


def _palavras_da_oferta(oferta):
    texto = " ".join([oferta["titulo"], oferta["categoria"], *oferta.get("categorias_caminho", [])])
    return palavras_relevantes(texto)
