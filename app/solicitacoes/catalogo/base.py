"""Contrato dos catálogos de ofertas: o formato da oferta normalizada e a interface de busca.

Toda implementação devolve ofertas no formato da seção 4 de docs/plano-backend/00-contrato-de-integracao.md.
"""

import re
import unicodedata

CAMPOS_OBRIGATORIOS = ("id_externo", "fonte", "titulo", "preco", "categoria", "categorias_caminho", "loja")
CAMPOS_OPCIONAIS = ("marca", "frete", "frete_gratis", "prazo_dias", "avaliacao", "estoque", "link", "imagem")

# Palavras que não identificam o produto e ficam fora da comparação da busca. Ficam no singular, porque a
# comparação é feita depois do radical ("caixas" -> "caixa").
PALAVRAS_IGNORADAS = frozenset({
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "com", "sem", "para", "tipo",
    # embalagens ("duas caixas de leite" procura leite)
    "pacote", "caixa", "garrafa", "frasco", "pote", "saco", "bandeja", "fardo", "kit", "embalagem", "duzia",
    # medidas escritas separadas do número ("2 kg de feijão", "leite 1 litro", "6 x 350ml")
    "x", "kg", "quilo", "kilo", "g", "grama", "ml", "l", "lt", "litro", "un", "und", "unid", "unidade", "rolo",
})

# Tokens de medida ("5kg", "500g", "1,5l", "12x350ml", "12") não restringem a busca; o ranking cuida da
# embalagem.
MEDIDA = re.compile(r"^\d+(?:[.,]\d+)?(?:x\d+(?:[.,]\d+)?)?(?:kg|g|ml|l|lt|un)?$")
TOKEN = re.compile(r"[a-z0-9]+(?:[.,]\d+)?[a-z]*")

# Plurais comuns em português, do mais específico ao mais geral: "feijoes" -> "feijao", "integrais" -> "integral".
PLURAIS = (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el"), ("ois", "ol"), ("res", "r"), ("zes", "z"),
           ("ns", "m"))


class Catalogo:
    """Interface comum: buscar(termo, limite) devolve até `limite` ofertas normalizadas."""

    def buscar(self, termo, limite=10):
        raise NotImplementedError


def nova_oferta(**campos):
    """Oferta com todos os campos do contrato; os opcionais não informados ficam None."""
    oferta = {campo: None for campo in CAMPOS_OBRIGATORIOS + CAMPOS_OPCIONAIS}
    oferta.update(campos)
    return oferta


def validar_oferta(oferta):
    """Lança ValueError se a oferta não cumpre o contrato (usada nos testes de todos os catálogos)."""
    faltando = [campo for campo in CAMPOS_OBRIGATORIOS if oferta.get(campo) in (None, "", [])]
    if faltando:
        raise ValueError(f"Oferta {oferta.get('id_externo')} sem: {', '.join(faltando)}.")
    preco = oferta["preco"]
    if isinstance(preco, bool) or not isinstance(preco, (int, float)) or preco <= 0:
        raise ValueError(f"Oferta {oferta['id_externo']} com preço inválido: {preco!r}.")
    if not isinstance(oferta["categorias_caminho"], list):
        raise ValueError(f"Oferta {oferta['id_externo']}: categorias_caminho deve ser uma lista.")


def sem_acentos(texto):
    """Minúsculas, sem acentos e sem espaços nas pontas: " Feijão " -> "feijao"."""
    decomposto = unicodedata.normalize("NFKD", texto.strip().lower())
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))


def radical(palavra):
    """Forma singular aproximada, para "leites" casar com "leite" e "integrais" com "integral"."""
    for plural, singular in PLURAIS:
        if palavra.endswith(plural) and len(palavra) > len(plural) + 1:
            return palavra[: -len(plural)] + singular
    if palavra.endswith("s") and len(palavra) > 3:
        return palavra[:-1]
    return palavra


def palavras_relevantes(texto):
    """Radicais das palavras que identificam o produto, sem medidas nem palavras ignoradas."""
    tokens = TOKEN.findall(sem_acentos(texto))
    return {radical(token) for token in tokens if not MEDIDA.match(token)} - PALAVRAS_IGNORADAS
