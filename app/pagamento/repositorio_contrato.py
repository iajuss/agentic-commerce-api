"""Acesso, pelo contrato de integração, às coleções de outros módulos.

- `solicitacoes` (do M2): o M3 lê o documento e escreve só `status` e `atualizada_em`, sempre com o status
  esperado no filtro (seção 5 do contrato).
- `usuarios` (do M1): o M3 lê só `senha_hash`, com projeção.
"""

from app.banco import banco
from app.pagamento import regras


def obter_solicitacao(usuario_id, solicitacao_id):
    return banco()["solicitacoes"].find_one({"_id": solicitacao_id, "usuario_id": usuario_id})


def mudar_status_solicitacao(usuario_id, solicitacao_id, de, para):
    """Troca o status só se ele ainda for `de`. Devolve True se mudou."""
    mudada = banco()["solicitacoes"].find_one_and_update(
        {"_id": solicitacao_id, "usuario_id": usuario_id, "status": de},
        {"$set": {"status": para, "atualizada_em": regras.agora()}},
    )
    return mudada is not None


def senha_hash(usuario_id):
    """Hash da senha do usuário, ou None se o usuário não existir."""
    usuario = banco()["usuarios"].find_one({"_id": usuario_id}, {"senha_hash": 1})
    return usuario.get("senha_hash") if usuario else None
