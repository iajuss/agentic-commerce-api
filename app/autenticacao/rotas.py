"""Cadastro, login e perfil: POST /usuarios, POST /sessoes, GET e PATCH /usuarios/me.

Responsável: Pessoa 2 (cadastro e login) e Pessoa 3 (perfil com ViaCEP).
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auditoria.registro import registrar_evento
from app.autenticacao import repositorio
from app.autenticacao.identidade import usuario_atual_id
from app.autenticacao.validacao import validar_cadastro, validar_login, validar_perfil
from app.autenticacao.viacep import consultar_cep
from app.erros import ErroApi, ler_json

bp = Blueprint("autenticacao", __name__)

CAMPOS_ENDERECO = ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")
HASH_SENHA_FICTICIA = generate_password_hash("senha-ficticia")


def _usuario_publico(usuario):
    return {"id": str(usuario["_id"]), "nome": usuario["nome"], "email": usuario["email"]}


@bp.post("/usuarios")
def cadastrar_usuario():
    nome, email, senha = validar_cadastro(ler_json())

    try:
        usuario = repositorio.criar(nome, email, generate_password_hash(senha))
    except DuplicateKeyError:
        raise ErroApi(409, "E-mail já cadastrado.", {"email": "Use outro e-mail."}) from None

    registrar_evento(usuario["_id"], "usuario_cadastrado", "usuario", usuario["_id"])
    return jsonify(_usuario_publico(usuario)), 201, {"Location": "/usuarios/me"}


@bp.post("/sessoes")
def criar_sessao():
    email, senha = validar_login(ler_json())
    usuario = repositorio.buscar_por_email(email)
    hash_senha = usuario["senha_hash"] if usuario is not None else HASH_SENHA_FICTICIA
    senha_correta = check_password_hash(hash_senha, senha)
    if usuario is None or not senha_correta:
        if usuario is not None:
            registrar_evento(usuario["_id"], "login_recusado", "usuario", usuario["_id"])
        raise ErroApi(401, "E-mail ou senha inválidos.")

    token = create_access_token(identity=str(usuario["_id"]))
    registrar_evento(usuario["_id"], "sessao_iniciada", "usuario", usuario["_id"])
    return jsonify(token=token, usuario=_usuario_publico(usuario))


def _perfil_publico(usuario):
    preferencias = usuario.get("preferencias") or {}
    endereco = usuario.get("endereco")
    if endereco is not None:
        endereco = {campo: endereco.get(campo) for campo in CAMPOS_ENDERECO}
    return {
        "id": str(usuario["_id"]),
        "nome": usuario["nome"],
        "email": usuario["email"],
        "data_nascimento": usuario.get("data_nascimento"),
        "endereco": endereco,
        "preferencias": {
            "marcas_preferidas": preferencias.get("marcas_preferidas", []),
            "marcas_evitadas": preferencias.get("marcas_evitadas", []),
        },
        "orcamento_mensal": usuario.get("orcamento_mensal"),
        "criado_em": usuario["criado_em"],
    }


def _endereco_atualizado(atual, alteracoes):
    existente = atual or {}
    cep = alteracoes.get("cep", existente.get("cep"))
    if cep is None:
        raise ErroApi(400, "Perfil inválido.", {"endereco.cep": "Informe um CEP."})

    endereco = consultar_cep(cep) if "cep" in alteracoes else dict(existente)
    endereco["numero"] = alteracoes.get("numero", existente.get("numero"))
    endereco["complemento"] = alteracoes.get("complemento", existente.get("complemento"))
    return endereco


def _usuario_da_sessao():
    usuario_id = usuario_atual_id()
    usuario = repositorio.obter(usuario_id)
    if usuario is None:
        raise ErroApi(401, "Sessão inválida. Faça login novamente.")
    return usuario_id, usuario


@bp.get("/usuarios/me")
def obter_perfil():
    _, usuario = _usuario_da_sessao()
    return jsonify(_perfil_publico(usuario))


@bp.patch("/usuarios/me")
def atualizar_perfil():
    usuario_id, usuario = _usuario_da_sessao()

    campos = validar_perfil(ler_json())
    if not campos:
        return jsonify(_perfil_publico(usuario))
    if "endereco" in campos:
        campos["endereco"] = _endereco_atualizado(usuario.get("endereco"), campos["endereco"])
    if "preferencias" in campos:
        campos["preferencias"] = {
            "marcas_preferidas": [],
            "marcas_evitadas": [],
            **(usuario.get("preferencias") or {}),
            **campos["preferencias"],
        }

    atualizado = repositorio.atualizar(usuario_id, campos)
    if atualizado is None:
        raise ErroApi(401, "Sessão inválida. Faça login novamente.")
    registrar_evento(usuario_id, "perfil_atualizado", "usuario", usuario_id, {"campos": sorted(campos)})
    return jsonify(_perfil_publico(atualizado))
