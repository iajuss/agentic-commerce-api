"""Regras puras de autorizações e pedidos, sem Flask nem banco.

`agora()` é a única fonte de data do módulo; os testes a trocam por `monkeypatch` para simular a
passagem do tempo.
"""

from datetime import datetime, timedelta, timezone

COM_OFERTA = "com_oferta"
CAMPOS_DA_OFERTA = ("id_externo", "titulo", "preco", "loja")
AGUARDANDO_PAGAMENTO = "aguardando_pagamento"
PAGO = "pago"
CAMPOS_DO_PEDIDO = ("solicitacao_id", "autorizacao_id", "status", "itens", "total", "pix", "historico", "entrega",
                    "criado_em")


def agora():
    """UTC com milissegundos inteiros, a precisão do BSON: a resposta do POST e a do GET mostram a mesma data."""
    momento = datetime.now(timezone.utc)
    return momento.replace(microsecond=momento.microsecond // 1000 * 1000)


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


def montar_pedido(autorizacao, cobranca, momento):
    """Pedido da autorização consumida: os mesmos itens e o valor autorizado, à espera do Pix."""
    return {
        "usuario_id": autorizacao["usuario_id"],
        "solicitacao_id": autorizacao["solicitacao_id"],
        "autorizacao_id": autorizacao["_id"],
        "status": AGUARDANDO_PAGAMENTO,
        "itens": [dict(item) for item in autorizacao["itens"]],
        "total": autorizacao["valor_maximo"],
        "pix": cobranca,
        "historico": [{"status": AGUARDANDO_PAGAMENTO, "em": momento}],
        "entrega": {"simulada": True},
        "criado_em": momento,
        "atualizado_em": momento,
    }


def pedido_para_json(pedido):
    """Comprovante no formato da seção 10 do contrato (sem o dono); `reembolso` só aparece quando existe.

    O `copia_e_cola` só serve enquanto o pedido aguarda pagamento; depois o Pix mostra só `txid` e `pago_em`.
    """
    corpo = {"id": pedido["_id"], **{campo: pedido[campo] for campo in CAMPOS_DO_PEDIDO}}
    if pedido["status"] != AGUARDANDO_PAGAMENTO:
        corpo["pix"] = {"txid": pedido["pix"]["txid"], "pago_em": pedido["pix"]["pago_em"]}
    for campo in ("reembolso", "devolucao"):
        if pedido.get(campo):
            corpo[campo] = pedido[campo]
    return corpo


def resumo_do_pedido(pedido):
    return {
        "id": pedido["_id"],
        "status": pedido["status"],
        "total": pedido["total"],
        "quantidade_itens": sum(item["quantidade"] for item in pedido["itens"]),
        "criado_em": pedido["criado_em"],
    }
