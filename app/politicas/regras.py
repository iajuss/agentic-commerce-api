"""Validador de regras e autonomia.

Decide se as políticas do usuário permitem comprar uma oferta ou uma cesta e se o agente pode
comprá-la sozinho. O orquestrador usa para filtrar as ofertas e avaliar a cesta recomendada; a
aprovação usa o resultado gravado na solicitação.

A oferta é um dicionário normalizado pelo conector do catálogo com pelo menos `preco`, `categoria`
e `loja`. `frete` é opcional e soma no valor comparado com o teto. `categorias_caminho` (da mais
geral à mais específica) deixa uma política de "bebidas" aceitar "Cervejas".
"""

import unicodedata
from dataclasses import dataclass, field

from bson import ObjectId

MANUAL = "manual"  # o agente recomenda e o usuário aprova cada compra com a senha
AUTOMATICA = "automatica"  # o agente compra sozinho quando a oferta cabe na política
NIVEIS_AUTONOMIA = (MANUAL, AUTOMATICA)


@dataclass(frozen=True)
class Avaliacao:
    permitida: bool
    compra_automatica: bool = False
    politica_id: ObjectId | None = None  # política que liberou a oferta
    motivos: list[str] = field(default_factory=list)  # por que cada política recusou


def normalizar(texto):
    """Categorias e lojas são comparadas sem diferenciar maiúsculas nem espaços nas pontas."""
    return texto.strip().lower()


def avaliar_oferta(oferta, politicas):
    """A oferta é permitida se ao menos uma política ativa a aceita.

    Sem nenhuma política ativa nada é bloqueado, mas o agente nunca compra sozinho.
    Se mais de uma política aceita, vale a que dá mais autonomia.
    """
    return _avaliar(politicas, lambda politica: violacoes_da_politica(oferta, politica))


def avaliar_cesta(itens, frete_total, politicas):
    """A cesta é permitida se uma mesma política ativa aceita todos os itens e o total cabe no teto.

    `itens` é uma lista de {"oferta": ..., "quantidade": ...}; o total é a soma de preço x quantidade
    mais `frete_total`. As demais regras são as de `avaliar_oferta`.
    """
    total = round(sum(item["oferta"]["preco"] * item["quantidade"] for item in itens) + frete_total, 2)

    def violacoes(politica):
        encontradas = _violacoes_de_teto(total, politica)
        for item in itens:
            encontradas += _violacoes_de_item(item["oferta"], politica)
        return list(dict.fromkeys(encontradas))  # sem repetir o mesmo motivo de dois itens

    return _avaliar(politicas, violacoes)


def violacoes_da_politica(oferta, politica):
    """Lista as regras da política que a oferta descumpre (vazia = a política aceita)."""
    total = oferta["preco"] + (oferta.get("frete") or 0)
    return _violacoes_de_teto(total, politica) + _violacoes_de_item(oferta, politica)


def _avaliar(politicas, violacoes_de):
    ativas = [politica for politica in politicas if politica["ativa"]]
    if not ativas:
        return Avaliacao(permitida=True)

    aceitaram = []
    motivos = []
    for politica in ativas:
        violacoes = violacoes_de(politica)
        if violacoes:
            motivos += [f"{politica['nome']}: {violacao}" for violacao in violacoes]
        else:
            aceitaram.append(politica)

    if not aceitaram:
        return Avaliacao(permitida=False, motivos=motivos)

    automatica = next((p for p in aceitaram if p["nivel_autonomia"] == AUTOMATICA), None)
    escolhida = automatica or aceitaram[0]
    return Avaliacao(permitida=True, compra_automatica=automatica is not None, politica_id=escolhida["_id"])


def _violacoes_de_teto(total, politica):
    if total > politica["teto_por_compra"]:
        return [f"total de {_reais(total)} passa do teto de {_reais(politica['teto_por_compra'])}"]
    return []


def _violacoes_de_item(oferta, politica):
    violacoes = []

    permitidas = {_comparavel(categoria) for categoria in politica["categorias"]}
    if permitidas and not permitidas & _categorias_da_oferta(oferta):
        violacoes.append(f"categoria '{oferta['categoria']}' não permitida")

    lojas = {_comparavel(loja) for loja in politica["lojas"]}
    if lojas and _comparavel(oferta["loja"]) not in lojas:
        violacoes.append(f"loja '{oferta['loja']}' não permitida")

    return violacoes


def _categorias_da_oferta(oferta):
    """Caminho de categorias da oferta; sem caminho, só a categoria."""
    return {_comparavel(categoria) for categoria in (oferta.get("categorias_caminho") or [oferta["categoria"]])}


def _comparavel(texto):
    """Forma usada na comparação: normalizada e sem acentos ("Bebidas Alcoólicas" -> "bebidas alcoolicas")."""
    decomposto = unicodedata.normalize("NFKD", normalizar(texto))
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))


def _reais(valor):
    return f"R$ {valor:.2f}".replace(".", ",")
