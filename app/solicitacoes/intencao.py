"""Interpretação da lista de compras escrita pelo usuário, sem LLM.

"arroz 5kg, 2 leites e duas caixas de sabão em pó" vira
[{"descricao": "arroz 5kg", "quantidade": 1}, {"descricao": "leites", "quantidade": 2},
 {"descricao": "caixas de sabão em pó", "quantidade": 2}].

O limite de itens por solicitação é conferido na validação da rota, não aqui.
"""

import re
import unicodedata

MAXIMO_QUANTIDADE = 99
TAMANHO_MAXIMO_DESCRICAO = 80

SEPARADORES = re.compile(r"[,;\n]+|\s+e\s+", re.IGNORECASE)
# "2 leites", "2x leite", "2 x leite"; um número seguido de unidade ("2 kg de feijão") é medida, não quantidade.
QUANTIDADE_EM_DIGITOS = re.compile(
    r"^(\d{1,2})\s*x?\s+(?!(?:kg|g|ml|l|lt|litros?|rolos?|un|unid|unidades?)\b)(.+)$", re.IGNORECASE
)
POR_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
}


def interpretar_intencao(texto):
    """Itens da lista, na ordem em que aparecem; itens repetidos somam as quantidades."""
    itens = {}
    for trecho in SEPARADORES.split(texto or ""):
        trecho = " ".join(trecho.split())
        if not trecho:
            continue

        quantidade, descricao = _separar_quantidade(trecho)
        descricao = descricao[:TAMANHO_MAXIMO_DESCRICAO].strip()
        if not descricao:
            continue

        chave = _chave(descricao)
        if chave in itens:
            itens[chave]["quantidade"] = min(itens[chave]["quantidade"] + quantidade, MAXIMO_QUANTIDADE)
        else:
            itens[chave] = {"descricao": descricao, "quantidade": quantidade}
    return list(itens.values())


def _separar_quantidade(trecho):
    em_digitos = QUANTIDADE_EM_DIGITOS.match(trecho)
    if em_digitos:
        return max(int(em_digitos.group(1)), 1), em_digitos.group(2)

    primeira, _, resto = trecho.partition(" ")
    if resto and _chave(primeira) in POR_EXTENSO:
        return POR_EXTENSO[_chave(primeira)], resto
    return 1, trecho


def _chave(texto):
    """Comparação sem acentos nem maiúsculas: "Leite" e "leite" são o mesmo item."""
    decomposto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))
