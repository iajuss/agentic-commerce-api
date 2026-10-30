"""Orquestrador da solicitação: lista de compras -> ofertas -> políticas -> ranking -> cesta recomendada.

`processar_solicitacao` não acessa o banco: recebe o catálogo, as políticas e o perfil e devolve o documento
da solicitação (seção 4 de docs/plano-backend/00-contrato-de-integracao.md), que a rota grava. A compra
automática é pedida ao M3 pelo gancho `compra_automatica` (seção 6.2 do contrato).
"""

from collections import Counter
from datetime import date, datetime, timezone

from flask import current_app

from app.erros import ErroApi
from app.politicas.regras import avaliar_cesta, avaliar_oferta
from app.solicitacoes.catalogo.base import sem_acentos
from app.solicitacoes.medidas import embalagens_necessarias
from app.solicitacoes.ranking import FRETE_ESTIMADO, ranquear

COM_OFERTA = "com_oferta"
SEM_OFERTA = "sem_oferta"
AGUARDANDO_APROVACAO = "aguardando_aprovacao"
SEM_RESULTADO = "sem_resultado"

LIMITE_DE_OFERTAS = 10
ALTERNATIVAS = 4
IDADE_MINIMA_ALCOOL = 18
CATEGORIAS_ALCOOLICAS = frozenset({"cervejas", "vinhos", "destilados", "bebidas alcoolicas"})

CATALOGO_INDISPONIVEL = "Catálogo indisponível no momento. Tente novamente em instantes."
CATALOGO_INDISPONIVEL_NO_ITEM = "Catálogo indisponível para este item"
MOTIVO_IDADE = "bebida alcoólica (venda só para maiores de 18 anos; confira a data de nascimento no perfil)"


def agora():
    return datetime.now(timezone.utc)


def processar_solicitacao(usuario_id, pedido, catalogo, politicas, perfil, hoje=None):
    """Documento da solicitação pronto para gravar (o repositório acrescenta _id e as datas).

    `pedido` é a saída de `validar_solicitacao`: {"texto": ..., "itens": [{descricao, quantidade}]}.
    Falha do catálogo em todos os itens responde 502; em parte deles, o item fica sem oferta.
    """
    maior_de_idade = _maior_de_idade(perfil.get("data_nascimento"), hoje or agora().date())
    preferencias = perfil.get("preferencias") or {}

    itens = []
    falhas = 0
    for item in pedido["itens"]:
        try:
            ofertas = catalogo.buscar(item["descricao"], limite=LIMITE_DE_OFERTAS)
        except ErroApi as erro:
            if erro.status != 502:
                raise
            falhas += 1
            itens.append(_item_sem_oferta(item, [CATALOGO_INDISPONIVEL_NO_ITEM], descartadas=0))
            continue
        itens.append(_processar_item(item, ofertas, politicas, preferencias, maior_de_idade))

    if falhas == len(pedido["itens"]):
        raise ErroApi(502, CATALOGO_INDISPONIVEL)

    cesta = montar_cesta(itens)
    algum_com_oferta = any(item["status"] == COM_OFERTA for item in itens)
    return {
        "usuario_id": usuario_id,
        "texto": pedido["texto"],
        "itens": itens,
        "cesta": cesta,
        "avaliacao": _avaliar(itens, cesta, politicas, perfil),
        "status": AGUARDANDO_APROVACAO if algum_com_oferta else SEM_RESULTADO,
        "compra_automatica": None,
    }


def montar_cesta(itens):
    """Soma as ofertas recomendadas; o frete é cobrado uma vez por loja."""
    escolhidos = [item for item in itens if item["status"] == COM_OFERTA]
    subtotal = round(sum(item["recomendada"]["preco"] * item["quantidade"] for item in escolhidos), 2)

    ofertas_por_loja = {}
    for item in escolhidos:
        ofertas_por_loja.setdefault(item["recomendada"]["loja"], []).append(item["recomendada"])
    frete = round(sum(_frete_da_loja(ofertas) for ofertas in ofertas_por_loja.values()), 2)

    total = round(subtotal + frete, 2)
    return {"subtotal": subtotal, "frete": frete, "total": total, "lojas": list(ofertas_por_loja)}


def pode_comprar_sozinho(solicitacao):
    """Pré-condições do contrato para chamar o gancho compra_automatica."""
    avaliacao = solicitacao["avaliacao"]
    return (
        solicitacao["status"] == AGUARDANDO_APROVACAO
        and avaliacao["permitida"]
        and avaliacao["compra_automatica"]
        and all(item["status"] == COM_OFERTA for item in solicitacao["itens"])
    )


