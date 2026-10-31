"""Consulta de endereços no ViaCEP."""

import requests
from flask import current_app

from app.erros import ErroApi

MENSAGEM_CEP = "CEP não encontrado."
MENSAGEM_INDISPONIVEL = "Serviço de CEP indisponível no momento. Tente novamente em instantes."
# Mesma chave da validação do perfil, para o erro aparecer embaixo do campo de CEP.
CAMPO_CEP = "endereco.cep"


def consultar_cep(cep):
    """Completa um CEP válido com logradouro, bairro, cidade e UF."""
    timeout = int(current_app.config.get("HTTP_TIMEOUT_SEGUNDOS", 8))
    try:
        resposta = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=timeout)
    except requests.RequestException:
        raise ErroApi(502, MENSAGEM_INDISPONIVEL) from None

    if resposta.status_code == 429:  # limite de requisições: o serviço está indisponível, o CEP pode existir
        raise ErroApi(502, MENSAGEM_INDISPONIVEL)
    if 400 <= resposta.status_code < 500:
        raise ErroApi(400, MENSAGEM_CEP, {CAMPO_CEP: "Confira o CEP."})
    if resposta.status_code != 200:
        raise ErroApi(502, MENSAGEM_INDISPONIVEL)

    try:
        dados = resposta.json()
    except ValueError:
        raise ErroApi(502, MENSAGEM_INDISPONIVEL) from None
    if not isinstance(dados, dict):
        raise ErroApi(502, MENSAGEM_INDISPONIVEL)
    if dados.get("erro") in (True, "true"):
        raise ErroApi(400, MENSAGEM_CEP, {CAMPO_CEP: "Confira o CEP."})

    campos = ("logradouro", "bairro", "localidade", "uf")
    if not all(isinstance(dados.get(campo), str) for campo in campos):
        raise ErroApi(502, MENSAGEM_INDISPONIVEL)

    return {
        "cep": cep,
        "logradouro": dados["logradouro"],
        "bairro": dados["bairro"],
        "cidade": dados["localidade"],
        "uf": dados["uf"],
    }
