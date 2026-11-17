"""Registro de eventos sem credenciais ou dados sensíveis."""

from datetime import datetime, timezone

from app.auditoria import repositorio

# Pedaços de nome de campo que nunca entram na trilha. A comparação é por substring e sem
# diferenciar maiúsculas, então "senha_nova", "access_token" e "COPIA_E_COLA" também ficam de fora.
FRAGMENTOS_SENSIVEIS = (
    "senha",
    "token",
    "secret",
    "segredo",
    "credencial",
    "authorization",
    "copia_e_cola",
    "qr_code",
    "cartao",
    "cvv",
    "cpf",
)


def agora():
    return datetime.now(timezone.utc)


def chave_sensivel(chave):
    """Diz se o nome do campo tem algum fragmento que não pode ir para a trilha."""
    if not isinstance(chave, str):
        return False
    normalizada = chave.strip().lower()
    return any(fragmento in normalizada for fragmento in FRAGMENTOS_SENSIVEIS)


def _sem_dados_sensiveis(valor):
    if isinstance(valor, dict):
        return {
            chave: _sem_dados_sensiveis(item)
            for chave, item in valor.items()
            if not chave_sensivel(chave)
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
