"""Validação de cadastro, login e campos editáveis do perfil."""

import math
import re
from datetime import date, datetime, timezone

from app.erros import ErroApi

FORMATO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CAMPOS_DE_MARCAS = ("marcas_preferidas", "marcas_evitadas")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_cadastro(dados):
    erros = {}

    nome = dados.get("nome")
    if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > 80:
        erros["nome"] = "Informe um nome de até 80 caracteres."

    email = dados.get("email")
    if not isinstance(email, str) or len(email.strip()) > 254 or not EMAIL.fullmatch(email.strip()):
        erros["email"] = "Informe um e-mail válido."

    senha = dados.get("senha")
    if not isinstance(senha, str) or not 8 <= len(senha) <= 128:
        erros["senha"] = "Use uma senha de 8 a 128 caracteres."

    if erros:
        raise ErroApi(400, "Dados de cadastro inválidos.", erros)

    return nome.strip(), email.strip().lower(), senha


def validar_login(dados):
    email = dados.get("email")
    senha = dados.get("senha")
    if not isinstance(email, str) or not isinstance(senha, str):
        raise ErroApi(401, "E-mail ou senha inválidos.")

    return email.strip().lower(), senha


def _data_no_passado(valor):
    if not isinstance(valor, str) or not FORMATO_DATA.fullmatch(valor):
        return False
    try:
        return date.fromisoformat(valor) < datetime.now(timezone.utc).date()
    except ValueError:
        return False


def _lista_de_marcas(valor):
    if not isinstance(valor, list) or not all(isinstance(item, str) for item in valor):
        return None
    return list(dict.fromkeys(item.strip().lower() for item in valor if item.strip()))


def validar_perfil(corpo):
    """Devolve só os campos reconhecidos ou aponta todos os erros encontrados."""
    campos = {}
    erros = {}

    if "nome" in corpo:
        nome = corpo["nome"]
        if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 80:
            erros["nome"] = "Informe um nome de até 80 caracteres."
        else:
            campos["nome"] = nome.strip()

    if "data_nascimento" in corpo:
        nascimento = corpo["data_nascimento"]
        if not _data_no_passado(nascimento):
            erros["data_nascimento"] = "Informe uma data no formato AAAA-MM-DD, anterior a hoje."
        else:
            campos["data_nascimento"] = nascimento

    if "endereco" in corpo:
        endereco = corpo["endereco"]
        if not isinstance(endereco, dict):
            erros["endereco"] = "Informe um objeto de endereço."
        else:
            validado = {}
            if "cep" in endereco:
                cep = endereco["cep"]
                cep_limpo = re.sub(r"\D", "", cep) if isinstance(cep, str) else ""
                if len(cep_limpo) != 8:
                    erros["endereco.cep"] = "Informe um CEP com 8 dígitos."
                else:
                    validado["cep"] = cep_limpo

            if "numero" in endereco:
                numero = endereco["numero"]
                if not isinstance(numero, str) or not 1 <= len(numero.strip()) <= 20:
                    erros["endereco.numero"] = "Informe um número de até 20 caracteres."
                else:
                    validado["numero"] = numero.strip()

            if "complemento" in endereco:
                complemento = endereco["complemento"]
                if not isinstance(complemento, str) or len(complemento.strip()) > 60:
                    erros["endereco.complemento"] = "Use no máximo 60 caracteres."
                else:
                    validado["complemento"] = complemento.strip()

            if validado:
                campos["endereco"] = validado

    if "preferencias" in corpo:
        preferencias = corpo["preferencias"]
        if not isinstance(preferencias, dict):
            erros["preferencias"] = "Informe um objeto de preferências."
        else:
            validado = {}
            for chave in CAMPOS_DE_MARCAS:
                if chave in preferencias:
                    marcas = _lista_de_marcas(preferencias[chave])
                    if marcas is None:
                        erros[f"preferencias.{chave}"] = "Informe uma lista de textos."
                    else:
                        validado[chave] = marcas
            if validado:
                campos["preferencias"] = validado

    if "orcamento_mensal" in corpo:
        orcamento = corpo["orcamento_mensal"]
        if orcamento is None:
            campos["orcamento_mensal"] = None
        elif (
            isinstance(orcamento, (int, float))
            and not isinstance(orcamento, bool)
            and math.isfinite(orcamento)
            and round(float(orcamento), 2) > 0
        ):
            campos["orcamento_mensal"] = round(float(orcamento), 2)
        else:
            erros["orcamento_mensal"] = "Informe um valor maior que zero ou null."

    if erros:
        raise ErroApi(400, "Perfil inválido.", erros)
    return campos
