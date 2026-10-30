"""Auxiliares dos testes do M3: usuários e solicitações gravados direto no mongomock, e ganchos isolados.

Não é coletado pelo pytest (não começa com `test_`). As fixtures daqui precisam ser importadas no arquivo de
teste: `from tests.apoio_pagamento import eventos, ganchos_isolados, relogio  # noqa: F401`.

A solicitação segue a seção 4 do contrato de integração, no mesmo formato que o M2 grava, para que os testes
do M3 não dependam do código do M2.
"""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from werkzeug.security import generate_password_hash

SENHA_PADRAO = "senha-forte-123"
GANCHOS = ("registrar_evento", "compra_automatica")


def _agora():
    return datetime.now(timezone.utc)


def inserir_usuario(app, senha=SENHA_PADRAO):
    """Grava um usuário com senha conferível por check_password_hash e devolve o ObjectId."""
    usuario_id = ObjectId()
    with app.app_context():
        app.extensions["mongo"]["usuarios"].insert_one({
            "_id": usuario_id,
            "nome": "Cliente Teste",
            "email": f"cliente-{usuario_id}@exemplo.com",
            # Hash barato só para a suíte ficar rápida; check_password_hash lê o método do próprio hash.
            "senha_hash": generate_password_hash(senha, method="pbkdf2:sha256:1000"),
            "criado_em": _agora(),
        })
    return usuario_id


def inserir_solicitacao(app, usuario_id, status="aguardando_aprovacao", permitida=True, compra_automatica=False,
                        total=33.8):
    """Grava uma solicitação com 2 itens com oferta e devolve o documento (com _id).

    Com o total padrão, a cesta bate com os itens (27,90 + 2 x 2,95, frete grátis). Outro `total` muda só a
    cesta: o M3 confia nela e não recalcula a partir dos itens.
    """
    arroz = _oferta("MLB1001", "Arroz Branco Tipo 1 5kg", 27.9, "Arroz", "Tio João", 5.58, "kg")
    leite = _oferta("MLB2002", "Leite Integral 1L", 2.95, "Leite", "Italac", 2.95, "l")
    itens = [_item("arroz 5kg", 1, arroz), _item("2 leites integrais", 2, leite)]
    total = round(total, 2)
    agora = _agora()
    solicitacao = {
        "_id": ObjectId(),
        "usuario_id": usuario_id,
        "texto": "arroz 5kg e 2 leites integrais",
        "itens": itens,
        "cesta": {"subtotal": total, "frete": 0.0, "total": total, "lojas": ["Loja Exemplo"]},
        "avaliacao": {
            "permitida": permitida,
            "compra_automatica": permitida and compra_automatica,
            "politica_id": ObjectId() if permitida else None,
            "motivos": [] if permitida else ["Mercado do mês: total de R$ 33,80 passa do teto de R$ 20,00"],
        },
        "status": status,
        "compra_automatica": None,
        "criada_em": agora,
        "atualizada_em": agora,
    }
    with app.app_context():
        app.extensions["mongo"]["solicitacoes"].insert_one(solicitacao)
    return solicitacao


def _item(descricao, quantidade, recomendada):
    return {
        "descricao": descricao,
        "quantidade": quantidade,
        "status": "com_oferta",
        "recomendada": recomendada,
        "alternativas": [],
        "descartadas": 0,
        "explicacao": ["1 oferta encontrada"],
    }


def _oferta(id_externo, titulo, preco, categoria, marca, preco_por_unidade, unidade):
    return {
        "id_externo": id_externo, "fonte": "fixo", "titulo": titulo, "preco": preco,
        "categoria": categoria, "categorias_caminho": ["Alimentos e Bebidas", categoria], "loja": "Loja Exemplo",
        "marca": marca, "frete": 0.0, "frete_gratis": True, "prazo_dias": 2, "avaliacao": 4.7, "estoque": 10,
        "link": None, "imagem": None,
        "preco_por_unidade": preco_por_unidade, "unidade": unidade, "pontuacao": 0.9,
        "explicacao": ["Menor preço entre 1 oferta"],
    }


class Relogio:
    """Hora controlada pelo teste: começa agora e só anda com avancar().

    Começa em milissegundos inteiros porque o BSON guarda datas com essa precisão; assim as datas lidas do
    banco podem ser comparadas com o relógio por igualdade.
    """

    def __init__(self):
        momento = _agora()
        self.momento = momento.replace(microsecond=momento.microsecond // 1000 * 1000)

    def __call__(self):
        return self.momento

    def avancar(self, **duracao):
        self.momento += timedelta(**duracao)


@pytest.fixture
def relogio(monkeypatch):
    """Troca o agora() do pagamento e do pós-compra pelo mesmo relógio: relogio.avancar(minutes=16)."""
    from app.pagamento import regras as regras_pagamento
    from app.pos_compra import regras as regras_pos_compra

    relogio = Relogio()
    monkeypatch.setattr(regras_pagamento, "agora", relogio)
    monkeypatch.setattr(regras_pos_compra, "agora", relogio)
    return relogio


@pytest.fixture(autouse=True)
def ganchos_isolados(app):
    """Tira os ganchos reais dos outros módulos; cada teste registra a versão falsa de que precisar."""
    for gancho in GANCHOS:
        app.extensions.pop(gancho, None)


@pytest.fixture
def eventos(app, ganchos_isolados):
    """Registra um registrar_evento falso e devolve a lista de eventos recebidos."""
    recebidos = []

    def registrar(usuario_id, tipo, recurso_tipo=None, recurso_id=None, dados=None):
        recebidos.append({"usuario_id": usuario_id, "tipo": tipo, "recurso_tipo": recurso_tipo,
                          "recurso_id": recurso_id, "dados": dados})

    app.extensions["registrar_evento"] = registrar
    return recebidos
