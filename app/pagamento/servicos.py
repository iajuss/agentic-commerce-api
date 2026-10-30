"""Casos de uso do pagamento, compartilhados pelas rotas e pela compra automática."""

from datetime import timedelta

from flask import current_app

from app.erros import ErroApi
from app.pagamento import pix, regras, repositorio_autorizacoes, repositorio_contrato, repositorio_pedidos
from app.pagamento.auditoria import auditar
from app.pagamento.repositorio_contrato import AGUARDANDO_APROVACAO, APROVADA, CONCLUIDA
from app.pos_compra import servicos as servicos_pos_compra
from app.pos_compra.regras import EXPIRADO


def emitir_autorizacao(usuario_id, solicitacao, origem):
    """Aprova a solicitação e emite a autorização limitada.

    A troca de status é atômica: se outra aprovação chegou antes, responde 409 e nada é criado.
    """
    if not repositorio_contrato.mudar_status_solicitacao(usuario_id, solicitacao["_id"], AGUARDANDO_APROVACAO,
                                                         APROVADA):
        raise ErroApi(409, "Esta solicitação não está aguardando aprovação.")

    validade = int(current_app.config.get("AUTORIZACAO_VALIDADE_MINUTOS", 15))
    autorizacao = repositorio_autorizacoes.criar(
        regras.montar_autorizacao(solicitacao, origem, regras.agora(), validade)
    )
    auditar(usuario_id, "autorizacao_emitida", "autorizacao", autorizacao["_id"], {"origem": origem})
    return autorizacao


def revogar_autorizacao(usuario_id, autorizacao_id):
    """Revoga a autorização ativa e devolve a solicitação para aprovação. Revogar de novo não faz nada."""
    revogada = repositorio_autorizacoes.revogar(usuario_id, autorizacao_id, regras.agora())
    if revogada is None:
        autorizacao = repositorio_autorizacoes.obter(usuario_id, autorizacao_id)
        if autorizacao is None:
            raise ErroApi(404, "Autorização não encontrada.")
        if autorizacao["status"] == repositorio_autorizacoes.USADA:
            raise ErroApi(409, "Esta autorização já foi usada em um pedido.")
        return  # já estava revogada

    repositorio_contrato.mudar_status_solicitacao(usuario_id, revogada["solicitacao_id"], APROVADA,
                                                  AGUARDANDO_APROVACAO)
    auditar(usuario_id, "autorizacao_revogada", "autorizacao", autorizacao_id)


def consumir_autorizacao(usuario_id, autorizacao_id):
    """Marca a autorização como usada (uso único) e a devolve.

    404 se não existe ou é de outro usuário; 409 se venceu, foi revogada ou já foi usada.
    """
    autorizacao = repositorio_autorizacoes.consumir(usuario_id, autorizacao_id, regras.agora())
    if autorizacao is None:
        if repositorio_autorizacoes.obter(usuario_id, autorizacao_id) is None:
            raise ErroApi(404, "Autorização não encontrada.")
        raise ErroApi(409, "Autorização expirada, revogada ou já usada.")
    return autorizacao


def criar_pedido(usuario_id, autorizacao):
    """Cria o pedido da autorização já consumida, com a cobrança Pix simulada."""
    momento = regras.agora()
    minutos = int(current_app.config.get("PIX_EXPIRACAO_MINUTOS", 30))
    expira_em = momento + timedelta(minutes=minutos)
    cobranca = pix.criar_cobranca(pix.novo_txid(), autorizacao["valor_maximo"], expira_em)
    pedido = repositorio_pedidos.criar(regras.montar_pedido(autorizacao, cobranca, momento))
    auditar(usuario_id, "pedido_criado", "pedido", pedido["_id"], {"total": pedido["total"]})
    return pedido


def confirmar_pagamento(usuario_id, txid):
    """Simula o Pix pago: o pedido vai para `pago` e a solicitação para `concluida`.

    Antes aplica as transições devidas, então um Pix vencido fica gravado como `expirado`.
    """
    pedido = repositorio_pedidos.obter_por_txid(usuario_id, txid)
    if pedido is None:
        raise ErroApi(404, "Cobrança Pix não encontrada.")
    pedido = servicos_pos_compra.aplicar_transicoes(usuario_id, pedido)
    if pedido["status"] == EXPIRADO:
        raise ErroApi(409, "Esta cobrança Pix expirou.")
    if pedido["status"] != regras.AGUARDANDO_PAGAMENTO:
        raise ErroApi(409, "Este pedido não está aguardando pagamento.")

    momento = regras.agora()
    pago = repositorio_pedidos.mudar_status(
        usuario_id, pedido["_id"], regras.AGUARDANDO_PAGAMENTO, regras.PAGO, momento,
        campos={"pix.pago_em": momento}, condicao={"pix.expira_em": {"$gt": momento}},
    )
    if pago is None:
        atual = repositorio_pedidos.obter(usuario_id, pedido["_id"])
        if atual["status"] == regras.AGUARDANDO_PAGAMENTO:
            raise ErroApi(409, "Esta cobrança Pix expirou.")
        raise ErroApi(409, "Este pedido não está aguardando pagamento.")

    repositorio_contrato.mudar_status_solicitacao(usuario_id, pago["solicitacao_id"], APROVADA, CONCLUIDA)
    auditar(usuario_id, "pagamento_confirmado", "pedido", pago["_id"], {"total": pago["total"]})
    return pago
