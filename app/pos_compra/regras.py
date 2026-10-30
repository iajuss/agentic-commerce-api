"""Regras puras do pós-compra (estados do pedido, cancelamento e devolução), sem Flask nem banco.

`agora()` é a única fonte de data do módulo; os testes a trocam por `monkeypatch` para simular a
passagem do tempo.
"""

from datetime import datetime, timezone


def agora():
    """UTC com milissegundos inteiros, a precisão do BSON: a resposta e a próxima leitura mostram a mesma data."""
    momento = datetime.now(timezone.utc)
    return momento.replace(microsecond=momento.microsecond // 1000 * 1000)
