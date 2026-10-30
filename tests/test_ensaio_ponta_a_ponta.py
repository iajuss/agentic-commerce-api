"""Ensaio HTTP exercitado sem rede, com o cliente Flask e banco em memória."""

import sys
from urllib.parse import urlsplit

from app.autenticacao import viacep
from app.solicitacoes.catalogo.fixo import CatalogoFixo
from scripts import ensaio_ponta_a_ponta as ensaio


class RespostaLocal:
    def __init__(self, resposta):
        self.resposta = resposta
        self.status_code = resposta.status_code

    def json(self):
        return self.resposta.get_json()


class SessaoLocal:
    def __init__(self, client):
        self.client = client
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *argumentos):
        return False

    def request(self, metodo, url, **opcoes):
        argumentos = {"method": metodo, "headers": dict(self.headers)}
        if "json" in opcoes:
            argumentos["json"] = opcoes["json"]
        resposta = self.client.open(urlsplit(url).path, **argumentos)
        return RespostaLocal(resposta)

    def get(self, url, **opcoes):
        return self.request("GET", url, **opcoes)


class RespostaViaCep:
    status_code = 200

    def json(self):
        return {
            "logradouro": "Praça da Sé",
            "bairro": "Sé",
            "localidade": "São Paulo",
            "uf": "SP",
        }


def test_ensaio_executa_os_dois_fluxos_sem_rede(app, client, monkeypatch, capsys):
    app.extensions["catalogo"] = CatalogoFixo()
    app.config.update(SIMULACAO_ENVIO_MINUTOS=0, SIMULACAO_ENTREGA_MINUTOS=0)
    monkeypatch.setattr(viacep.requests, "get", lambda *args, **kwargs: RespostaViaCep())

    sessoes = []

    def nova_sessao():
        sessoes.append(None)
        if len(sessoes) == 3:
            app.config.update(SIMULACAO_ENVIO_MINUTOS=2, SIMULACAO_ENTREGA_MINUTOS=5)
        return SessaoLocal(client)

    monkeypatch.setattr(ensaio.requests, "Session", nova_sessao)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ensaio", "--base-url", "http://ensaio.local", "--limite-entrega-segundos", "0"],
    )

    assert ensaio.main() == 0
    saida = capsys.readouterr().out
    assert "✓ pedido entregue" in saida
    assert "✓ ensaio completo" in saida


def test_ensaio_falha_com_status_http_inesperado(monkeypatch, capsys):
    class RespostaFalha:
        status_code = 503

    class SessaoFalha:
        def __enter__(self):
            return self

        def __exit__(self, *argumentos):
            return False

        def request(self, *argumentos, **opcoes):
            return RespostaFalha()

    monkeypatch.setattr(ensaio.requests, "Session", SessaoFalha)
    monkeypatch.setattr(sys, "argv", ["ensaio", "--base-url", "http://ensaio.local"])

    assert ensaio.main() == 1
    assert "✗ saúde da API: HTTP 503" in capsys.readouterr().out
