"""Medidas de embalagem lidas do título da oferta.

Servem para comparar o preço por kg, litro ou unidade e para calcular quantas embalagens atendem ao pedido.
"""

import math
import re

from app.solicitacoes.catalogo.base import radical, sem_acentos

# Unidade escrita no título -> (unidade base, fator de conversão).
UNIDADES = {
    "kg": ("kg", 1.0), "quilo": ("kg", 1.0), "quilos": ("kg", 1.0), "kilo": ("kg", 1.0), "kilos": ("kg", 1.0),
    "g": ("kg", 0.001), "grama": ("kg", 0.001), "gramas": ("kg", 0.001),
    "l": ("l", 1.0), "lt": ("l", 1.0), "litro": ("l", 1.0), "litros": ("l", 1.0), "ml": ("l", 0.001),
    "un": ("un", 1.0), "und": ("un", 1.0), "unid": ("un", 1.0), "unidade": ("un", 1.0), "unidades": ("un", 1.0),
    "rolo": ("un", 1.0), "rolos": ("un", 1.0),
}
NOMES_EXIBIDOS = {"kg": "kg", "l": "L", "un": "un"}

# Palavras do pedido que contam embalagens, e não itens soltos: "2 fardos de água" são 2 fardos.
EMBALAGEM_EXTERNA = frozenset({"pack", "fardo", "kit", "pacote", "embalagem"})
# Num pacote de itens soltos (ovos, rolos), estas também nomeiam a embalagem ("2 caixas de ovos"); num
# multipack ("Leite Caixa 12x1L"), "2 caixas de leite" são 2 das caixinhas de dentro.
EMBALAGEM_DE_ITENS_SOLTOS = EMBALAGEM_EXTERNA | {"caixa", "bandeja", "cartela", "saco"}

NUMERO = r"(\d+(?:[.,]\d+)?)"
UNIDADE = r"(kg|quilos?|kilos?|g|gramas?|ml|lt|litros?|l|un|und|unid|unidades?|rolos?)"
MULTIPACK = re.compile(rf"(\d+)\s*x\s*{NUMERO}\s*{UNIDADE}\b", re.IGNORECASE)  # "12x1L", "6 x 350ml"
PACK_DE_LATAS = re.compile(  # "Pack 12 Latas 350ml", "6 garrafas de 600ml"
    rf"(\d+)\s*(?:latas?|garrafas?|long necks?)\s+(?:de\s+)?{NUMERO}\s*(ml|l)\b", re.IGNORECASE
)
SIMPLES = re.compile(rf"{NUMERO}\s*{UNIDADE}\b", re.IGNORECASE)  # "5kg", "1,6 kg", "12 Rolos"
DUZIA = re.compile(r"(?:\b(meia)\s+|(\d+)\s*)?d[uú]zias?\b", re.IGNORECASE)  # "Ovos Dúzia", "meia dúzia"


def extrair_medida(titulo):
    """Quantidade total da embalagem ("Leite Caixa 12x1L" -> {"quantidade": 12.0, "unidade": "l"}) ou None."""
    for padrao in (MULTIPACK, PACK_DE_LATAS):
        encontrado = padrao.search(titulo or "")
        if encontrado:
            vezes, numero, unidade = encontrado.groups()
            return _medida(int(vezes) * _numero(numero), unidade)

    encontrado = SIMPLES.search(titulo or "")
    if encontrado:
        numero, unidade = encontrado.groups()
        return _medida(_numero(numero), unidade)

    encontrado = DUZIA.search(titulo or "")
    if encontrado:
        meia, numero = encontrado.groups()
        return _medida(6 if meia else 12 * int(numero or 1), "un")
    return None


def formatar_medida(medida):
    """{"quantidade": 5.0, "unidade": "kg"} -> "5 kg"; {"quantidade": 1.5, "unidade": "l"} -> "1,5 L"."""
    quantidade = f"{medida['quantidade']:g}".replace(".", ",")
    return f"{quantidade} {NOMES_EXIBIDOS[medida['unidade']]}"


def embalagens_necessarias(quantidade, descricao, titulo):
    """Embalagens da oferta que atendem ao item pedido e a frase que explica o ajuste (None se nada mudou).

    - Com medida no pedido, compra o suficiente para completar quantidade x medida: "2 kg de feijão" em
      pacotes de 1 kg são 2 pacotes.
    - Sem medida, a quantidade conta os itens de uma embalagem com vários: "Dez ovos" numa caixa com 12
      unidades é 1 caixa, a não ser que o pedido fale da embalagem ("2 caixas de ovos").
    - Nos demais casos, a quantidade pedida já é o número de embalagens.
    """
    medida = extrair_medida(titulo)
    if medida is None:
        return quantidade, None

    pedida = extrair_medida(descricao)
    if pedida is not None:
        if pedida["unidade"] != medida["unidade"]:
            return quantidade, None
        total = {"quantidade": round(quantidade * pedida["quantidade"], 3), "unidade": pedida["unidade"]}
        embalagens = _arredondar_para_cima(total["quantidade"] / medida["quantidade"])
        frase = f"Você pediu {formatar_medida(total)}: {_embalagens(embalagens)} de {formatar_medida(medida)}"
    else:
        soltos = _itens_soltos(titulo)
        if soltos is None:
            return quantidade, None
        itens, nomes_da_embalagem = soltos
        if nomes_da_embalagem & _palavras(descricao):
            return quantidade, None
        embalagens = _arredondar_para_cima(quantidade / itens)
        frase = f"Você pediu {quantidade}: {_embalagens(embalagens)} com {itens} unidades"
    return embalagens, frase if embalagens != quantidade else None


def _medida(quantidade, unidade):
    base, fator = UNIDADES[unidade.lower()]
    total = round(quantidade * fator, 3)
    return {"quantidade": total, "unidade": base} if total > 0 else None


def _numero(texto):
    return float(texto.replace(",", "."))


def _itens_soltos(titulo):
    """(itens, palavras que nomeiam a embalagem) de uma oferta com vários itens dentro, ou None."""
    for padrao in (MULTIPACK, PACK_DE_LATAS):
        encontrado = padrao.search(titulo or "")
        if encontrado:
            vezes = int(encontrado.group(1))
            return (vezes, EMBALAGEM_EXTERNA) if vezes > 1 else None

    medida = extrair_medida(titulo)
    if medida and medida["unidade"] == "un" and medida["quantidade"] > 1:
        return int(medida["quantidade"]), EMBALAGEM_DE_ITENS_SOLTOS
    return None


def _palavras(texto):
    return {radical(palavra) for palavra in re.findall(r"[a-z]+", sem_acentos(texto))}


def _arredondar_para_cima(valor):
    # O round evita que um resultado como 2.0000000001 vire 3 embalagens.
    return max(1, math.ceil(round(valor, 6)))


def _embalagens(quantidade):
    return f"{quantidade} {'embalagem' if quantidade == 1 else 'embalagens'}"
