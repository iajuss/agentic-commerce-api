# M3 — Aprovação, Pagamento Pix e Pós-compra (Dev 3)

Leia antes: [README](README.md) (protocolo e cronograma) e [contrato](00-contrato-de-integracao.md).

**Objetivo:** levar a cesta aprovada até o pós-compra:
1. aprovação com senha, que gera uma autorização limitada de uso único;
2. pedido com cobrança Pix **simulada**;
3. simulador de pagamento para a demonstração;
4. estados do pedido (expiração, envio e entrega simulados);
5. cancelamento e devolução;
6. chamados;
7. a compra automática, oferecida ao M2 pelo gancho `compra_automatica`.

**É dono de:** `app/pagamento/`, `app/pos_compra/`, `docs/postman/pagamento-pos-compra.postman_collection.json`,
`tests/apoio_pagamento.py` e os testes `test_autorizacoes*`, `test_pedidos*`, `test_pos_compra*`, `test_chamados*` e
`test_compra_automatica*`.

**Entrega ao contrato:**
- as 12 rotas do M3 (seção 2);
- as transições de status da solicitação que cabem ao M3 (seção 5);
- o gancho `compra_automatica` (seção 6.2);
- o consumo de `registrar_evento` (seção 6.1).

**Não depende de código novo de ninguém:**
- lê a solicitação pelo esquema da seção 4 do contrato;
- lê `usuarios.senha_hash` com projeção e confere com `werkzeug.security.check_password_hash`;
- confia na `avaliacao` gravada pelo M2, sem reavaliar políticas.

Nos testes, as solicitações e os usuários são inseridos direto no mongomock pelos auxiliares do M3-01.

| Tarefa | Dia | Prioridade |
|---|---|---|
| M3-01 Base do módulo e dados de teste | Qua | Obrigatória |
| M3-02 Autorizações com reautenticação | Qua–Qui | Obrigatória |
| M3-03 Pix simulado, pedidos e simulador | Qui | Obrigatória |
| M3-04 Estados do pedido e comprovante | Sex | Obrigatória |
| M3-05 Cancelamento e devolução | Sex | Obrigatória |
| M3-06 Chamados de pós-venda | Sex | Obrigatória |
| M3-07 Gancho `compra_automatica` | Sex | Obrigatória |
| M3-08 Testes de contrato e coleção Postman | Sex | Obrigatória |

Os arquivos do M3 são `app/pagamento/{rotas,validacao,servicos,pix,regras,auditoria}.py`,
`app/pagamento/repositorio_autorizacoes.py`, `app/pagamento/repositorio_pedidos.py` e
`app/pos_compra/{rotas,validacao,regras,repositorio}.py`; `pos_compra` lê e grava pedidos por
`app.pagamento.repositorio_pedidos`, que também é do M3.

## M3-01 — Base do módulo e dados de teste
Branch `feat/m3-base` · Quarta

**Especificação:**
- `app/pagamento/auditoria.py`: a função `auditar(...)` exatamente como na seção 6.1 do contrato.
- `agora()` em `app/pagamento/regras.py` e em `app/pos_compra/regras.py` (UTC), que os testes trocam por `monkeypatch`.
- `tests/apoio_pagamento.py` (não é coletado pelo pytest, por não começar com `test_`):
  - `inserir_usuario(app, senha="senha-forte-123")`: grava `nome`, `email` e `senha_hash` com
    `generate_password_hash`;
  - `inserir_solicitacao(app, usuario_id, status="aguardando_aprovacao", permitida=True, compra_automatica=False,
    total=33.8)`: monta um documento **idêntico** ao da seção 4 do contrato, com 2 itens `com_oferta`.
**Aceite:**
- [x] Os auxiliares produzem documentos que batem campo a campo com o contrato (um teste compara as chaves).

## M3-02 — Autorizações com reautenticação
Branch `feat/m3-autorizacoes` · Quarta–quinta · Rotas em `app/pagamento/rotas.py`

**`POST /solicitacoes/<solicitacao_id>/autorizacoes`** com `{"senha": "..."}`. Checagens, nesta ordem:
1. `senha` precisa ser texto, senão `400`;
2. a solicitação precisa ser do usuário, senão `404`;
3. o `status` precisa ser `aguardando_aprovacao`, senão `409` "Esta solicitação não está aguardando aprovação.";
4. a senha precisa bater com `usuarios.senha_hash`, senão `401` "Senha incorreta." e evento `reautenticacao_recusada`;
5. `avaliacao.permitida` precisa ser verdadeira, senão `422` "Nenhuma política permite esta compra." com
   `detalhes: {"motivos": [...]}` copiados da solicitação.

Depois, em `servicos.emitir_autorizacao(usuario_id, solicitacao, origem)`:
- muda a solicitação de `aguardando_aprovacao` para `aprovada` com `find_one_and_update`, com o status esperado no
  filtro; se nada casar, `409`;
