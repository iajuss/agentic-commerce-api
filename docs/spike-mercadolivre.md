# Spike do Mercado Livre (M2-01)

Objetivo: descobrir se o app do time consegue buscar ofertas de supermercado na API do Mercado Livre e escolher o
conector do catálogo (portão A, B ou C de `docs/plano-backend/02-modulo-descoberta-solicitacoes.md`). O prazo do
portão era quarta, 28/10, às 14h.

## Resultado: opção C (30/10/2026)

**Decisão do Dev 2 (Lucas Ibanez) em 30/10/2026: o MVP segue sem a API do Mercado Livre.** Motivos:

- Sem app no DevCenter e sem token, a API não deixa buscar ofertas. Em 30/10, `verificar` repetiu o que já tinha sido
  visto em 27/10 (tabela abaixo).
- O portão de quarta passou sem o teste com token. O conector `mercadolivre` das opções A e B (renovação do token de
  uso único, nova tentativa no `401`, normalização e testes) leva cerca de um dia e não cabe antes do congelamento de
  funcionalidades de sexta, 30/10, às 23h.
- Mesmo com o catálogo, a compra continuaria simulada: o Mercado Livre não tem API de checkout para comprador.

| Chamada sem token (`python scripts/autorizar_mercadolivre.py verificar`, 30/10/2026) | Status | Resposta |
|---|---|---|
| `GET /sites/MLB/search?q=arroz` | `403` | `forbidden` |
| `GET /sites/MLB/search?category=MLB263835` (Arroz) | `403` | `forbidden` |
| `GET /products/search?site_id=MLB&q=arroz` | `403` | `At least one policy returned UNAUTHORIZED.` |
| `GET /sites/MLB/domain_discovery/search?q=arroz 5kg` (pública) | `200` | categoria `MLB263835` (Arroz) |
| `GET /categories/MLB1403` (pública) | `200` | "Alimentos e Bebidas" |

### O que isso muda no MVP

- **Catálogo:** `CATALOGO_PROVEDOR=combinado` na demonstração e na produção. O catálogo fixo (44 ofertas de
  supermercado em português) e a DummyJSON (o catálogo externo, com 27 produtos) entram no mesmo ranking; se a
  DummyJSON cair, a busca segue com o fixo. O padrão continua `fixo`, para o desenvolvimento e os testes, sem rede.
- **Ranking:** o preço por unidade compara a unidade da maioria das ofertas e conta só o que atende ao pedido. As
  ofertas da DummyJSON, sem medida no título, ficam com a nota neutra no preço e não desligam o preço por kg das outras.
- **Mercado Livre em tempo de execução:** nenhum. A opção C do plano previa usar o `domain_discovery` (público) para
  prever categorias; ficou de fora para a demonstração não depender do Mercado Livre. As categorias vêm do próprio
  catálogo, e as ofertas da DummyJSON ficam em "Mercearia".
- **Fixtures dos testes do M2-03:** `tests/fixtures/dummyjson_groceries.json`, resposta real da DummyJSON, sem
  credenciais. Conferida em 30/10: os 7 produtos da fixture são iguais aos da API.
- **Contrato:** `combinado` entra nos valores de `CATALOGO_PROVEDOR`; as chaves `ML_*` e a coleção `integracoes` ficam
  para depois do MVP. `CATALOGO_PROVEDOR=mercadolivre` impede a API de subir, com uma mensagem clara.

### Limitações (para o README e a apresentação)

- A DummyJSON tem títulos em inglês, preços fictícios (tratados como reais), nenhuma medida no título, frete não
  informado (a cesta cobra o estimado de R$ 15) e uma única loja ("DummyJSON").
- Dos 12 itens do catálogo fixo, a DummyJSON só tem arroz, leite, café, óleo e refrigerante. Em compensação, traz o
  que o fixo não tem, como suco, mel, frutas, legumes e carnes.
- O catálogo fixo é de demonstração: lojas e preços fictícios, sem link nem imagem.

### Depois do MVP

1. Criar o app no DevCenter com a conta do time: escopos de leitura e `offline_access` (sem ele não vem o
   `refresh_token`), PKCE desligado e um `redirect_uri` HTTPS do time.
2. Rodar `autorizar` e `testar` (passo a passo abaixo) e escolher entre A e B.
3. Escrever `app/solicitacoes/catalogo/mercadolivre.py` conforme as opções A e B do M2-03 e registrá-lo em `FABRICAS`
   (`app/solicitacoes/catalogo/__init__.py`), sem mudar a interface `Catalogo`.

## Portão de decisão

| Opção | Condição | Conector |
|---|---|---|
| A | Uma das buscas `[A]` responde `200` com resultados | `CATALOGO_PROVEDOR=mercadolivre` por busca |
| B | Só a busca por vendedor `[B]` responde `200` | `CATALOGO_PROVEDOR=mercadolivre` nos vendedores de `ML_VENDEDORES` |
| C | Nenhuma responde | `CATALOGO_PROVEDOR=combinado` (catálogo fixo + DummyJSON) |

## Verificação anterior, sem token (27/10/2026)

| Chamada | Resultado |
|---|---|
| `GET /sites/MLB/search?q=arroz` | `403 forbidden` |
| `GET /items/{id}`, `GET /products/search`, `GET /sites/MLB/categories`, `GET /trends/MLB/{categoria}` | `403` (`PolicyAgent`) |
| `GET /highlights/MLB/category/MLB1403` | `401` (exige token) |
| `GET /categories/MLB1403` | `200`: "Alimentos e Bebidas", com as subcategorias |
| `GET /sites/MLB/domain_discovery/search?q=leite integral 1L` | `200`: categoria `MLB455818` (Leite) |

A documentação oficial "Busca de itens" (atualizada em 31/08/2026) só documenta a busca **por vendedor**
(`seller_id`), com token. Não há busca por palavra-chave documentada, e também não existe API de compra para
comprador (no MVP, a compra é simulada pelo M3).

## Como repetir a verificação sem token

`python scripts/autorizar_mercadolivre.py verificar`: não precisa de app, token nem `.env`.

## Como rodar o teste com token (depois do MVP, cerca de 15 minutos)

1. No DevCenter do Mercado Livre, com a conta do time, crie um app e cadastre um `redirect_uri` HTTPS estático, de
   preferência um endereço do time (ex.: a página do repositório no GitHub). Ele precisa bater exatamente com o
   `ML_REDIRECT_URI` do `.env`; a página não precisa carregar, porque o `code` aparece na barra de endereço.
2. Preencha `ML_CLIENT_ID`, `ML_CLIENT_SECRET` e `ML_REDIRECT_URI` no `.env` (nunca no Git).
3. `python scripts/autorizar_mercadolivre.py autorizar`: abra a URL impressa, autorize, cole o `code` e copie o
   `ML_REFRESH_TOKEN` impresso para o `.env`.
4. `python scripts/autorizar_mercadolivre.py testar`: mostra o status de cada busca. Atualize o `.env` com o novo
   refresh token impresso, porque ele é de uso único.
5. Opcional, para testar a opção B: ponha o ID de um vendedor de supermercado em `ML_VENDEDORES` e rode o passo 4 de
   novo.
