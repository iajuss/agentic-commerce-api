"""Validação do corpo de POST e PUT /politicas."""

import math

from app.erros import ErroApi
from app.politicas.regras import MANUAL, NIVEIS_AUTONOMIA, normalizar

TAMANHO_MAXIMO_NOME = 80


def validar_politica(corpo):
    """Devolve a política pronta para salvar ou responde 400 com o erro de cada campo.

    Categorias e lojas vazias significam "qualquer uma". Campos desconhecidos são ignorados.
    """
    erros = {}

    nome = corpo.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        erros["nome"] = "Informe um nome."
    elif len(nome.strip()) > TAMANHO_MAXIMO_NOME:
        erros["nome"] = f"Use no máximo {TAMANHO_MAXIMO_NOME} caracteres."

    teto = corpo.get("teto_por_compra")
    if not _eh_numero(teto) or teto <= 0:
        erros["teto_por_compra"] = "Informe um valor maior que zero."

    categorias = _lista_de_textos(corpo.get("categorias", []))
    if categorias is None:
        erros["categorias"] = "Informe uma lista de textos."

    lojas = _lista_de_textos(corpo.get("lojas", []))
    if lojas is None:
        erros["lojas"] = "Informe uma lista de textos."

    nivel_autonomia = corpo.get("nivel_autonomia", MANUAL)
    if nivel_autonomia not in NIVEIS_AUTONOMIA:
        erros["nivel_autonomia"] = f"Use um destes valores: {', '.join(NIVEIS_AUTONOMIA)}."

    ativa = corpo.get("ativa", True)
    if not isinstance(ativa, bool):
        erros["ativa"] = "Use true ou false."

    if erros:
        raise ErroApi(400, "Política inválida.", erros)

    return {
        "nome": nome.strip(),
        "teto_por_compra": float(teto),
        "categorias": categorias,
        "lojas": lojas,
        "nivel_autonomia": nivel_autonomia,
        "ativa": ativa,
    }


def _eh_numero(valor):
    # bool é subclasse de int no Python, então true/false precisam ser recusados à parte.
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _lista_de_textos(valor):
    """Normaliza e remove repetidos; devolve None se não for uma lista de textos."""
    if not isinstance(valor, list) or not all(isinstance(item, str) for item in valor):
        return None
    return list(dict.fromkeys(normalizar(item) for item in valor if item.strip()))
