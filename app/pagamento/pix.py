"""Provedor Pix simulado do MVP: gera uma cobrança claramente falsa, sem chamar nenhum banco.

O front monta o QR code a partir de `copia_e_cola`. Um provedor real (fora do MVP) trocaria só este arquivo.
"""

import secrets


def novo_txid():
    return secrets.token_hex(16)


def criar_cobranca(txid, valor, expira_em):
    """Cobrança de `valor` reais. A simulação não usa o valor, mas um provedor real precisaria dele."""
    return {
        "txid": txid,
        "copia_e_cola": f"PIX-SIMULADO-{txid}",
        "qr_code_base64": None,
        "expira_em": expira_em,
        "pago_em": None,
    }
