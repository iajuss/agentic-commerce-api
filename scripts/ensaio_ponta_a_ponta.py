"""Exercita os fluxos automático e manual contra uma API HTTP em execução."""

import argparse
import sys
import time
from uuid import uuid4

import requests

TEMPO_LIMITE_HTTP = 15
ESPERA_ENTRE_CONSULTAS = 5


class FalhaEnsaio(Exception):
    """Interrompe o ensaio quando uma etapa não atende ao contrato."""


def _requisitar(sessao, metodo, base_url, caminho, descricao, esperado, **opcoes):
    try:
        resposta = sessao.request(
            metodo,
            f"{base_url}{caminho}",
            timeout=TEMPO_LIMITE_HTTP,
            allow_redirects=False,
            **opcoes,
        )
    except requests.RequestException as erro:
        print(f"✗ {descricao}: falha de conexão ({type(erro).__name__})")
        raise FalhaEnsaio(descricao) from erro

    if resposta.status_code != esperado:
        print(f"✗ {descricao}: HTTP {resposta.status_code}; esperado {esperado}")
        raise FalhaEnsaio(descricao)
    print(f"✓ {descricao}: HTTP {resposta.status_code}")
    return resposta


def _dados(resposta, descricao):
    try:
        return resposta.json()
    except ValueError as erro:
        print(f"✗ {descricao}: resposta sem JSON válido")
        raise FalhaEnsaio(descricao) from erro


def _conferir(condicao, descricao):
    if not condicao:
        print(f"✗ {descricao}")
        raise FalhaEnsaio(descricao)
    print(f"✓ {descricao}")


def _entrar(sessao, base_url, fluxo):
    senha = f"senha-ensaio-{uuid4().hex}"
    email = f"ensaio-{fluxo}-{uuid4().hex}@example.com"
    cadastro = {"nome": f"Ensaio {fluxo}", "email": email, "senha": senha}
    resposta = _requisitar(
        sessao, "POST", base_url, "/usuarios", f"{fluxo}: cadastro", 201, json=cadastro
    )
    _conferir(bool(_dados(resposta, "cadastro").get("id")), f"{fluxo}: usuário criado")

    resposta = _requisitar(
        sessao,
        "POST",
        base_url,
        "/sessoes",
        f"{fluxo}: login",
        200,
        json={"email": email, "senha": senha},
    )
    token = _dados(resposta, "login").get("token")
    _conferir(isinstance(token, str) and bool(token), f"{fluxo}: token recebido")
    sessao.headers["Authorization"] = f"Bearer {token}"
    return senha


def _politica(sessao, base_url, fluxo, autonomia):
    resposta = _requisitar(
        sessao,
        "POST",
        base_url,
        "/politicas",
        f"{fluxo}: política {autonomia}",
        201,
        json={"nome": f"Mercado {fluxo}", "teto_por_compra": 500, "nivel_autonomia": autonomia},
    )
    return _dados(resposta, "política")


def _solicitacao(sessao, base_url, fluxo, item):
    resposta = _requisitar(
        sessao,
        "POST",
        base_url,
        "/solicitacoes",
        f"{fluxo}: solicitação",
        201,
        json={"itens": [{"descricao": item, "quantidade": 1}]},
    )
    return _dados(resposta, "solicitação")


def _pedido(sessao, base_url, pedido_id):
    resposta = _requisitar(
        sessao, "GET", base_url, f"/pedidos/{pedido_id}", "consultar pedido", 200
    )
    return _dados(resposta, "pedido")


def _pagar(sessao, base_url, pedido):
    resposta = _requisitar(
        sessao,
        "POST",
        base_url,
        "/simulador-pix/pagamentos",
        "confirmar Pix simulado",
        200,
        json={"txid": pedido["pix"]["txid"]},
    )
    _conferir(_dados(resposta, "pagamento").get("status") == "pago", "pedido pago")


def _aguardar_entrega(sessao, base_url, pedido_id, limite):
    inicio = time.monotonic()
    while True:
        try:
            resposta = sessao.get(
                f"{base_url}/pedidos/{pedido_id}",
                timeout=TEMPO_LIMITE_HTTP,
                allow_redirects=False,
            )
        except requests.RequestException as erro:
            print(f"✗ entrega: falha de conexão ({type(erro).__name__})")
            raise FalhaEnsaio("entrega") from erro

        if resposta.status_code != 200:
            print(f"✗ entrega: HTTP {resposta.status_code}; esperado 200")
            raise FalhaEnsaio("entrega")
        status = _dados(resposta, "entrega").get("status")
        if status == "entregue":
            print("✓ pedido entregue: HTTP 200")
            return
        if status not in {"pago", "enviado"}:
            print(f"✗ entrega: estado inesperado {status}")
            raise FalhaEnsaio("entrega")

        restante = limite - (time.monotonic() - inicio)
        if restante <= 0:
            print(f"✗ entrega: não ocorreu em {limite} segundos")
            raise FalhaEnsaio("entrega")
        time.sleep(min(ESPERA_ENTRE_CONSULTAS, restante))


