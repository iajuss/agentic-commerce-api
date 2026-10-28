"""Ranking explicável das ofertas de um item da lista de compras.

Cada critério vira uma nota de 0 a 1:
- preço: proporcional ao menor preço do conjunto (menor / preço), para que centavos de diferença não pesem
  como a escala inteira; é o preço por kg/L/un quando todas as ofertas têm a mesma unidade, senão o preço;
- frete e prazo: posição entre o menor e o maior valor do conjunto; frete não informado conta como
  FRETE_ESTIMADO, o mesmo valor que a cesta cobra, e prazo não informado recebe a nota neutra;
- avaliação: nota da loja dividida por 5 (sem avaliação, nota neutra), para que 4,1 contra 4,8 não vire
  0 contra 1.

A pontuação é a soma ponderada das notas, mais os bônus de marca e de embalagem igual à pedida. A explicação
traz as frases que o front mostra.

Desvios do plano (M2-06), escolhidos de propósito: a normalização do preço e da avaliação acima, o frete
estimado em vez da nota neutra e o BONUS_EMBALAGEM_PEDIDA, que o plano não previa.
"""

from app.solicitacoes.medidas import NOMES_EXIBIDOS, extrair_medida, formatar_medida

PESO_PRECO = 0.50  # preço por kg/L/un quando todas as ofertas têm a mesma unidade; senão, o preço
PESO_FRETE = 0.20
PESO_PRAZO = 0.15
PESO_AVALIACAO = 0.15
BONUS_MARCA_PREFERIDA = 0.10
PENALIDADE_MARCA_EVITADA = 0.20
BONUS_EMBALAGEM_PEDIDA = 0.15  # "arroz 5kg" prefere a embalagem de 5 kg
NOTA_NEUTRA = 0.5
FRETE_ESTIMADO = 15.0  # usado quando a loja não informa o frete


def ranquear(ofertas, preferencias=None, medida_pedida=None, frete_estimado=FRETE_ESTIMADO):
    """Cópias das ofertas, da melhor para a pior, com pontuacao, explicacao, preco_por_unidade e unidade."""
    if not ofertas:
        return []

    preferencias = preferencias or {}
    preferidas = {_marca(marca) for marca in preferencias.get("marcas_preferidas") or []}
    evitadas = {_marca(marca) for marca in preferencias.get("marcas_evitadas") or []}

    medidas = [extrair_medida(oferta["titulo"]) for oferta in ofertas]
    unidades = {medida["unidade"] if medida else None for medida in medidas}
    por_unidade = None not in unidades and len(unidades) == 1
    precos = [_preco_comparado(oferta, medida, por_unidade) for oferta, medida in zip(ofertas, medidas)]

    notas_preco = _notas_proporcionais(precos)
    notas_frete = _notas_entre_extremos([_frete_efetivo(oferta, frete_estimado) for oferta in ofertas])
    notas_prazo = _notas_entre_extremos([oferta.get("prazo_dias") for oferta in ofertas])
    notas_avaliacao = [_nota_avaliacao(oferta.get("avaliacao")) for oferta in ofertas]

    ranqueadas = []
    for indice, (oferta, medida) in enumerate(zip(ofertas, medidas)):
        pontuacao = (PESO_PRECO * notas_preco[indice] + PESO_FRETE * notas_frete[indice]
                     + PESO_PRAZO * notas_prazo[indice] + PESO_AVALIACAO * notas_avaliacao[indice])
        explicacao = [_frase_preco(precos[indice], precos, medida if por_unidade else None)]
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


def _preco_comparado(oferta, medida, por_unidade):
    return oferta["preco"] / medida["quantidade"] if por_unidade else oferta["preco"]


def _frete_efetivo(oferta, frete_estimado):
    if oferta.get("frete_gratis"):
        return 0.0
    return oferta["frete"] if oferta.get("frete") is not None else frete_estimado


def _notas_proporcionais(precos):
    """1 para o menor preço; os demais, menor / preço (os preços do contrato são sempre positivos)."""
    menor = min(precos)
    return [menor / preco for preco in precos]


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


def _frase_preco(preco, precos, medida):
    quantidade = len(precos)
    if medida:
        unidade = NOMES_EXIBIDOS[medida["unidade"]]
        valor = f"{_reais(preco)}/{unidade}"
        if quantidade > 1 and preco == min(precos):
            return f"Menor preço por {unidade} entre {quantidade} ofertas: {valor}"
        return f"Preço por {unidade}: {valor}"
    if quantidade == 1:
        return f"Única oferta encontrada: {_reais(preco)}"
    if preco == min(precos):
        return f"Menor preço entre {quantidade} ofertas: {_reais(preco)}"
    return f"Preço: {_reais(preco)}"


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
