"""Políticas de compra: teto por compra, categorias, lojas e nível de autonomia.

Responsável: Pessoa 1.
"""

from flask import Blueprint, jsonify, url_for
from flask_jwt_extended import jwt_required

from app.autenticacao.identidade import usuario_atual_id
from app.banco import documento_para_json, para_object_id
from app.erros import ErroApi, ler_json
from app.politicas import repositorio
from app.politicas.validacao import validar_politica

bp = Blueprint("politicas", __name__)

NAO_ENCONTRADA = "Política não encontrada."


@bp.get("/politicas")
@jwt_required()
def listar_politicas():
    politicas = repositorio.listar(usuario_atual_id())
    return jsonify([documento_para_json(politica) for politica in politicas])


@bp.post("/politicas")
@jwt_required()
def criar_politica():
    dados = validar_politica(ler_json())
    politica = repositorio.criar(usuario_atual_id(), dados)
    local = url_for(".obter_politica", politica_id=str(politica["_id"]))
    return jsonify(documento_para_json(politica)), 201, {"Location": local}


@bp.get("/politicas/<politica_id>")
@jwt_required()
def obter_politica(politica_id):
    politica = repositorio.obter(usuario_atual_id(), para_object_id(politica_id))
    if politica is None:
        raise ErroApi(404, NAO_ENCONTRADA)
    return jsonify(documento_para_json(politica))


@bp.put("/politicas/<politica_id>")
@jwt_required()
def substituir_politica(politica_id):
    dados = validar_politica(ler_json())
    politica = repositorio.substituir(usuario_atual_id(), para_object_id(politica_id), dados)
    if politica is None:
        raise ErroApi(404, NAO_ENCONTRADA)
    return jsonify(documento_para_json(politica))


@bp.delete("/politicas/<politica_id>")
@jwt_required()
def remover_politica(politica_id):
    if not repositorio.remover(usuario_atual_id(), para_object_id(politica_id)):
        raise ErroApi(404, NAO_ENCONTRADA)
    return "", 204