def _automatico(base_url, item, limite_entrega):
    with requests.Session() as sessao:
        _entrar(sessao, base_url, "automatico")
        resposta = _requisitar(
            sessao,
            "PATCH",
            base_url,
            "/usuarios/me",
            "automatico: endereço via ViaCEP",
            200,
            json={"endereco": {"cep": "01001000", "numero": "10"}},
        )
        endereco = _dados(resposta, "endereço").get("endereco") or {}
        _conferir(
            endereco.get("cep") == "01001-000" and bool(endereco.get("cidade")),
            "automatico: CEP completado pelo ViaCEP",
        )

        _politica(sessao, base_url, "automatico", "automatica")
        solicitacao = _solicitacao(sessao, base_url, "automatico", item)
        _conferir(solicitacao.get("status") == "aprovada", "compra aprovada automaticamente")
        compra = solicitacao.get("compra_automatica") or {}
        pedido_id = compra.get("pedido_id")
        _conferir(bool(pedido_id), "pedido automático criado")

        pedido = _pedido(sessao, base_url, pedido_id)
        _conferir(pedido.get("status") == "aguardando_pagamento", "Pix aguardando pagamento")
        _pagar(sessao, base_url, pedido)
        _aguardar_entrega(sessao, base_url, pedido_id, limite_entrega)

        resposta = _requisitar(
            sessao,
            "POST",
            base_url,
            f"/pedidos/{pedido_id}/chamados",
            "automatico: abrir chamado",
            201,
            json={"assunto": "Entrega", "mensagem": "Gostaria de confirmar os itens recebidos."},
        )
        _conferir(bool(_dados(resposta, "chamado").get("id")), "chamado criado")

        resposta = _requisitar(
            sessao, "GET", base_url, "/auditoria", "automatico: auditoria", 200
        )
        tipos = [evento["tipo"] for evento in _dados(resposta, "auditoria")["eventos"]]
        esperados = [
            "chamado_aberto", "pedido_entregue", "pagamento_confirmado", "pedido_criado",
            "autorizacao_emitida", "solicitacao_criada", "politica_criada", "perfil_atualizado",
            "sessao_iniciada", "usuario_cadastrado",
        ]
        _conferir(tipos == esperados, "automatico: eventos auditados na ordem")


def _manual(base_url, item):
    with requests.Session() as sessao:
        senha = _entrar(sessao, base_url, "manual")
        _politica(sessao, base_url, "manual", "manual")
        solicitacao = _solicitacao(sessao, base_url, "manual", item)
        _conferir(
            solicitacao.get("status") == "aguardando_aprovacao",
            "manual: solicitação aguardando aprovação",
        )
        resposta = _requisitar(
            sessao,
            "POST",
            base_url,
            f"/solicitacoes/{solicitacao['id']}/autorizacoes",
            "manual: autorização com senha",
            201,
            json={"senha": senha},
        )
        autorizacao = _dados(resposta, "autorização")
        _conferir(autorizacao.get("origem") == "manual", "manual: autorização emitida")

        resposta = _requisitar(
            sessao,
            "POST",
            base_url,
            "/pedidos",
            "manual: criar pedido",
            201,
            json={"autorizacao_id": autorizacao["id"]},
        )
        pedido = _dados(resposta, "pedido")
        _conferir(pedido.get("status") == "aguardando_pagamento", "manual: Pix criado")
        _pagar(sessao, base_url, pedido)

        resposta = _requisitar(
            sessao,
            "PATCH",
            base_url,
            f"/pedidos/{pedido['id']}",
            "manual: cancelar pedido",
            200,
            json={"status": "cancelado"},
        )
        cancelado = _dados(resposta, "cancelamento")
        _conferir(cancelado.get("status") == "cancelado", "manual: pedido cancelado")
        reembolso = cancelado.get("reembolso") or {}
        _conferir(
            reembolso.get("status") == "simulado" and reembolso.get("valor") == pedido["total"],
            "manual: reembolso registrado",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Ex.: http://localhost:5000")
    parser.add_argument("--item", default="arroz", help="Item disponível no catálogo configurado")
    parser.add_argument(
        "--limite-entrega-segundos",
        type=int,
        default=480,
        help="Tempo máximo para envio e entrega simulados (padrão: 480)",
    )
    argumentos = parser.parse_args()
    base_url = argumentos.base_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        parser.error("--base-url deve começar com http:// ou https://")
    if argumentos.limite_entrega_segundos < 0:
        parser.error("--limite-entrega-segundos deve ser maior ou igual a zero")

    try:
        with requests.Session() as sessao:
            resposta = _requisitar(
                sessao, "GET", base_url, "/health", "saúde da API", 200
            )
        _conferir(_dados(resposta, "saúde").get("banco") == "ok", "Atlas conectado")
        _automatico(base_url, argumentos.item, argumentos.limite_entrega_segundos)
        _manual(base_url, argumentos.item)
    except (FalhaEnsaio, KeyError, TypeError, ValueError) as erro:
        if not isinstance(erro, FalhaEnsaio):
            print(f"✗ resposta fora do contrato: {type(erro).__name__}")
        return 1

    print("✓ ensaio completo")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
