"""Medidas de embalagem lidas do título da oferta, para comparar o preço por kg, litro ou unidade."""

import re

# Unidade escrita no título -> (unidade base, fator de conversão).
UNIDADES = {
    "kg": ("kg", 1.0), "g": ("kg", 0.001), "l": ("l", 1.0), "lt": ("l", 1.0), "litro": ("l", 1.0),
    "litros": ("l", 1.0), "ml": ("l", 0.001), "un": ("un", 1.0), "und": ("un", 1.0), "unid": ("un", 1.0),
    "unidade": ("un", 1.0), "unidades": ("un", 1.0), "rolo": ("un", 1.0), "rolos": ("un", 1.0),
}
NOMES_EXIBIDOS = {"kg": "kg", "l": "L", "un": "un"}

NUMERO = r"(\d+(?:[.,]\d+)?)"
UNIDADE = r"(kg|g|ml|lt|litros?|l|un|und|unid|unidades?|rolos?)"
MULTIPACK = re.compile(rf"(\d+)\s*x\s*{NUMERO}\s*{UNIDADE}\b", re.IGNORECASE)  # "12x1L", "6 x 350ml"
PACK_DE_LATAS = re.compile(  # "Pack 12 Latas 350ml", "6 garrafas de 600ml"
    rf"(\d+)\s*(?:latas?|garrafas?|long necks?)\s+(?:de\s+)?{NUMERO}\s*(ml|l)\b", re.IGNORECASE
)
SIMPLES = re.compile(rf"{NUMERO}\s*{UNIDADE}\b", re.IGNORECASE)  # "5kg", "1,6 kg", "12 Rolos"


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
    return None


def formatar_medida(medida):
    """{"quantidade": 5.0, "unidade": "kg"} -> "5 kg"; {"quantidade": 1.5, "unidade": "l"} -> "1,5 L"."""
    quantidade = f"{medida['quantidade']:g}".replace(".", ",")
    return f"{quantidade} {NOMES_EXIBIDOS[medida['unidade']]}"


def _medida(quantidade, unidade):
    base, fator = UNIDADES[unidade.lower()]
    total = round(quantidade * fator, 3)
    return {"quantidade": total, "unidade": base} if total > 0 else None


def _numero(texto):
    return float(texto.replace(",", "."))
