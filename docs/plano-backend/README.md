# Plano do MVP do backend — entrega em 01/11/2026

Guia de execução do backend do Agentic Commerce para os **3 devs de backend** e para as IAs que os ajudam. O MVP
precisa estar **pronto e demonstrável no domingo, 01/11/2026**. A apresentação é na terça, 03/11; a segunda, 02/11
(Finados), fica de reserva.

**Produto:** compra de supermercado por intenção, com autonomia controlada. O usuário descreve a lista de compras; a API
busca ofertas no catálogo, aplica as políticas que o usuário definiu, recomenda com um ranking explicável e conduz a
aprovação (com senha), o pagamento por Pix (simulado) e o pós-compra. Quando a política permite, o agente compra
sozinho. Toda ação fica numa trilha de auditoria.

## Arquivos deste plano

| Arquivo | Para quem | Conteúdo |
|---|---|---|
| [00-contrato-de-integracao.md](00-contrato-de-integracao.md) | Todos (leitura obrigatória) | Rotas, esquemas de dados, ganchos, configuração e convenções que ligam os módulos |
| [01-modulo-conta-auditoria-plataforma.md](01-modulo-conta-auditoria-plataforma.md) | Dev 1 | Perfil com ViaCEP, auditoria, configuração, deploy na EC2 e liderança da integração |
| [02-modulo-descoberta-solicitacoes.md](02-modulo-descoberta-solicitacoes.md) | Dev 2 | Catálogo (externo + fixo), políticas da cesta, intenção, ranking e solicitações |
| [03-modulo-aprovacao-pagamento-pos-compra.md](03-modulo-aprovacao-pagamento-pos-compra.md) | Dev 3 | Autorizações com senha, pedidos com Pix simulado, pós-compra, chamados e compra automática |
| [04-integracao-e-entrega.md](04-integracao-e-entrega.md) | Todos (sábado e domingo) | Roteiro de integração, ensaio ponta a ponta, deploy final, entrega e plano B |

## Ponto de partida (`main` em `f62d781`)

Já existem: app factory com blueprints, padrão de erros JSON, CORS, `GET /health`, CRUD de `/politicas` com o validador
`avaliar_oferta`, cadastro (`POST /usuarios`), login (`POST /sessoes`) e **proteção JWT global** (`proteger_rotas` em
`app/__init__.py`: toda rota exige token, exceto `/health`, cadastro e login). São 48 testes passando
(`pytest`, sem rede nem Atlas, com mongomock).

## Como o trabalho foi dividido

São 3 módulos, um por dev. **Nenhum módulo importa código novo de outro**: quando uma parte precisava de outra, as
duas ficaram no mesmo módulo. Os módulos se conectam só por três caminhos, todos definidos no
[contrato](00-contrato-de-integracao.md):

1. **Documentos no MongoDB** com esquema congelado: o contrato diz quem escreve e quem lê cada campo.
2. **Dois ganchos** em `app.extensions`, registrados pelo próprio módulo que os fornece: `registrar_evento` (M1) e
   `compra_automatica` (M3). Quem consome chama `current_app.extensions.get(...)`; se o gancho ainda não existe, recebe
   `None` e segue sem ele. Por isso cada módulo funciona e é testável sozinho.
3. **A API HTTP** (rotas e formatos do contrato).

| Módulo | Dev | Pastas de que é dono | Rotas novas | Ganchos |
|---|---|---|---|---|
| **M1** — Conta, Auditoria e Plataforma | Dev 1 | `app/autenticacao/`, `app/auditoria/`, `app/saude.py`, `deploy/` + arquivos compartilhados (tabela abaixo) | `GET/PATCH /usuarios/me`, `GET /auditoria` | fornece `registrar_evento` |
| **M2** — Descoberta e Solicitações | Dev 2 | `app/solicitacoes/` (inclui `catalogo/`), `app/politicas/regras.py`, `scripts/autorizar_mercadolivre.py` | `POST/GET /solicitacoes`, `GET/DELETE /solicitacoes/{id}` | consome os dois |
| **M3** — Aprovação, Pagamento e Pós-compra | Dev 3 | `app/pagamento/`, `app/pos_compra/` | 12 rotas de autorizações, pedidos, simulador Pix e chamados | fornece `compra_automatica`, consome `registrar_evento` |

```
            usuarios (perfil)                          solicitacoes (status)
  M1 ───────────────────────────► M2 ─────────────────────────────────► M3
  │   leitura por contrato          │  gancho compra_automatica (M3)      │
  │                                 │                                     │
  └──── gancho registrar_evento ◄───┴───────────── eventos ◄─────────────┘
        (auditoria do M1)
```

