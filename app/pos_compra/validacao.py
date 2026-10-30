"""Validação dos corpos das rotas de chamados."""

from app.erros import ErroApi


def validar_chamado(corpo):
    """(assunto, mensagem) de POST /pedidos/<id>/chamados, ou 400 com cada campo inválido em `detalhes`."""
    assunto = _texto(corpo, "assunto")
    mensagem = _texto(corpo, "mensagem")
    problemas = {}
    if not 3 <= len(assunto) <= 80:
        problemas["assunto"] = "Informe o assunto, de 3 a 80 caracteres."
    if not 10 <= len(mensagem) <= 1000:
        problemas["mensagem"] = "Informe a mensagem, de 10 a 1000 caracteres."
    if problemas:
        raise ErroApi(400, "Chamado inválido.", problemas)
    return assunto, mensagem


def _texto(corpo, campo):
    valor = corpo.get(campo)
    return valor.strip() if isinstance(valor, str) else ""
