"""Validação dos corpos das rotas de pagamento."""

from app.erros import ErroApi


def validar_aprovacao(corpo):
    """Senha de POST /solicitacoes/<id>/autorizacoes, ou 400 se não for um texto preenchido."""
    senha = corpo.get("senha")
    if not isinstance(senha, str) or not senha:
        raise ErroApi(400, "Aprovação inválida.", {"senha": "Informe a senha."})
    return senha