- insere a autorização: `valor_maximo` = `cesta.total`, `lojas` = `cesta.lojas`, `itens` = cópia dos itens
  `com_oferta` (`id_externo`, `titulo`, `preco`, `quantidade`, `loja`), `origem`, `politica_id`, `status: "ativa"`,
  `expira_em = agora() + AUTORIZACAO_VALIDADE_MINUTOS` (padrão 15) e `criada_em`;
- emite o evento `autorizacao_emitida` com `dados: {"origem": ...}`.

Resposta `201` + `Location: /autorizacoes/<id>` + a autorização.

**As outras rotas:**
- `GET /autorizacoes`: só as `ativa` e não vencidas, mais recentes primeiro.
- `GET /autorizacoes/<autorizacao_id>`: qualquer status, só do dono (senão `404`).
- `DELETE /autorizacoes/<autorizacao_id>`:
  - `ativa` → `revogada` (`204`); a solicitação volta de `aprovada` para `aguardando_aprovacao`; evento
    `autorizacao_revogada`;
  - já `revogada` → `204` (idempotente);
  - `usada` → `409` "Esta autorização já foi usada em um pedido.".

**Testes** (`tests/test_autorizacoes.py`):
- senha certa → 201 com `Location`;
- senha errada → 401 e nenhuma autorização;
- `permitida` falsa → 422 com os motivos;
- dois `POST` seguidos → o segundo dá 409;
- autorização vencida (tempo avançado) some de `GET /autorizacoes`;
- revogar → 204, e a solicitação volta a aguardar;
- revogar uma usada → 409;
- outro usuário → 404.

**Aviso ao front, que vai no README:** nesta rota, `401` significa **senha errada**, não sessão expirada.

## M3-03 — Pix simulado, pedidos e simulador
Branch `feat/m3-pedidos-pix` · Quinta

**Especificação:**
- `app/pagamento/pix.py`: `criar_cobranca(txid, valor, expira_em)` devolve `{"txid", "copia_e_cola":
  f"PIX-SIMULADO-{txid}", "qr_code_base64": None, "expira_em", "pago_em": None}`. O texto é claramente falso; o front
  gera o QR a partir dele. O `txid` vem de `secrets.token_hex(16)`.
- **`POST /pedidos`** com `{"autorizacao_id": "..."}`:
  - consome a autorização de forma atômica, com o filtro `status: "ativa"` e `expira_em > agora()` e a mudança para
    `usada` e `usada_em`;
  - se nada casar: autorização inexistente ou de outro usuário → `404`; vencida, revogada ou usada → `409`
    "Autorização expirada, revogada ou já usada.";
  - em `servicos.criar_pedido(usuario_id, autorizacao)`, cria o pedido no formato da seção 10 do contrato: `itens`,
    `total = valor_maximo`, `status: "aguardando_pagamento"`, `historico`, `pix` com
    `expira_em = agora() + PIX_EXPIRACAO_MINUTOS` (padrão 30), `entrega: {"simulada": true}`, `solicitacao_id` e
    `autorizacao_id`;
  - resposta `201` + `Location: /pedidos/<id>`; evento `pedido_criado`.
- **`GET /pedidos`**: resumo (`id`, `status`, `total`, quantidade de itens, `criado_em`), mais recentes primeiro, já com
  as transições do M3-04 aplicadas.
- **`POST /simulador-pix/pagamentos`** com `{"txid": "..."}`:
  - procura o pedido do usuário por `pix.txid` (senão `404`) e aplica as transições;
  - se não estiver `aguardando_pagamento`, responde `409`;
  - `servicos.confirmar_pagamento`: muda para `pago` com `pix.pago_em` e `historico`, a solicitação passa de
    `aprovada` para `concluida` e emite `pagamento_confirmado`;
  - devolve `200` com o pedido.
**Testes** (`tests/test_pedidos.py`):
- 201 com `Location` e dados do Pix;
- reusar a autorização → 409; autorização vencida → 409;
- simulador confirma, e a solicitação fica `concluida`;
- simular de novo → 409;
- `txid` de outro usuário → 404.

## M3-04 — Estados do pedido e comprovante
Branch `feat/m3-estados-pedido` · Sexta · Arquivos: `app/pos_compra/regras.py` e `rotas.py`

**Transições** (funções puras: `transicoes_devidas(pedido, agora, minutos_envio, minutos_entrega)` e
`transicao_permitida(atual, novo)`):

| De | Para | Gatilho | Efeito na solicitação |
|---|---|---|---|
| `aguardando_pagamento` | `pago` | simulador (M3-03) | → `concluida` |
| `aguardando_pagamento` | `expirado` | leitura depois de `pix.expira_em` | → `expirada` |
| `aguardando_pagamento` | `cancelado` | `PATCH` (M3-05) | → `expirada` |
| `pago` | `enviado` | leitura depois de `SIMULACAO_ENVIO_MINUTOS` (padrão 2) contados de `pago_em` | — |
| `enviado` | `entregue` | leitura depois de `SIMULACAO_ENTREGA_MINUTOS` (padrão 5) contados do envio | — |
| `pago` ou `enviado` | `cancelado` | `PATCH`; grava `reembolso` simulado | — |
| `entregue` | `devolucao_solicitada` | `PATCH` com motivo, até 7 dias depois da entrega | — |
| `devolucao_solicitada` | `devolvido` | leitura depois de `SIMULACAO_ENTREGA_MINUTOS`; grava `reembolso` simulado | — |