def tentar_compra_automatica(solicitacao):
    """Chama o gancho do M3 quando possível. Devolve (tentou, resultado); sem gancho, (False, None)."""
    executar = current_app.extensions.get("compra_automatica")
    if executar is None or not pode_comprar_sozinho(solicitacao):
        return False, None
    try:
        return True, executar(solicitacao)
    except Exception:
        current_app.logger.exception("Falha na compra automática da solicitação %s", solicitacao["_id"])
        return True, None


def _processar_item(item, ofertas, politicas, preferencias, maior_de_idade):
    permitidas = []
    motivos = Counter()
    for oferta in ofertas:
        if not maior_de_idade and _eh_alcoolica(oferta):
            motivos[MOTIVO_IDADE] += 1
            continue
        embalagens, _ = embalagens_necessarias(item["quantidade"], item["descricao"], oferta["titulo"])
        avaliacao = avaliar_oferta({**oferta, "preco": oferta["preco"] * embalagens}, politicas)
        if not avaliacao.permitida:
            motivos["; ".join(avaliacao.motivos)] += 1
            continue
        permitidas.append(oferta)

    explicacao = [_contar(len(ofertas), "oferta encontrada", "ofertas encontradas")] if ofertas else []
    explicacao += [f"{_contar(total, 'descartada', 'descartadas')}: {motivo}" for motivo, total in motivos.items()]

    if not permitidas:
        if not ofertas:
            explicacao = ["Nenhuma oferta encontrada para este item"]
        else:
            explicacao.append("Nenhuma oferta permitida para este item")
        return _item_sem_oferta(item, explicacao, descartadas=len(ofertas))

    ranqueadas = ranquear(permitidas, preferencias, quantidade=item["quantidade"], descricao=item["descricao"])
    # A quantidade gravada é o número de embalagens da recomendada, que o M3 multiplica pelo preço.
    quantidade, ajuste = embalagens_necessarias(item["quantidade"], item["descricao"], ranqueadas[0]["titulo"])
    if ajuste:
        explicacao.append(ajuste)
    return {
        "descricao": item["descricao"],
        "quantidade": quantidade,
        "status": COM_OFERTA,
        "recomendada": ranqueadas[0],
        "alternativas": ranqueadas[1:1 + ALTERNATIVAS],
        "descartadas": len(ofertas) - len(permitidas),
        "explicacao": explicacao,
    }


def _item_sem_oferta(item, explicacao, descartadas):
    return {
        "descricao": item["descricao"],
        "quantidade": item["quantidade"],
        "status": SEM_OFERTA,
        "recomendada": None,
        "alternativas": [],
        "descartadas": descartadas,
        "explicacao": explicacao,
    }


def _avaliar(itens, cesta, politicas, perfil):
    escolhidos = [{"oferta": item["recomendada"], "quantidade": item["quantidade"]}
                  for item in itens if item["status"] == COM_OFERTA]
    if not escolhidos:
        return {"permitida": False, "compra_automatica": False, "politica_id": None,
                "motivos": ["Nenhum item da lista tem oferta disponível"]}

    avaliacao = avaliar_cesta(escolhidos, cesta["frete"], politicas)
    resultado = {
        "permitida": avaliacao.permitida,
        "compra_automatica": avaliacao.compra_automatica,
        "politica_id": avaliacao.politica_id,
        "motivos": list(avaliacao.motivos),
    }

    orcamento = perfil.get("orcamento_mensal")
    if resultado["compra_automatica"] and orcamento and cesta["total"] > orcamento:
        resultado["compra_automatica"] = False
        resultado["motivos"].append(
            f"O total de {_reais(cesta['total'])} passa do seu orçamento mensal de {_reais(orcamento)}; "
            "aprove manualmente."
        )
    return resultado


def _frete_da_loja(ofertas):
    """Grátis se todas as ofertas da loja têm frete grátis; senão, o maior frete informado ou a estimativa."""
    if all(oferta.get("frete_gratis") for oferta in ofertas):
        return 0.0
    informados = [oferta["frete"] for oferta in ofertas
                  if not oferta.get("frete_gratis") and oferta.get("frete") is not None]
    return max(informados) if informados else FRETE_ESTIMADO


def _eh_alcoolica(oferta):
    caminho = oferta.get("categorias_caminho") or [oferta["categoria"]]
    return bool({sem_acentos(categoria) for categoria in caminho} & CATEGORIAS_ALCOOLICAS)


def _maior_de_idade(data_nascimento, hoje):
    """Sem data de nascimento válida, o usuário não é tratado como maior de idade."""
    try:
        nascimento = date.fromisoformat(data_nascimento)
    except (TypeError, ValueError):
        return False
    idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
    return idade >= IDADE_MINIMA_ALCOOL


def _contar(quantidade, singular, plural):
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _reais(valor):
    return f"R$ {valor:.2f}".replace(".", ",")
