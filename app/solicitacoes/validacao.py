"""Validação do corpo de POST /solicitacoes: o texto da lista de compras ou os itens já separados."""

from app.erros import ErroApi
from app.solicitacoes.intencao import MAXIMO_QUANTIDADE, TAMANHO_MAXIMO_DESCRICAO, interpretar_intencao

MAXIMO_ITENS = 20
TAMANHO_MINIMO_TEXTO = 3
TAMANHO_MAXIMO_TEXTO = 500
INVALIDA = "Solicitação inválida."


def validar_solicitacao(corpo):
    """Devolve {"texto", "itens"} pronta para o orquestrador ou responde 400 com o erro de cada campo.

    Exatamente um de `texto` (interpretado em itens) ou `itens` ([{descricao, quantidade}]) deve vir no corpo.
    """
    tem_texto, tem_itens = "texto" in corpo, "itens" in corpo
    if tem_texto == tem_itens:
        raise ErroApi(400, INVALIDA, {"texto": "Envie o texto da lista de compras ou os itens, não os dois."})
    if tem_texto:
        return _validar_texto(corpo["texto"])
    return {"texto": None, "itens": _validar_itens(corpo["itens"])}


def _validar_texto(texto):
    if not isinstance(texto, str) or not TAMANHO_MINIMO_TEXTO <= len(texto.strip()) <= TAMANHO_MAXIMO_TEXTO:
        erro = f"Escreva a lista com {TAMANHO_MINIMO_TEXTO} a {TAMANHO_MAXIMO_TEXTO} caracteres."
        raise ErroApi(400, INVALIDA, {"texto": erro})

    itens = interpretar_intencao(texto)
    if not itens:
        raise ErroApi(400, INVALIDA, {"texto": "Não encontramos itens na lista."})
    if len(itens) > MAXIMO_ITENS:
        raise ErroApi(400, INVALIDA, {"texto": f"Use no máximo {MAXIMO_ITENS} itens por solicitação."})
    return {"texto": texto.strip(), "itens": itens}


def _validar_itens(itens):
    if not isinstance(itens, list) or not 1 <= len(itens) <= MAXIMO_ITENS:
        raise ErroApi(400, INVALIDA, {"itens": f"Informe de 1 a {MAXIMO_ITENS} itens."})

    erros = {}
    validos = []
    for indice, item in enumerate(itens):
        if not isinstance(item, dict):
            erros[f"itens[{indice}]"] = "Use um objeto com descricao e quantidade."
            continue

        descricao = item.get("descricao")
        if not isinstance(descricao, str) or not 1 <= len(descricao.strip()) <= TAMANHO_MAXIMO_DESCRICAO:
            erros[f"itens[{indice}].descricao"] = f"Descreva o item com até {TAMANHO_MAXIMO_DESCRICAO} caracteres."

        quantidade = item.get("quantidade", 1)
        if not _eh_quantidade(quantidade):
            erros[f"itens[{indice}].quantidade"] = f"Use um número inteiro de 1 a {MAXIMO_QUANTIDADE}."

        if not erros:
            validos.append({"descricao": " ".join(descricao.split()), "quantidade": quantidade})

    if erros:
        raise ErroApi(400, INVALIDA, erros)
    return validos


def _eh_quantidade(valor):
    # bool é subclasse de int no Python, então true/false precisam ser recusados à parte.
    return isinstance(valor, int) and not isinstance(valor, bool) and 1 <= valor <= MAXIMO_QUANTIDADE
