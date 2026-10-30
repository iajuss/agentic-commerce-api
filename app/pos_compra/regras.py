"""Regras puras do pós-compra (estados do pedido, cancelamento e devolução), sem Flask nem banco.

`agora()` é a única fonte de data do módulo; os testes a trocam por `monkeypatch` para simular a
passagem do tempo.
"""

from datetime import datetime, timezone


def agora():
    return datetime.now(timezone.utc)