## Dono de cada arquivo compartilhado

Só o dono edita. Precisou de mudança num arquivo de outro módulo? Peça ao dono ou proponha mudança no contrato.

| Arquivo | Dono | Como os outros módulos lidam |
|---|---|---|
| `app/__init__.py`, `app/config.py`, `app/banco.py` | M1 | Leem configuração com `current_app.config.get(CHAVE, padrão_do_contrato)`; não criam índices |
| `app/erros.py`, `app/json.py` | congelados | Usam como estão (`ErroApi`, `ler_json`) |
| `app/politicas/rotas.py` | M1 (só as linhas de auditoria) | — |
| `app/politicas/regras.py` | M2 | O M3 não chama o validador: confia na `avaliacao` gravada na solicitação |
| `requirements.txt`, `.env.example`, `.gitignore` | M1 | `requests` já está no `requirements.txt`; peçam ao M1 qualquer dependência nova |
| `tests/conftest.py` | M1 | Fixtures específicas ficam no próprio arquivo de teste do módulo |
| `README.md`, `docs/agentic-commerce.postman_collection.json` | M1 (só no sábado e domingo) | M2 e M3 entregam `docs/postman/<modulo>.postman_collection.json`; o M1 unifica no sábado |
| `tests/test_<assunto>.py` | dono do assunto | Prefixos: M1 `test_perfil*`, `test_auditoria*`, `test_config*`; M2 `test_solicitacoes*`, `test_catalogo*`, `test_ranking*`, `test_intencao*`, `test_medidas*`, `test_regras_cesta*`; M3 `test_autorizacoes*`, `test_pedidos*`, `test_pos_compra*`, `test_chamados*` |

## Cronograma

| Dia | Dev 1 (M1) | Dev 2 (M2) | Dev 3 (M3) | Marco do time |
|---|---|---|---|---|
| Ter 27/10 (noite) | Lê M1 e contrato; monta `.env` | Lê M2 e contrato; monta `.env`; cria conta/app no ML | Lê M3 e contrato; monta `.env` | Kickoff; enviar ao professor a validação do escopo |
| Qua 28/10 | M1-01 (merge até 12h), M1-02, M1-03 | M2-01 spike (decisão até 14h), M2-02 | M3-01, M3-02 | **12h: contrato congelado** |
| Qui 29/10 | M1-04 (perfil + ViaCEP), M1-05 | M2-03, M2-04, M2-05 | M3-03 | Cada um com PRs pequenos revisados por outro dev |
| Sex 30/10 | M1-06, M1-07 (EC2 no ar com o `main`) | M2-06, M2-07, M2-08 | M3-04 a M3-08 | **23h: congelamento de funcionalidades** |
| Sáb 31/10 | Lidera a integração | Integração e correções | Integração e correções | Fluxo completo rodando local e na EC2 |
| Dom 01/11 | Deploy final, README, Blackboard | Ensaio e correções | Ensaio e correções | **MVP pronto (18h)** |
| Seg 02/11 | Reserva | Reserva | Reserva | Ensaio da apresentação com o front |

Sincronização: 15 minutos por dia (fim da tarde) para revisar PRs abertos, bloqueios e mudanças no contrato.

## Fora do MVP

Ficam para depois: sandbox real de Pix (Mercado Pago), webhook e reconciliação de pagamento, interpretação da intenção
por LLM, saldo pré-pago, recompras agendadas, CI no GitHub, reavaliação das políticas no momento da aprovação e soma do
gasto mensal no orçamento. Nenhum desses itens é cobrado pela rubrica.

## Rubrica do backend → onde é atendida

| Critério | Onde | Evidência na apresentação |
|---|---|---|
| Servidor em Flask | Já atende | `requirements.txt`, `wsgi.py`, `app/__init__.py` |
| REST nível 2 de Richardson | Todos os módulos seguem o [contrato](00-contrato-de-integracao.md); teste global de contrato (M1-08) | Coleção Postman mostrando verbos, `201` + `Location`, `204`, erros JSON |
| MongoDB no Atlas | M1 (índices, banco de produção) + todos (`banco()`) | `/health` com `"banco": "ok"` na EC2; coleções no painel do Atlas |
| Deploy em EC2 | M1-07 | Link de produção no README respondendo |
| Pelo menos uma API externa | M1-04 (ViaCEP, garantida) + M2-03 (catálogo: Mercado Livre ou DummyJSON) | Perfil completando o endereço pelo CEP; ofertas do catálogo externo no ranking |
| Repositórios separados | Já atende | `agentic-commerce-api` e `agentic-commerce-web` na org `iajuss` |
| Credenciais fora do Git, via variáveis de ambiente, enviadas pelo Blackboard | Todos + M1 (entrega) | `.gitignore`, `.env.example`, histórico sem segredos, envio no Blackboard |
| Tema validado pelo professor | Time, já na terça | Registro da validação (o escopo mudou para supermercado + Pix) |

