"""Ranking explicável das ofertas de um item da lista de compras.

Cada critério vira uma nota de 0 a 1:
- preço: proporcional ao menor preço do conjunto (menor / preço), para que centavos de diferença não pesem
  como a escala inteira; é o preço por kg/L/un na unidade da maioria das ofertas, contando só o que atende ao
  pedido ("2 leites" numa caixa 12x1L pagam 12 L para usar 2), e a oferta sem essa medida (como as da DummyJSON)
  recebe a nota neutra; sem nenhuma medida, vale o preço da embalagem;
- frete e prazo: posição entre o menor e o maior valor do conjunto; frete não informado conta como
  FRETE_ESTIMADO, o mesmo valor que a cesta cobra, e prazo não informado recebe a nota neutra;
- avaliação: nota da loja dividida por 5 (sem avaliação, nota neutra), para que 4,1 contra 4,8 não vire
  0 contra 1.

A pontuação é a soma ponderada das notas, mais os bônus de marca e de embalagem igual à pedida. A explicação
traz as frases que o front mostra.

Desvios do plano (M2-06), escolhidos de propósito: a normalização do preço e da avaliação acima, a comparação
pela unidade da maioria e só do que atende ao pedido, o frete estimado em vez da nota neutra e o
BONUS_EMBALAGEM_PEDIDA, que o plano não previa.
"""

from collections import Counter, namedtuple

from app.solicitacoes.medidas import (NOMES_EXIBIDOS, embalagens_necessarias, extrair_medida, formatar_medida,
                                      quantidade_aproveitada)

# Valor usado no critério de preço e, quando ele é por unidade, quanto da compra atende ao pedido.
Comparacao = namedtuple("Comparacao", "preco aproveitada comprada")
SEM_COMPARACAO = Comparacao(None, None, None)

PESO_PRECO = 0.50  # preço por kg/L/un na unidade da maioria das ofertas; sem nenhuma medida, o preço
PESO_FRETE = 0.20
PESO_PRAZO = 0.15
PESO_AVALIACAO = 0.15
BONUS_MARCA_PREFERIDA = 0.10
PENALIDADE_MARCA_EVITADA = 0.20
BONUS_EMBALAGEM_PEDIDA = 0.15  # "arroz 5kg" prefere a embalagem de 5 kg
NOTA_NEUTRA = 0.5
FRETE_ESTIMADO = 15.0  # usado quando a loja não informa o frete


def ranquear(ofertas, preferencias=None, quantidade=1, descricao="", frete_estimado=FRETE_ESTIMADO):
    """Cópias das ofertas, da melhor para a pior, com pontuacao, explicacao, preco_por_unidade e unidade.

    `quantidade` e `descricao` são as do item da lista de compras: a embalagem igual à medida pedida ganha bônus,
    e o que a embalagem tem além do pedido não barateia o preço por unidade (medidas.quantidade_aproveitada).
    """
    if not ofertas:
        return []

    preferencias = preferencias or {}
    preferidas = {_marca(marca) for marca in preferencias.get("marcas_preferidas") or []}
    evitadas = {_marca(marca) for marca in preferencias.get("marcas_evitadas") or []}
    medida_pedida = extrair_medida(descricao)

    medidas = [extrair_medida(oferta["titulo"]) for oferta in ofertas]
    unidade = _unidade_mais_comum(medidas)
    comparacoes = [_comparar(oferta, medida, unidade, quantidade, descricao)
                   for oferta, medida in zip(ofertas, medidas)]
    precos = [comparacao.preco for comparacao in comparacoes]

    notas_preco = _notas_proporcionais(precos)
    notas_frete = _notas_entre_extremos([_frete_efetivo(oferta, frete_estimado) for oferta in ofertas])
    notas_prazo = _notas_entre_extremos([oferta.get("prazo_dias") for oferta in ofertas])
    notas_avaliacao = [_nota_avaliacao(oferta.get("avaliacao")) for oferta in ofertas]

    ranqueadas = []
    for indice, (oferta, medida) in enumerate(zip(ofertas, medidas)):
        pontuacao = (PESO_PRECO * notas_preco[indice] + PESO_FRETE * notas_frete[indice]
                     + PESO_PRAZO * notas_prazo[indice] + PESO_AVALIACAO * notas_avaliacao[indice])
        explicacao = [_frase_preco(oferta["preco"], comparacoes[indice], precos, unidade)]
        explicacao += _frases_entrega(oferta)

        marca = _marca(oferta.get("marca"))
        if marca and marca in preferidas:
            pontuacao += BONUS_MARCA_PREFERIDA
            explicacao.append("Marca preferida")
        elif marca and marca in evitadas:
            pontuacao -= PENALIDADE_MARCA_EVITADA
            explicacao.append("Marca que você prefere evitar")

        if medida_pedida and medida == medida_pedida:
            pontuacao += BONUS_EMBALAGEM_PEDIDA
            explicacao.append(f"Embalagem igual à pedida ({formatar_medida(medida_pedida)})")

        ranqueadas.append({
            **oferta,
            "preco_por_unidade": round(oferta["preco"] / medida["quantidade"], 2) if medida else None,
            "unidade": medida["unidade"] if medida else None,
            "pontuacao": round(pontuacao, 4),
            "explicacao": explicacao,
        })

    return sorted(ranqueadas, key=lambda oferta: (-oferta["pontuacao"], oferta["preco"], oferta["id_externo"]))


