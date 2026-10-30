"""Eventos de auditoria do M3, enviados pelo gancho `registrar_evento` do M1 (seção 6.1 do contrato).

Sem o gancho registrado (M1 ausente ou testes), nada é gravado e a ação segue normalmente.
"""

from flask import current_app


def auditar(usuario_id, tipo, recurso_tipo=None, recurso_id=None, dados=None):
    """Registra o evento se a auditoria (M1) estiver ativa."""
    registrar = current_app.extensions.get("registrar_evento")
    if registrar is not None:
        registrar(usuario_id, tipo, recurso_tipo, recurso_id, dados)