## Protocolo de execução (pessoas e IAs)

1. Pegue a próxima tarefa do seu módulo, na ordem do arquivo. Não implemente nada de outro módulo.
2. **Antes de editar**, crie a branch a partir da `main` atualizada: `git switch main && git pull && git switch -c
   feat/m<N>-<assunto>` (use `fix/` para correção e `chore/` para configuração). Nunca commite na `main`.
3. Siga as convenções do [contrato](00-contrato-de-integracao.md#1-convenções) e as camadas de `app/politicas/`
   (`rotas.py` → `validacao.py` → `repositorio.py` → `regras.py`).
4. Escreva os testes da tarefa junto com o código; testes nunca acessam a rede nem o Atlas.
5. Antes do PR: `git pull origin main` na sua branch e `pytest` com a suíte inteira verde.
6. PR pequeno para a `main`, revisado por **outro dev**. Use merge normal (sem squash) para preservar os commits de cada
   pessoa, que o professor avalia. Em dupla, termine a mensagem com `Co-authored-by: Nome <email-do-github>`.
7. Mudança no contrato (rota, campo, status, gancho, chave de configuração) só por PR em
   `00-contrato-de-integracao.md`, aprovado pelos 3 devs.

**Nunca:** commitar `.env`, chave `.pem` ou qualquer credencial; chamar API real em teste; editar arquivo de outro
módulo; mudar o formato de erro `{"erro", "detalhes"}`; apagar ou desativar teste para "fazer passar".

## Definição de Pronto (vale para toda tarefa)

- [ ] Critérios de aceite da tarefa atendidos e `pytest` inteiro verde.
- [ ] Rotas seguem o contrato: códigos HTTP, `201` com `Location`, `204` sem corpo, erros via `ErroApi`.
- [ ] Toda consulta filtra por `usuario_id`; recurso de outro usuário responde `404`.
- [ ] Eventos de auditoria emitidos pelo gancho onde o contrato manda.
- [ ] Nenhum segredo no código, nos testes ou nos logs.
- [ ] Coleção Postman do módulo atualizada com as rotas novas.
- [ ] PR revisado por outro dev.

## Ambiente local e credenciais

1. `python -m venv .venv`, ative (`.venv\Scripts\activate` no Windows) e `pip install -r requirements.txt`.
2. `copy .env.example .env` (Linux/macOS: `cp`) e preencha conforme a tabela abaixo. O `.env` está no `.gitignore` e
   **nunca** vai para o Git.
3. `python scripts/testar_atlas.py` confere a conexão; `flask --app wsgi run --debug` sobe a API em
   `http://localhost:5000/health`.

| Credencial | Quem precisa | Como obter | Onde fica |
|---|---|---|---|
| `MONGO_URI` (usuário e senha de banco no Atlas) | Todos | Quem administra o cluster cria o usuário em *Database Access* e libera o IP de cada dev em *Network Access* | `.env` de cada dev; produção no arquivo de ambiente da EC2 |
| `MONGO_DB_NAME` | Todos | Cada dev usa o seu: `agentic_commerce_dev_<nome>`; produção usa `agentic_commerce` | `.env` |
| `JWT_SECRET_KEY` | Todos | Cada um gera: `python -c "import secrets; print(secrets.token_hex(32))"` | `.env` (a de produção só na EC2) |
| `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, `ML_REFRESH_TOKEN` | Dev 2 (e a produção) | App no DevCenter do Mercado Livre + `scripts/autorizar_mercadolivre.py` (M2-01); só se o spike aprovar o ML | `.env` |
| Acesso à AWS e chave SSH `.pem` da EC2 | Dev 1 | Console da AWS (ou Learner Lab) | Fora do repositório (ex.: `~/.ssh/`); `*.pem` está no `.gitignore` |
| Arquivo com as credenciais de produção | Dev 1 entrega | Cópia do arquivo de ambiente da EC2 | **Blackboard** (nunca no Git) |

ViaCEP, DummyJSON e o Pix simulado **não usam credencial**. Compartilhem `MONGO_URI` e as credenciais do Mercado
Livre só por canal privado (mensagem direta ou gerenciador de senhas), nunca no repositório nem em grupo aberto.
