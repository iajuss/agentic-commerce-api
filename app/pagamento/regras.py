"""Regras puras de autorizações e pedidos, sem Flask nem banco.

`agora()` é a única fonte de data do módulo; os testes a trocam por `monkeypatch` para simular a
passagem do tempo.
"""

from datetime import datetime, timedelta, timezone

COM_OFERTA = "com_oferta"
CAMPOS_DA_OFERTA = ("id_externo", "titulo", "preco", "loja")


def agora():
    return datetime.now(timezone.utc)


def itens_autorizados(solicitacao):
    """Cópia enxuta dos itens com oferta: só o que o pedido precisa, sem a explicação do ranking."""
    return [
        {**{campo: item["recomendada"][campo] for campo in CAMPOS_DA_OFERTA}, "quantidade": item["quantidade"]}
        for item in solicitacao["itens"]
        if item["status"] == COM_OFERTA
    ]


def montar_autorizacao(solicitacao, origem, momento, validade_minutos):
    """Autorização limitada à cesta aprovada: valor, lojas e itens fixos, uso único e prazo curto."""
    return {
        "usuario_id": solicitacao["usuario_id"],
        "solicitacao_id": solicitacao["_id"],
        "origem": origem,
        "politica_id": solicitacao["avaliacao"]["politica_id"],
        "valor_maximo": round(solicitacao["cesta"]["total"], 2),
        "lojas": list(solicitacao["cesta"]["lojas"]),
        "itens": itens_autorizados(solicitacao),
        "status": "ativa",
        "expira_em": momento + timedelta(minutes=validade_minutos),
        "criada_em": momento,
        "atualizada_em": momento,
    }
