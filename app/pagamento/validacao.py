"""Validação dos corpos das rotas de pagamento."""

from app.erros import ErroApi


def validar_aprovacao(corpo):
    """Senha de POST /solicitacoes/<id>/autorizacoes, ou 400 se não for um texto preenchido."""
    senha = corpo.get("senha")
    if not isinstance(senha, str) or not senha:
        raise ErroApi(400, "Aprovação inválida.", {"senha": "Informe a senha."})
    return senha


def validar_pedido(corpo):
    """`autorizacao_id` de POST /pedidos, ou 400."""
    return _texto_obrigatorio(corpo, "autorizacao_id", "Pedido inválido.", "Informe a autorização.")


def validar_pagamento_simulado(corpo):
    """`txid` de POST /simulador-pix/pagamentos, ou 400."""
    return _texto_obrigatorio(corpo, "txid", "Pagamento inválido.", "Informe o txid da cobrança Pix.")


def _texto_obrigatorio(corpo, campo, mensagem, problema):
    valor = corpo.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ErroApi(400, mensagem, {campo: problema})
    return valor.strip()
