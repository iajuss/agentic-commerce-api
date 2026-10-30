"""Regras puras do pós-compra (estados do pedido, cancelamento e devolução), sem Flask nem banco.

O envio, a entrega e a devolução são simulados: acontecem sozinhos depois de alguns minutos e são aplicados na
leitura do pedido (seção 1 do contrato). `agora()` é a única fonte de data do módulo; os testes a trocam por
`monkeypatch` para simular a passagem do tempo.
"""

from datetime import datetime, timedelta, timezone

from app.pagamento.regras import AGUARDANDO_PAGAMENTO, PAGO

ENVIADO = "enviado"
ENTREGUE = "entregue"
EXPIRADO = "expirado"
CANCELADO = "cancelado"
DEVOLUCAO_SOLICITADA = "devolucao_solicitada"
DEVOLVIDO = "devolvido"

# Estados do pedido (tabela do M3-04). As automáticas vêm de transicoes_devidas;
# as demais, do simulador e do PATCH.
TRANSICOES_PERMITIDAS = frozenset({
    (AGUARDANDO_PAGAMENTO, PAGO),
    (AGUARDANDO_PAGAMENTO, EXPIRADO),
    (AGUARDANDO_PAGAMENTO, CANCELADO),
    (PAGO, ENVIADO),
    (ENVIADO, ENTREGUE),
    (PAGO, CANCELADO),
    (ENVIADO, CANCELADO),
    (ENTREGUE, DEVOLUCAO_SOLICITADA),
    (DEVOLUCAO_SOLICITADA, DEVOLVIDO),
})


def agora():
    """UTC com milissegundos inteiros, a precisão do BSON: a resposta e a próxima leitura mostram a mesma data."""
    momento = datetime.now(timezone.utc)
    return momento.replace(microsecond=momento.microsecond // 1000 * 1000)


def transicao_permitida(atual, novo):
    return (atual, novo) in TRANSICOES_PERMITIDAS


def transicoes_devidas(pedido, agora, minutos_envio, minutos_entrega):
    """Transições simuladas que já deveriam ter acontecido, em ordem, como (de, para, em).

    `em` é o momento em que a transição aconteceu (ex.: o envio sai `minutos_envio` depois do pagamento), não a
    hora da leitura, para o histórico contar a história certa mesmo quando o pedido é lido muito depois.
    """
    envio = timedelta(minutes=minutos_envio)
    entrega = timedelta(minutes=minutos_entrega)
    status = pedido["status"]

    if status == AGUARDANDO_PAGAMENTO:
        vence_em = pedido["pix"]["expira_em"]
        return [(AGUARDANDO_PAGAMENTO, EXPIRADO, vence_em)] if agora >= vence_em else []

    if status == DEVOLUCAO_SOLICITADA:
        devolvido_em = momento_do_status(pedido, DEVOLUCAO_SOLICITADA) + entrega
        return [(DEVOLUCAO_SOLICITADA, DEVOLVIDO, devolvido_em)] if agora >= devolvido_em else []

    devidas = []
    if status == PAGO:
        enviado_em = pedido["pix"]["pago_em"] + envio
        if agora < enviado_em:
            return []
        devidas.append((PAGO, ENVIADO, enviado_em))
    elif status == ENVIADO:
        enviado_em = momento_do_status(pedido, ENVIADO)
    else:
        return []  # entregue, expirado, cancelado e devolvido só mudam por ação do usuário ou nunca mais

    entregue_em = enviado_em + entrega
    if agora >= entregue_em:
        devidas.append((ENVIADO, ENTREGUE, entregue_em))
    return devidas


def momento_do_status(pedido, status):
    """Quando o pedido entrou pela última vez em `status`, pelo histórico; None se nunca entrou."""
    return next((registro["em"] for registro in reversed(pedido["historico"]) if registro["status"] == status),
                None)


def reembolso(pedido, momento):
    """Reembolso simulado do valor total do pedido."""
    return {"valor": pedido["total"], "status": "simulado", "em": momento}