def _unidade_mais_comum(medidas):
    """Unidade em que o preço é comparado (no empate, a primeira em ordem alfabética); None sem nenhuma medida."""
    contagem = Counter(medida["unidade"] for medida in medidas if medida)
    if not contagem:
        return None
    return min(contagem, key=lambda unidade: (-contagem[unidade], unidade))


def _comparar(oferta, medida, unidade, quantidade, descricao):
    """Comparacao da oferta: o preço por unidade do que atende ao pedido.

    Sem medida na unidade comparada, o preço fica None (nota neutra); sem nenhuma medida no conjunto, vale o preço
    da embalagem.
    """
    if unidade is None:
        return Comparacao(oferta["preco"], None, None)
    if medida is None or medida["unidade"] != unidade:
        return SEM_COMPARACAO
    embalagens, _ = embalagens_necessarias(quantidade, descricao, oferta["titulo"])
    aproveitada = quantidade_aproveitada(quantidade, descricao, oferta["titulo"])
    comprada = round(embalagens * medida["quantidade"], 3)
    return Comparacao(oferta["preco"] * embalagens / aproveitada, aproveitada, comprada)


def _frete_efetivo(oferta, frete_estimado):
    if oferta.get("frete_gratis"):
        return 0.0
    return oferta["frete"] if oferta.get("frete") is not None else frete_estimado


def _notas_proporcionais(precos):
    """1 para o menor preço; os demais, menor / preço; preço sem comparação (None) = nota neutra.

    Há sempre ao menos um preço conhecido, e os preços do contrato são sempre positivos.
    """
    menor = min(preco for preco in precos if preco is not None)
    return [NOTA_NEUTRA if preco is None else menor / preco for preco in precos]


def _notas_entre_extremos(valores):
    """Menor valor = 1, maior = 0 (quanto menor, melhor); todos iguais = 1; valor ausente = nota neutra."""
    conhecidos = [valor for valor in valores if valor is not None]
    if not conhecidos:
        return [NOTA_NEUTRA] * len(valores)

    menor, maior = min(conhecidos), max(conhecidos)
    notas = []
    for valor in valores:
        if valor is None:
            notas.append(NOTA_NEUTRA)
        elif maior == menor:
            notas.append(1.0)
        else:
            notas.append((maior - valor) / (maior - menor))
    return notas


def _nota_avaliacao(avaliacao):
    if avaliacao is None:
        return NOTA_NEUTRA
    return min(max(avaliacao / 5, 0.0), 1.0)


def _frase_preco(preco, comparacao, comparados, unidade):
    """Frase do critério de preço; `comparacao.preco` é o valor usado na nota (por unidade ou o preço)."""
    conhecidos = [valor for valor in comparados if valor is not None]
    if unidade is None:
        if len(conhecidos) == 1:
            return f"Única oferta encontrada: {_reais(preco)}"
        if comparacao.preco == min(conhecidos):
            return f"Menor preço entre {len(conhecidos)} ofertas: {_reais(preco)}"
        return f"Preço: {_reais(preco)}"

    nome = NOMES_EXIBIDOS[unidade]
    if comparacao.preco is None:
        return f"Preço: {_reais(preco)} (embalagem sem medida em {nome})"
    valor = f"{_reais(comparacao.preco)}/{nome}"
    if len(conhecidos) > 1 and comparacao.preco == min(conhecidos):
        frase = f"Menor preço por {nome} entre {len(conhecidos)} ofertas: {valor}"
    else:
        frase = f"Preço por {nome}: {valor}"
    if comparacao.aproveitada < comparacao.comprada:
        usada = formatar_medida({"quantidade": comparacao.aproveitada, "unidade": unidade})
        total = formatar_medida({"quantidade": comparacao.comprada, "unidade": unidade})
        frase += f" (o pedido usa {usada} de {total})"
    return frase


def _frases_entrega(oferta):
    frases = []
    if oferta.get("frete_gratis"):
        frases.append("Frete grátis")
    elif oferta.get("frete") is None:
        frases.append("Frete estimado (a loja não informou)")
    else:
        frases.append(f"Frete de {_reais(oferta['frete'])}")

    prazo = oferta.get("prazo_dias")
    if prazo is not None:
        frases.append(f"Entrega estimada em {prazo} {'dia' if prazo == 1 else 'dias'}")

    avaliacao = oferta.get("avaliacao")
    if avaliacao is not None:
        frases.append(f"Avaliação {avaliacao:.1f}".replace(".", ","))
    return frases


def _marca(marca):
    return (marca or "").strip().lower()


def _reais(valor):
    return f"R$ {valor:.2f}".replace(".", ",")
