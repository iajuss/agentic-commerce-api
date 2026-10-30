"""Casos de uso do pós-compra: aplica as transições simuladas do pedido, gravando cada uma uma só vez."""

from flask import current_app

from app.pagamento import repositorio_contrato, repositorio_pedidos
from app.pagamento.auditoria import auditar
from app.pagamento.regras import AGUARDANDO_PAGAMENTO
from app.erros import ErroApi
from app.pos_compra import regras


def mudar_status_pelo_usuario(usuario_id, pedido, novo, motivo=None):
    """Cancelamento ou devolução pedidos pelo usuário (PATCH), depois das transições simuladas já devidas.

    Grava com o status atual no filtro: se outra requisição mudou o pedido no meio, responde 409.
    """
    pedido = aplicar_transicoes(usuario_id, pedido)
    atual = pedido["status"]
    if not regras.transicao_permitida(atual, novo) or novo not in (regras.CANCELADO, regras.DEVOLUCAO_SOLICITADA):
        raise ErroApi(409, f"Não é possível mudar o pedido de {atual} para {novo}.")

    momento = regras.agora()
    if novo == regras.DEVOLUCAO_SOLICITADA:
        if not regras.devolucao_no_prazo(pedido, momento):
            raise ErroApi(409, "O prazo de 7 dias para devolução terminou.")
        campos = {"devolucao": {"motivo": motivo}}
    elif atual == AGUARDANDO_PAGAMENTO:
        campos = None
    else:
        campos = {"reembolso": regras.reembolso(pedido, momento)}

    atualizado = repositorio_pedidos.mudar_status(usuario_id, pedido["_id"], atual, novo, momento, campos)
    if atualizado is None:
        atual = repositorio_pedidos.obter(usuario_id, pedido["_id"])["status"]
        raise ErroApi(409, f"Não é possível mudar o pedido de {atual} para {novo}.")

    if novo == regras.CANCELADO:
        if atual == AGUARDANDO_PAGAMENTO:
            repositorio_contrato.mudar_status_solicitacao(usuario_id, atualizado["solicitacao_id"],
                                                          repositorio_contrato.APROVADA,
                                                          repositorio_contrato.EXPIRADA)
        auditar(usuario_id, "pedido_cancelado", "pedido", atualizado["_id"])
    else:
        auditar(usuario_id, "devolucao_solicitada", "pedido", atualizado["_id"])
    return atualizado


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
