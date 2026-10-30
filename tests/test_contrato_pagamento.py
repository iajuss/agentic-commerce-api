"""Contrato do M3: auxiliares de teste fiéis à seção 4, auditoria pelo gancho e datas em UTC."""

from datetime import datetime, timedelta

from bson import ObjectId
from werkzeug.security import check_password_hash

from app.pagamento import regras as regras_pagamento
from app.pagamento.auditoria import auditar
from app.pos_compra import regras as regras_pos_compra
from tests.apoio_pagamento import (  # noqa: F401
    SENHA_PADRAO,
    eventos,
    ganchos_isolados,
    inserir_solicitacao,
    inserir_usuario,
)

# Chaves da seção 4 do contrato de integração.
CHAVES_SOLICITACAO = {"_id", "usuario_id", "texto", "itens", "cesta", "avaliacao", "status", "compra_automatica",
                      "criada_em", "atualizada_em"}
CHAVES_ITEM = {"descricao", "quantidade", "status", "recomendada", "alternativas", "descartadas", "explicacao"}
CHAVES_OFERTA = {"id_externo", "fonte", "titulo", "preco", "frete", "frete_gratis", "prazo_dias", "categoria",
                 "categorias_caminho", "loja", "avaliacao", "preco_por_unidade", "unidade", "link", "imagem",
                 "pontuacao", "explicacao"}
CHAVES_EXTRAS_DO_M2 = {"marca", "estoque"}
CHAVES_CESTA = {"subtotal", "frete", "total", "lojas"}
CHAVES_AVALIACAO = {"permitida", "compra_automatica", "politica_id", "motivos"}


def test_usuario_inserido_tem_senha_conferivel(app):
    usuario_id = inserir_usuario(app)

    usuario = app.extensions["mongo"]["usuarios"].find_one({"_id": usuario_id})
    assert check_password_hash(usuario["senha_hash"], SENHA_PADRAO)
    assert not check_password_hash(usuario["senha_hash"], "outra-senha")


def test_solicitacao_inserida_tem_as_chaves_do_contrato(app):
    solicitacao = inserir_solicitacao(app, ObjectId())

    assert set(solicitacao) == CHAVES_SOLICITACAO
    assert set(solicitacao["cesta"]) == CHAVES_CESTA
    assert set(solicitacao["avaliacao"]) == CHAVES_AVALIACAO
    for item in solicitacao["itens"]:
        assert set(item) == CHAVES_ITEM
        assert item["status"] == "com_oferta"
        assert set(item["recomendada"]) == CHAVES_OFERTA | CHAVES_EXTRAS_DO_M2


def test_solicitacao_inserida_esta_gravada_com_ids_e_datas_do_banco(app):
    usuario_id = ObjectId()
    solicitacao = inserir_solicitacao(app, usuario_id)

    gravada = app.extensions["mongo"]["solicitacoes"].find_one({"_id": solicitacao["_id"]})
    assert gravada["usuario_id"] == usuario_id
    assert isinstance(gravada["avaliacao"]["politica_id"], ObjectId)
    assert gravada["criada_em"].tzinfo is not None


def test_cesta_padrao_bate_com_os_itens(app):
    solicitacao = inserir_solicitacao(app, ObjectId())

    soma = sum(item["recomendada"]["preco"] * item["quantidade"] for item in solicitacao["itens"])
    assert round(soma, 2) == solicitacao["cesta"]["total"] == 33.8


def test_solicitacao_nao_permitida_traz_motivos_e_sem_politica(app):
    solicitacao = inserir_solicitacao(app, ObjectId(), permitida=False, compra_automatica=True)

    avaliacao = solicitacao["avaliacao"]
    assert avaliacao["permitida"] is False
    assert avaliacao["compra_automatica"] is False
    assert avaliacao["politica_id"] is None
    assert avaliacao["motivos"]


def test_ganchos_reais_ficam_de_fora(app):
    assert "registrar_evento" not in app.extensions
    assert "compra_automatica" not in app.extensions


def test_auditar_repassa_o_evento_ao_gancho(app, eventos):
    usuario_id, pedido_id = ObjectId(), ObjectId()

    with app.app_context():
        auditar(usuario_id, "pedido_criado", "pedido", pedido_id, {"total": 33.8})

    assert eventos == [{"usuario_id": usuario_id, "tipo": "pedido_criado", "recurso_tipo": "pedido",
                        "recurso_id": pedido_id, "dados": {"total": 33.8}}]


def test_auditar_sem_gancho_nao_faz_nada(app):
    with app.app_context():
        auditar(ObjectId(), "pedido_criado")


def test_agora_dos_dois_modulos_e_utc():
    for modulo in (regras_pagamento, regras_pos_compra):
        momento = modulo.agora()
        assert isinstance(momento, datetime)
        assert momento.utcoffset() == timedelta(0)
