"""Trilha de auditoria só de inserção: GET /auditoria."""

import re

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request

from app.auditoria import repositorio
from app.auditoria.registro import registrar_evento
from app.autenticacao.identidade import usuario_atual_id
from app.erros import ErroApi

bp = Blueprint("auditoria", __name__)
bp.record_once(lambda estado: estado.app.extensions.setdefault("registrar_evento", registrar_evento))

PARAMETROS_INVALIDOS = "Parâmetros de auditoria inválidos."
# Os tipos de evento do contrato são snake_case (ex.: solicitacao_criada).
TIPO = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def _evento_publico(evento):
    return {
        "id": str(evento["_id"]),
        "tipo": evento["tipo"],
        "recurso": evento["recurso"],
        "dados": evento["dados"],
        "criado_em": evento["criado_em"],
    }


def _erro_de_parametro(campo, detalhe):
    return ErroApi(400, PARAMETROS_INVALIDOS, {campo: detalhe})


def _limite(texto):
    try:
        limite = int(texto)
    except (TypeError, ValueError):
        raise _erro_de_parametro("limite", "Use um inteiro de 1 a 100.") from None
    if not 1 <= limite <= 100:
        raise _erro_de_parametro("limite", "Use um inteiro de 1 a 100.")
    return limite


def _antes_de(texto):
    if texto is None:
        return None
    try:
        return ObjectId(texto)
    except (InvalidId, TypeError):
        raise _erro_de_parametro("antes_de", "Use um id válido.") from None


def _tipo(texto):
    if texto is None:
        return None
    if not TIPO.fullmatch(texto):
        raise _erro_de_parametro("tipo", "Use um tipo de evento, como solicitacao_criada.")
    return texto


@bp.get("/auditoria")
def listar_eventos():
    """Lista eventos do usuário com paginação por _id e filtro opcional por tipo."""
    limite = _limite(request.args.get("limite", "50"))
    antes_de = _antes_de(request.args.get("antes_de"))
    tipo = _tipo(request.args.get("tipo"))

    eventos = repositorio.listar(usuario_atual_id(), limite + 1, antes_de, tipo)
    proximo = str(eventos[limite - 1]["_id"]) if len(eventos) > limite else None
    return jsonify(eventos=[_evento_publico(evento) for evento in eventos[:limite]], proximo=proximo)
