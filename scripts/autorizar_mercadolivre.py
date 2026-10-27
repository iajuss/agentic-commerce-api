"""Spike do Mercado Livre (M2-01): autoriza o app do time e testa se o token permite buscar ofertas.

Uso (na raiz do repositório, com o ambiente virtual ativo e o .env com ML_CLIENT_ID, ML_CLIENT_SECRET e
ML_REDIRECT_URI):
    python scripts/autorizar_mercadolivre.py autorizar   # abre o fluxo OAuth e imprime o ML_REFRESH_TOKEN
    python scripts/autorizar_mercadolivre.py testar      # testa as buscas com o ML_REFRESH_TOKEN do .env

O refresh token é de uso único: cada execução de "testar" imprime um novo, que precisa substituir o do .env.
Nenhum token vai para o Git; os valores ficam só no .env de quem roda o spike.
"""

import os
import secrets
import sys
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

URL_AUTORIZACAO = "https://auth.mercadolivre.com.br/authorization"
URL_TOKEN = "https://api.mercadolibre.com/oauth/token"
URL_API = "https://api.mercadolibre.com"
TIMEOUT_SEGUNDOS = 15

# Chamadas que decidem o portão do spike (docs/spike-mercadolivre.md).
CHAMADAS_DO_SPIKE = (
    ("A", "Busca por palavra-chave", "/sites/MLB/search", {"q": "arroz", "limit": 3}),
    ("A", "Busca por categoria (Arroz)", "/sites/MLB/search", {"category": "MLB263835", "limit": 3}),
    ("A", "Busca no catálogo de produtos", "/products/search", {"site_id": "MLB", "q": "arroz", "limit": 3}),
    ("-", "Previsão de categoria (pública)", "/sites/MLB/domain_discovery/search",
     {"q": "arroz 5kg", "limit": 1}),
)


def _exigir(nome):
    valor = os.getenv(nome)
    if not valor:
        sys.exit(f"{nome} ausente. Preencha no .env (veja .env.example) e rode de novo.")
    return valor


def _trocar_token(dados):
    resposta = requests.post(
        URL_TOKEN, data=dados, headers={"accept": "application/json"}, timeout=TIMEOUT_SEGUNDOS
    )
    if resposta.status_code != 200:
        sys.exit(f"O Mercado Livre recusou a troca de token ({resposta.status_code}): {resposta.text}")
    return resposta.json()


def autorizar():
    client_id = _exigir("ML_CLIENT_ID")
    redirect_uri = _exigir("ML_REDIRECT_URI")
    parametros = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": secrets.token_urlsafe(16),
    }
    print("1. Abra esta URL no navegador, entre com a conta do time e autorize o app:")
    print(f"   {URL_AUTORIZACAO}?{urlencode(parametros)}")
    print("2. Depois do redirecionamento, copie o valor de code= da barra de endereço")
    print("   (a página de destino pode não carregar; o code aparece mesmo assim).")
    codigo = input("code: ").strip()

    tokens = _trocar_token({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": _exigir("ML_CLIENT_SECRET"),
        "code": codigo,
        "redirect_uri": redirect_uri,
    })
    print("\nAutorizado. Coloque no .env (nunca no Git):")
    print(f"ML_REFRESH_TOKEN={tokens['refresh_token']}")
    print(f"(o access token vale {tokens.get('expires_in')} s; o refresh token vale 6 meses e é de uso único)")


def testar():
    tokens = _trocar_token({
        "grant_type": "refresh_token",
        "client_id": _exigir("ML_CLIENT_ID"),
        "client_secret": _exigir("ML_CLIENT_SECRET"),
        "refresh_token": _exigir("ML_REFRESH_TOKEN"),
    })
    print("O refresh token anterior deixou de valer. Atualize o .env com o novo:")
    print(f"ML_REFRESH_TOKEN={tokens['refresh_token']}\n")

    chamadas = list(CHAMADAS_DO_SPIKE)
    vendedor = os.getenv("ML_VENDEDORES", "").split(",")[0].strip()
    if vendedor:
        chamadas.append(("B", f"Busca no vendedor {vendedor}", "/sites/MLB/search",
                         {"seller_id": vendedor, "category": "MLB1403", "limit": 3}))

    cabecalho = {"Authorization": f"Bearer {tokens['access_token']}"}
    for opcao, nome, caminho, parametros in chamadas:
        try:
            resposta = requests.get(
                URL_API + caminho, params=parametros, headers=cabecalho, timeout=TIMEOUT_SEGUNDOS
            )
        except requests.RequestException as erro:
            print(f"[{opcao}] ERRO  {nome}: {erro}")
            continue
        detalhe = ""
        if resposta.ok:
            corpo = resposta.json()
            if isinstance(corpo, dict) and "results" in corpo:
                detalhe = f"{len(corpo['results'])} resultados nesta página"
        print(f"[{opcao}] {resposta.status_code}  {nome}  {caminho}  {detalhe}")

    print("\nDecisão (registre em docs/spike-mercadolivre.md):")
    print("  A: alguma chamada [A] respondeu 200 com resultados -> conector mercadolivre por busca;")
    print("  B: só a chamada [B] respondeu 200 -> conector mercadolivre por vendedor (ML_VENDEDORES);")
    print("  C: nenhuma -> manter CATALOGO_PROVEDOR=dummyjson (o ViaCEP garante a API externa da rubrica).")


COMANDOS = {"autorizar": autorizar, "testar": testar}

if __name__ == "__main__":
    load_dotenv()
    if len(sys.argv) != 2 or sys.argv[1] not in COMANDOS:
        sys.exit(__doc__)
    COMANDOS[sys.argv[1]]()
