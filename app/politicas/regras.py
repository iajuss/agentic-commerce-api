"""Validador de regras e autonomia.

Decide se as políticas do usuário permitem comprar uma oferta e se o agente pode
comprá-la sozinho. O orquestrador usa para filtrar as ofertas; a aprovação usa
para gerar a autorização sem pedir a senha quando a compra é automática.

A oferta é um dicionário normalizado pelo conector do catálogo com pelo menos
`preco`, `categoria` e `loja`. `frete` é opcional e soma no valor comparado com o teto.
"""

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
    ativas = [politica for politica in politicas if politica["ativa"]]
    if not ativas:
        return Avaliacao(permitida=True)

    aceitaram = []
    motivos = []
    for politica in ativas:
        violacoes = violacoes_da_politica(oferta, politica)
        if violacoes:
            motivos += [f"{politica['nome']}: {violacao}" for violacao in violacoes]
        else:
            aceitaram.append(politica)

    if not aceitaram:
        return Avaliacao(permitida=False, motivos=motivos)

    automatica = next((p for p in aceitaram if p["nivel_autonomia"] == AUTOMATICA), None)
    escolhida = automatica or aceitaram[0]
    return Avaliacao(permitida=True, compra_automatica=automatica is not None, politica_id=escolhida["_id"])


def violacoes_da_politica(oferta, politica):
    """Lista as regras da política que a oferta descumpre (vazia = a política aceita)."""
    violacoes = []

    total = oferta["preco"] + oferta.get("frete", 0)
    if total > politica["teto_por_compra"]:
        violacoes.append(f"total de {_reais(total)} passa do teto de {_reais(politica['teto_por_compra'])}")

    if politica["categorias"] and normalizar(oferta["categoria"]) not in politica["categorias"]:
        violacoes.append(f"categoria '{oferta['categoria']}' não permitida")

    if politica["lojas"] and normalizar(oferta["loja"]) not in politica["lojas"]:
        violacoes.append(f"loja '{oferta['loja']}' não permitida")

    return violacoes


def _reais(valor):
    return f"R$ {valor:.2f}".replace(".", ",")
