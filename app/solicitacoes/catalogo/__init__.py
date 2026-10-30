"""Catálogo de ofertas do orquestrador. A implementação vem de CATALOGO_PROVEDOR (padrão: fixo)."""

from flask import current_app

from app.solicitacoes.catalogo.dummyjson import CatalogoDummyJson
from app.solicitacoes.catalogo.fixo import CatalogoFixo

PROVEDOR_PADRAO = "fixo"


def _criar_fixo(config):
    return CatalogoFixo()


def _criar_dummyjson(config):
    return CatalogoDummyJson(timeout=int(config.get("HTTP_TIMEOUT_SEGUNDOS", 8)))


# Cada provedor recebe a configuração do app e devolve uma instância de Catalogo.
FABRICAS = {"fixo": _criar_fixo, "dummyjson": _criar_dummyjson}


def fabrica_do_provedor(config):
    """Fábrica do CATALOGO_PROVEDOR configurado; sem conector, o RuntimeError diz quais provedores existem."""
    provedor = config.get("CATALOGO_PROVEDOR") or PROVEDOR_PADRAO
    fabrica = FABRICAS.get(provedor)
    if fabrica is None:
        disponiveis = ", ".join(FABRICAS)
        raise RuntimeError(f"CATALOGO_PROVEDOR={provedor} não está disponível. Use um de: {disponiveis}.")
    return fabrica


def obter_catalogo():
    """Catálogo do app atual, criado na primeira chamada.

    Os testes podem colocar um catálogo falso em app.extensions["catalogo"].
    """
    catalogo = current_app.extensions.get("catalogo")
    if catalogo is None:
        criar = fabrica_do_provedor(current_app.config)
        catalogo = current_app.extensions["catalogo"] = criar(current_app.config)
    return catalogo
