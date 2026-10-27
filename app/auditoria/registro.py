"""Registro de eventos sem credenciais ou dados sensíveis."""

from datetime import datetime, timezone

from app.auditoria import repositorio

CHAVES_SENSIVEIS = frozenset({"senha", "senha_hash", "token", "copia_e_cola"})


def agora():
    return datetime.now(timezone.utc)


def _sem_dados_sensiveis(valor):
    if isinstance(valor, dict):
        return {
            chave: _sem_dados_sensiveis(item)
            for chave, item in valor.items()
            if chave not in CHAVES_SENSIVEIS
        }
    if isinstance(valor, list):
        return [_sem_dados_sensiveis(item) for item in valor]
    return valor


def registrar_evento(usuario_id, tipo, recurso_tipo=None, recurso_id=None, dados=None):
    """Grava um evento na trilha de auditoria (só inserção)."""
    evento = {
        "usuario_id": usuario_id,
        "tipo": tipo,
        "recurso": {"tipo": recurso_tipo, "id": str(recurso_id) if recurso_id is not None else None},
        "dados": _sem_dados_sensiveis(dados or {}),
        "criado_em": agora(),
    }
    return repositorio.inserir(evento)
