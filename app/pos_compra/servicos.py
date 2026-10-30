"""Casos de uso do pós-compra: aplica as transições simuladas do pedido, gravando cada uma uma só vez."""

from flask import current_app

from app.pagamento import repositorio_contrato, repositorio_pedidos
from app.pagamento.auditoria import auditar
from app.pos_compra import regras


def aplicar_transicoes(usuario_id, pedido):
    """Grava as transições simuladas já devidas e devolve o pedido atualizado.

    Cada transição leva o status esperado no filtro: se outra leitura gravou antes, relê o pedido e continua
    dali, então duas leituras seguidas nunca duplicam o histórico nem os eventos.
    """
    minutos_envio = int(current_app.config.get("SIMULACAO_ENVIO_MINUTOS", 2))
    minutos_entrega = int(current_app.config.get("SIMULACAO_ENTREGA_MINUTOS", 5))

    for de, para, em in regras.transicoes_devidas(pedido, regras.agora(), minutos_envio, minutos_entrega):
        campos = {"reembolso": regras.reembolso(pedido, em)} if para == regras.DEVOLVIDO else None
        atualizado = repositorio_pedidos.mudar_status(usuario_id, pedido["_id"], de, para, em, campos)
        if atualizado is None:
            return aplicar_transicoes(usuario_id, repositorio_pedidos.obter(usuario_id, pedido["_id"]))
        pedido = atualizado
        _efeitos_da_transicao(usuario_id, pedido, para)
    return pedido


def _efeitos_da_transicao(usuario_id, pedido, status):
    if status == regras.EXPIRADO:
        repositorio_contrato.mudar_status_solicitacao(usuario_id, pedido["solicitacao_id"],
                                                      repositorio_contrato.APROVADA, repositorio_contrato.EXPIRADA)
        auditar(usuario_id, "pedido_expirado", "pedido", pedido["_id"])
    elif status == regras.ENTREGUE:
        auditar(usuario_id, "pedido_entregue", "pedido", pedido["_id"])
