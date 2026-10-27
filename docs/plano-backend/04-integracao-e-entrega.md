# Integração e entrega — sábado 31/10 e domingo 01/11

Os três módulos foram feitos para se ligar sozinhos: os ganchos se registram ao subir o app e os dados seguem o
[contrato](00-contrato-de-integracao.md). Este roteiro confirma que o sistema funciona inteiro, coloca o MVP na EC2 e
prepara a entrega. **Lidera: Dev 1.** Todos participam. Cada correção é feita pelo dono do arquivo, em branch e PR,
mesmo no fim de semana.

## Sábado, 31/10 — integração

### 1. Merges (até 10h)
- Todos os PRs do M1, M2 e M3 abertos até sexta às 23h. Cada autor atualiza a branch com a `main` (`git pull origin
  main`), roda `pytest` inteiro e só então faz o merge, depois da revisão de outro dev.
- Ordem sugerida: o que falta do M1 → M2 → M3. Conflito em arquivo de outro módulo indica violação de propriedade:
  resolva com o dono.

### 2. Checagens de integração (Dev 1, com os testes abaixo na `main`)
- [ ] **Ganchos ativos:** num teste, `app.extensions` contém `registrar_evento` e `compra_automatica`.
- [ ] **Contrato global** (`tests/test_contrato.py`):
  - o `app.url_map` tem exatamente as 27 rotas (método + regra) da seção 2 do contrato;
  - os endpoints públicos são exatamente os de `ENDPOINTS_PUBLICOS`;
  - todas as outras rotas respondem `401` sem token (parâmetros de URL preenchidos com `ObjectId()`);
  - nenhum segmento de URI é um verbo (`criar`, `listar`, `deletar`, `remover`, `atualizar`, `cancelar`, `pagar`,
    `aprovar`, `buscar`, `obter`).
- [ ] **Fluxo completo no pytest** (`tests/test_fluxo_completo.py`, catálogo fixo e ViaCEP mockado):
  - **automático:** cadastro → login → `PATCH /usuarios/me` → política automática → `POST /solicitacoes` (vem
    `aprovada`, com `compra_automatica`) → `POST /simulador-pix/pagamentos` → `GET /pedidos/<id>` (`pago`) → tempo
    avançado (`entregue`) → chamado → `GET /auditoria` com os eventos na ordem;
  - **manual:** política manual → `POST /solicitacoes` → `POST /solicitacoes/<id>/autorizacoes` com senha →
    `POST /pedidos` → simulador → `PATCH /pedidos/<id>` para `cancelado` (com `reembolso`).
- [ ] `pytest` inteiro verde na `main`.

### 3. Ensaio ponta a ponta contra um servidor real
`scripts/ensaio_ponta_a_ponta.py` (Dev 1, sábado de manhã), com `requests`:
`python scripts/ensaio_ponta_a_ponta.py --base-url http://localhost:5000` (ou `http://<ip>/api`).
- Roda os dois fluxos do item 2 contra o servidor, com um e-mail único por execução e um CEP real (`01001000`, para
  provar o ViaCEP).
- Imprime ✓ ou ✗ por passo, com o status HTTP recebido, e sai com código diferente de zero se algo falhar.
- Primeiro localmente (Atlas com o banco do dev e o catálogo externo ligado); depois na EC2.

### 4. Postman unificado (Dev 1)
- Juntar `docs/postman/solicitacoes.postman_collection.json` e `docs/postman/pagamento-pos-compra.postman_collection.json`
  à `docs/agentic-commerce.postman_collection.json`, em pastas por módulo.
- Variáveis: `baseUrl` (local e produção), `token`, `politicaId`, `solicitacaoId`, `autorizacaoId`, `pedidoId`, `txid`,
  `chamadoId`.
- Rodar a coleção inteira na ordem do fluxo.

