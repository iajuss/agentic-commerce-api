"""Trilha de auditoria só de inserção: GET /auditoria."""

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request

from app.auditoria import repositorio
from app.auditoria.registro import registrar_evento
from app.autenticacao.identidade import usuario_atual_id
from app.erros import ErroApi

bp = Blueprint("auditoria", __name__)
bp.record_once(lambda estado: estado.app.extensions.setdefault("registrar_evento", registrar_evento))


def _evento_publico(evento):
    return {
        "id": str(evento["_id"]),
        "tipo": evento["tipo"],
        "recurso": evento["recurso"],
        "dados": evento["dados"],
        "criado_em": evento["criado_em"],
    }


@bp.get("/auditoria")
def listar_eventos():
    """Lista eventos do usuário com paginação por _id."""
    texto_limite = request.args.get("limite", "50")
    try:
        limite = int(texto_limite)
    except (TypeError, ValueError):
        raise ErroApi(
            400, "Parâmetros de auditoria inválidos.", {"limite": "Use um inteiro de 1 a 100."}
        ) from None
    if not 1 <= limite <= 100:
        raise ErroApi(400, "Parâmetros de auditoria inválidos.", {"limite": "Use um inteiro de 1 a 100."})

    texto_antes = request.args.get("antes_de")
    antes_de = None
    if texto_antes is not None:
        try:
            antes_de = ObjectId(texto_antes)
        except (InvalidId, TypeError):
            raise ErroApi(400, "Parâmetros de auditoria inválidos.", {"antes_de": "Use um id válido."}) from None

    eventos = repositorio.listar(usuario_atual_id(), limite + 1, antes_de)
    proximo = str(eventos[limite - 1]["_id"]) if len(eventos) > limite else None
    return jsonify(eventos=[_evento_publico(evento) for evento in eventos[:limite]], proximo=proximo)
