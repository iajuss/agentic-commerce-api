"""Padrão de erros da API: toda falha vira JSON no formato {"erro": "...", "detalhes": {...}}.

O campo "erro" traz uma mensagem pronta para mostrar ao usuário; "detalhes" só
aparece quando há algo a mais, como os campos inválidos de um formulário.
"""

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

MENSAGENS_HTTP = {
    400: "Requisição inválida.",
    401: "Faça login para continuar.",
    403: "Acesso negado.",
    404: "Recurso não encontrado.",
    405: "Método não permitido nesta rota.",
    415: "Envie o corpo da requisição em JSON.",
}


class ErroApi(Exception):
    """Lance em qualquer rota para responder com erro: raise ErroApi(404, "Política não encontrada.")."""

    def __init__(self, status, mensagem, detalhes=None):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem
        self.detalhes = detalhes


def resposta_erro(status, mensagem, detalhes=None):
    corpo = {"erro": mensagem}
    if detalhes:
        corpo["detalhes"] = detalhes
    return jsonify(corpo), status


def ler_json():
    """Devolve o corpo da requisição como dicionário ou responde 400."""
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        raise ErroApi(400, "O corpo da requisição deve ser um objeto JSON.")
    return corpo


def registrar_tratadores(app, jwt):
    @app.errorhandler(ErroApi)
    def erro_api(erro):
        return resposta_erro(erro.status, erro.mensagem, erro.detalhes)

    @app.errorhandler(HTTPException)
    def erro_http(erro):
        return resposta_erro(erro.code, MENSAGENS_HTTP.get(erro.code, erro.name))

    @app.errorhandler(Exception)
    def erro_inesperado(erro):
        app.logger.exception("Erro não tratado")
        return resposta_erro(500, "Erro interno do servidor.")

    # Falhas de token do flask-jwt-extended, no mesmo formato das demais.
    @jwt.unauthorized_loader
    def token_ausente(motivo):
        return resposta_erro(401, "Faça login para continuar.")

    @jwt.invalid_token_loader
    def token_invalido(motivo):
        return resposta_erro(401, "Sessão inválida. Faça login novamente.")

    @jwt.expired_token_loader
    def token_expirado(cabecalho, conteudo):
        return resposta_erro(401, "Sessão expirada. Faça login novamente.")