### 5. Deploy integrado (até 18h)
- Na EC2: `deploy/atualizar.sh`.
- Conferir o arquivo de ambiente de produção: `PROXY_FIX=1`, `MONGO_DB_NAME=agentic_commerce`, `CATALOGO_PROVEDOR` e as
  credenciais do catálogo, e `CORS_ORIGINS` com a origem do front.
- Rodar o ensaio contra `http://<ip>/api`.
- Passar ao time do front a URL base e a coleção Postman.

## Domingo, 01/11 — entrega

| Hora | O quê | Quem |
|---|---|---|
| até 12h | Últimas correções (só bugs; nada de funcionalidade nova) | Dono de cada módulo |
| 12h | **Congelamento do código** | Todos |
| 13h | README final (abaixo) | Dev 1 |
| 14h | Deploy final na EC2 e ensaio contra a produção | Dev 1 |
| 15h | Ensaio da demonstração com o front, se ele já estiver no ar | Todos |
| 17h | Credenciais de produção enviadas pelo Blackboard | Dev 1 |
| **18h** | **MVP pronto** (opcional: `git tag mvp-2026-11-01`) | Todos |

**README final** (Dev 1):
- produto em 2 parágrafos;
- **link de produção**;
- como rodar localmente e como rodar os testes;
- variáveis de ambiente, só com os nomes;
- APIs externas usadas (ViaCEP e o catálogo escolhido);
- tabela de rotas da seção 2 do contrato;
- convenções REST e formato de erro;
- deploy e atualização;
- limitações do MVP: Pix e compra no Mercado Livre são simulados, e o simulador de pagamento existe só para a
  demonstração.

**Blackboard** (Dev 1):
- os valores reais do arquivo de ambiente de produção (`MONGO_URI`, `MONGO_DB_NAME`, `JWT_SECRET_KEY`, credenciais do
  catálogo, se houver) e o link de produção;
- nada disso vai para o Git;
- depois da correção, recomenda-se trocar a senha do banco e a `JWT_SECRET_KEY`.

## Evidências da rubrica para a apresentação

- [ ] **Flask:** `wsgi.py` e `create_app` com os blueprints.
- [ ] **REST nível 2:** na coleção Postman, mostrar `POST` → `201` + `Location`, `DELETE` → `204`, `PATCH` mudando
      status, erro `409`/`422` em JSON e rota sem token → `401`.
- [ ] **MongoDB Atlas:** coleções no painel do Atlas e `/api/health` com `"banco": "ok"`.
- [ ] **EC2:** o link de produção respondendo na hora.
- [ ] **API externa:** `PATCH /usuarios/me` completando o endereço pelo CEP (ViaCEP) e as ofertas do catálogo externo
      no ranking.
- [ ] **Repositórios separados:** `agentic-commerce-api` e `agentic-commerce-web`.
- [ ] **Credenciais:** `.gitignore`, `.env.example` só com nomes e o envio no Blackboard.
- [ ] **Tema validado:** registro da validação do escopo novo pelo professor.
- [ ] **Testes:** `pytest` inteiro verde, com catálogo e pagamento mockados.

## Plano B

| Se… | Então… |
|---|---|
| O catálogo do Mercado Livre não funcionar | Opção C do M2-01 (DummyJSON). O ViaCEP garante sozinho o critério de API externa |
| Um módulo atrasar na sexta | Outro dev ajuda **na branch do dono**, em dupla (`Co-authored-by`); cortar primeiro a devolução e depois os chamados, mantendo as rotas com o comportamento mínimo |
| A EC2 der problema no sábado | Recriar a instância seguindo o passo a passo do M1-07; a EC2 é obrigatória na rubrica e não tem substituto |
| O IP mudar (Learner Lab) | Atualizar o *Network Access* do Atlas, o `CORS_ORIGINS` e o link do README; em último caso, liberar `0.0.0.0/0` no Atlas com senha forte só durante a apresentação |
| O front não estiver pronto | Demonstrar o backend pela coleção Postman e pelo ensaio ponta a ponta |
