"""Casos de uso do pagamento, compartilhados pelas rotas e pela compra automática."""

from flask import current_app

from app.erros import ErroApi
from app.pagamento import regras, repositorio_autorizacoes, repositorio_contrato
from app.pagamento.auditoria import auditar

AGUARDANDO_APROVACAO = "aguardando_aprovacao"
APROVADA = "aprovada"


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
