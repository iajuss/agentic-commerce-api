"""Acesso à coleção `pedidos`, usado pelo pagamento e pelo pós-compra.

Toda consulta filtra pelo dono. Toda mudança de status leva o status esperado no filtro, então duas
requisições simultâneas (ou duas leituras que aplicam a mesma transição) nunca duplicam o `historico`.
"""

from pymongo import ReturnDocument

from app.banco import banco


def _colecao():
    return banco()["pedidos"]


def criar(pedido):
    _colecao().insert_one(pedido)  # o insert_one preenche pedido["_id"]
    return pedido


def obter(usuario_id, pedido_id):
    return _colecao().find_one({"_id": pedido_id, "usuario_id": usuario_id})


def obter_por_txid(usuario_id, txid):
    return _colecao().find_one({"pix.txid": txid, "usuario_id": usuario_id})


def listar(usuario_id):
    """Mais recentes primeiro; o _id desempata os criados no mesmo instante."""
    return list(_colecao().find({"usuario_id": usuario_id}).sort([("criado_em", -1), ("_id", -1)]))


def mudar_status(usuario_id, pedido_id, de, para, momento, campos=None, condicao=None):
    """Troca o status de `de` para `para` e registra no histórico. Devolve o pedido novo ou None se nada mudou.

    `campos` são gravados junto (ex.: {"pix.pago_em": momento}); `condicao` restringe o filtro.
    """
    return _colecao().find_one_and_update(
        {**(condicao or {}), "_id": pedido_id, "usuario_id": usuario_id, "status": de},
        {
            "$set": {**(campos or {}), "status": para, "atualizado_em": momento},
            "$push": {"historico": {"status": para, "em": momento}},
        },
        return_document=ReturnDocument.AFTER,
    )
