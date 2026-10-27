"""Acesso à coleção `solicitacoes` e leitura, por contrato, do perfil em `usuarios`.

Toda consulta filtra pelo dono. Do perfil, o M2 lê só os campos que o contrato de integração libera
(data_nascimento, preferencias e orcamento_mensal); campo ausente significa "não informado".
"""

from datetime import datetime, timezone

from app.banco import banco

AGUARDANDO_APROVACAO = "aguardando_aprovacao"
SEM_RESULTADO = "sem_resultado"
STATUS_CANCELAVEIS = (AGUARDANDO_APROVACAO, SEM_RESULTADO)
CAMPOS_DO_PERFIL = {"data_nascimento": 1, "preferencias": 1, "orcamento_mensal": 1}
COMPRA_AUTOMATICA_FALHOU = "Não foi possível concluir a compra automática; aprove manualmente."


def _colecao():
    return banco()["solicitacoes"]


def _agora():
    return datetime.now(timezone.utc)


def criar(documento):
    agora = _agora()
    solicitacao = {**documento, "criada_em": agora, "atualizada_em": agora}
    _colecao().insert_one(solicitacao)  # o insert_one preenche solicitacao["_id"]
    return solicitacao


def listar(usuario_id):
    """Mais recentes primeiro; o _id desempata solicitações criadas no mesmo instante."""
    return list(_colecao().find({"usuario_id": usuario_id}).sort([("criada_em", -1), ("_id", -1)]))


def obter(usuario_id, solicitacao_id):
    return _colecao().find_one({"_id": solicitacao_id, "usuario_id": usuario_id})


def remover_se_cancelavel(usuario_id, solicitacao_id):
    """Remove só antes da aprovação. Devolve "removida", "inexistente" ou "nao_cancelavel"."""
    filtro = {"_id": solicitacao_id, "usuario_id": usuario_id, "status": {"$in": list(STATUS_CANCELAVEIS)}}
    if _colecao().delete_one(filtro).deleted_count == 1:
        return "removida"
    return "nao_cancelavel" if obter(usuario_id, solicitacao_id) else "inexistente"


def registrar_compra_automatica(usuario_id, solicitacao_id, resultado):
    """Grava o retorno do gancho compra_automatica; sem resultado, explica nos motivos que é preciso aprovar."""
    mudanca = {"$set": {"compra_automatica": resultado or None, "atualizada_em": _agora()}}
    if not resultado:
        mudanca["$push"] = {"avaliacao.motivos": COMPRA_AUTOMATICA_FALHOU}
    _colecao().update_one({"_id": solicitacao_id, "usuario_id": usuario_id}, mudanca)


def perfil_do_usuario(usuario_id):
    """Campos do perfil liberados ao M2; usuário sem documento devolve {} (nada informado)."""
    return banco()["usuarios"].find_one({"_id": usuario_id}, CAMPOS_DO_PERFIL) or {}