**`GET /pedidos/<pedido_id>`:**
- aplica as transições devidas, gravando cada uma em `historico` com `find_one_and_update` e o status esperado no
  filtro, para que ler duas vezes não duplique nada;
- emite `pedido_expirado` e `pedido_entregue` quando for o caso;
- devolve o comprovante no formato da seção 10 do contrato: `copia_e_cola` só enquanto aguarda pagamento; depois,
  `txid` e `pago_em`;
- de outro usuário → `404`.
**Testes:** tabela de `transicoes_devidas` (puros); pela rota, com o tempo avançado: `pago` → `enviado` → `entregue`, e
pedido não pago → `expirado` com a solicitação `expirada`; duas leituras seguidas não duplicam `historico`.

## M3-05 — Cancelamento e devolução
Branch `feat/m3-cancelamento-devolucao` · Sexta

**`PATCH /pedidos/<pedido_id>`** com `{"status": "cancelado"}` ou
`{"status": "devolucao_solicitada", "motivo": "..."}` (motivo de 3 a 300 caracteres); outro valor → `400`.
- Primeiro aplica as transições devidas; depois decide pela tabela do M3-04. Qualquer outra transição → `409` com o
  status atual na mensagem.
- Cancelar `pago` ou `enviado` grava `reembolso: {"valor": total, "status": "simulado", "em": ...}`.
- Devolução depois de 7 dias da entrega → `409` "O prazo de 7 dias para devolução terminou." (direito de
  arrependimento, CDC art. 49).
- Devolve `200` com o pedido. Eventos `pedido_cancelado` e `devolucao_solicitada`.
**Testes:** cada linha da tabela do M3-04 acionada por `PATCH`; cancelar `entregue` → 409; devolução no 8º dia → 409;
corpo vazio → 400.

## M3-06 — Chamados de pós-venda
Branch `feat/m3-chamados` · Sexta · Arquivos: `app/pos_compra/{rotas,validacao,repositorio}.py` (coleção `chamados`)

**Especificação:**
- `POST /pedidos/<pedido_id>/chamados` com `assunto` (3 a 80) e `mensagem` (10 a 1000) → `201` +
  `Location: /pedidos/<pedido_id>/chamados/<chamado_id>`, `status: "aberto"`, evento `chamado_aberto`.
- `GET /pedidos/<pedido_id>/chamados`: lista do pedido, mais recentes primeiro.
- `GET /pedidos/<pedido_id>/chamados/<chamado_id>`: um chamado.
- Pedido ou chamado de outro usuário, ou chamado de outro pedido → `404`.
**Testes** (`tests/test_chamados.py`): 201 com `Location` que responde 200; validação 400; isolamento 404; chamado de
outro pedido → 404.

## M3-07 — Gancho `compra_automatica`
Branch `feat/m3-compra-automatica` · Sexta

**Especificação** (contrato, seção 6.2):
- `servicos.executar_compra_automatica(solicitacao)`:
  - confirma que `status == "aguardando_aprovacao"` e que `avaliacao.permitida` e `avaliacao.compra_automatica` são
    verdadeiros; se não, devolve `None`;
  - chama `emitir_autorizacao(..., origem="automatica")` (sem senha) e `criar_pedido`, as mesmas funções das rotas,
    sem duplicar lógica;
  - devolve `{"autorizacao_id": str, "pedido_id": str}`;
  - por motivo de negócio (ex.: o status mudou no meio) devolve `None`, sem lançar exceção.
- Registro em `app/pagamento/rotas.py`:
  `bp.record_once(lambda estado: estado.app.extensions.setdefault("compra_automatica", executar_compra_automatica))`.
**Testes** (`tests/test_compra_automatica.py`):
- o gancho existe em `app.extensions`;
- com solicitação automática inserida pelo auxiliar, gera autorização `automatica` e pedido `aguardando_pagamento`, e a
  solicitação fica `aprovada`;
- solicitação manual ou já `aprovada` → `None` e nada criado;
- evento `autorizacao_emitida` com `origem: "automatica"`.

## M3-08 — Testes de contrato e coleção Postman
Branch: a da última tarefa ou `chore/m3-contrato` · Sexta

**Especificação:**
- `tests/test_contrato_pagamento.py`: as 12 rotas do M3 existem no `app.url_map`, com as regras exatas da seção 2 do
  contrato, e respondem `401` sem token.
- `docs/postman/pagamento-pos-compra.postman_collection.json`: as 12 rotas com exemplos, guardando `autorizacaoId`,
  `pedidoId`, `txid` e `chamadoId` como variáveis da coleção.
**Aceite:**
- [x] Suíte inteira verde, sem rede.
- [x] Toda transição de status do pedido e da solicitação coberta por teste.
- [x] Nenhum teste depende de código do M1 ou do M2.
