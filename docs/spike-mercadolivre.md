# Spike do Mercado Livre (M2-01)

Objetivo: descobrir se o app do time consegue buscar ofertas de supermercado na API do Mercado Livre e escolher o
conector do catálogo (portão A, B ou C de `docs/plano-backend/02-modulo-descoberta-solicitacoes.md`).
**Prazo da decisão: quarta, 28/10, às 14h.**

## O que já foi verificado sem token (27/10/2026)

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

## Como rodar o teste com token (15 minutos)

1. No DevCenter do Mercado Livre, com a conta do time, crie um app e cadastre um `redirect_uri` HTTPS estático (ex.:
   `https://localhost.com/redirect`). Ele precisa bater exatamente com o `ML_REDIRECT_URI` do `.env`.
2. Preencha `ML_CLIENT_ID`, `ML_CLIENT_SECRET` e `ML_REDIRECT_URI` no `.env` (nunca no Git).
3. `python scripts/autorizar_mercadolivre.py autorizar`: abra a URL impressa, autorize, cole o `code` e copie o
   `ML_REFRESH_TOKEN` impresso para o `.env`.
4. `python scripts/autorizar_mercadolivre.py testar`: mostra o status de cada busca. Atualize o `.env` com o novo
   refresh token impresso, porque ele é de uso único.
5. Opcional, para testar a opção B: ponha o ID de um vendedor de supermercado em `ML_VENDEDORES` e rode o passo 4 de
   novo.

## Decisão

| Opção | Condição | Conector |
|---|---|---|
| A | Uma das buscas `[A]` responde `200` com resultados | `CATALOGO_PROVEDOR=mercadolivre` por busca |
| B | Só a busca por vendedor `[B]` responde `200` | `CATALOGO_PROVEDOR=mercadolivre` nos vendedores de `ML_VENDEDORES` |
| C | Nenhuma responde | `CATALOGO_PROVEDOR=dummyjson` |

**Resultado:** _a preencher depois do passo 4 (data, quem rodou, status de cada chamada e opção escolhida)._

**Enquanto isso:** o conector `dummyjson` (opção C) foi implementado no M2-03 e já funciona sem chave. O MVP não fica
bloqueado, e o critério de API externa da rubrica está garantido pelo ViaCEP (M1) e pela DummyJSON. Se o resultado for
A ou B, o conector `mercadolivre` entra como tarefa adicional do M2, mantendo a mesma interface de catálogo.
