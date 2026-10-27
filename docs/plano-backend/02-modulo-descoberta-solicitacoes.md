# M2 — Descoberta e Solicitações (Dev 2)

Leia antes: [README](README.md) (protocolo e cronograma) e [contrato](00-contrato-de-integracao.md).

**Objetivo:** transformar a lista de compras do usuário numa cesta recomendada. O M2 interpreta o texto, busca ofertas
no catálogo (externo + fixo), aplica as políticas, ranqueia com explicação, monta a cesta e, quando a política
permite, dispara a compra automática pelo gancho do M3.

**É dono de:** `app/solicitacoes/` (inclui `catalogo/`), `app/politicas/regras.py`, `scripts/autorizar_mercadolivre.py`,
`docs/spike-mercadolivre.md`, `docs/postman/solicitacoes.postman_collection.json` e os testes `test_solicitacoes*`,
`test_catalogo*`, `test_ranking*`, `test_intencao*`, `test_medidas*` e `test_regras_cesta*`.

**Entrega ao contrato:**
- o documento de solicitação (seção 4) e os status que ele define (seção 5);
- o consumo dos ganchos `registrar_evento` e `compra_automatica` (seção 6);
- o catálogo externo, que cumpre o critério de API externa da rubrica junto com o ViaCEP.

**Não depende de código novo de ninguém:**
- o perfil é lido direto de `usuarios`, com projeção (seção 3 do contrato);
- as políticas vêm de `app.politicas.repositorio.listar` (já existe);
- os ganchos são opcionais (`current_app.extensions.get`).

| Tarefa | Dia | Prioridade |
|---|---|---|
| M2-01 Spike do Mercado Livre | Qua (decisão até 14h) | Obrigatória |
| M2-02 Interface do catálogo e catálogo fixo | Qua | Obrigatória |
| M2-03 Conector do catálogo externo | Qua–Qui | Obrigatória |
| M2-04 Políticas da cesta | Qui | Obrigatória |
| M2-05 Interpretação da lista de compras | Qui | Obrigatória |
| M2-06 Ranking explicável e preço por unidade | Qui–Sex | Obrigatória |
| M2-07 Orquestrador e rotas de solicitações | Sex | Obrigatória |
| M2-08 Testes de contrato e coleção Postman | Sex | Obrigatória |

## M2-01 — Spike do Mercado Livre
Branch `chore/m2-spike-mercadolivre` · Quarta, com limite de tempo: **decisão até 14h**

**Já se sabe (testado em 27/10/2026):**
- sem token, `/sites/MLB/search?q=` responde 403, assim como `/items/{id}` e `/products/search`;
- `GET /categories/{id}` (`MLB1403` = Alimentos e Bebidas) e `GET /sites/MLB/domain_discovery/search?q=<texto>`
  (prevê a categoria, ex.: "leite integral 1L" → `MLB455818`) são públicos;
- a doc oficial "Busca de itens" (31/08/2026) só documenta busca **por vendedor**, com token;
- não existe API de compra para comprador (a compra no MVP é simulada pelo M3).

**Passos:**
1. Criar o app no DevCenter com a conta do time e cadastrar um `redirect_uri` HTTPS estático. Ele precisa bater
   exatamente com o enviado; o `code` chega na barra de endereço mesmo que a página não carregue.
2. `scripts/autorizar_mercadolivre.py`:
   - monta `https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=...&redirect_uri=...&state=...`;
   - recebe o `code` digitado e troca em `POST https://api.mercadolibre.com/oauth/token`
     (`grant_type=authorization_code`, corpo `application/x-www-form-urlencoded`);
   - imprime o `refresh_token`, que vai para o `.env` e **nunca** para o Git.
3. Com o token, testar e anotar status e formato de: `/sites/MLB/search?q=arroz`,
   `/sites/MLB/search?category=MLB263835`, `/sites/MLB/search?seller_id=<id>&category=<id>` e
   `/products/search?site_id=MLB&q=arroz`.

**Portão de decisão** (registrar em `docs/spike-mercadolivre.md`, sem credenciais, e avisar o time):
- **A:** busca por palavra-chave ou categoria funciona → conector `mercadolivre` por busca.
- **B:** só a busca por vendedor funciona → conector `mercadolivre` nos vendedores de `ML_VENDEDORES`, usando a
  categoria do `domain_discovery`.
- **C:** nada funciona até 14h → conector `dummyjson`, com o Mercado Livre só para prever categorias (público).

**Aceite:**
- [ ] Decisão registrada.
- [ ] Respostas de exemplo **sem tokens** salvas em `tests/fixtures/` para os testes do M2-03.

## M2-02 — Interface do catálogo e catálogo fixo
Branch `feat/m2-catalogo` · Quarta

**Especificação:**
- `app/solicitacoes/catalogo/base.py`: classe `Catalogo` com `buscar(termo, limite=10) -> list[dict]` (ofertas no
  formato da seção 4 do contrato) e `validar_oferta(oferta)`, que confere os campos obrigatórios e é usada nos testes
  de todos os catálogos.
- `catalogo/fixo.py` + `catalogo/dados_fixos.json`:
  - pelo menos 40 ofertas em PT-BR cobrindo 12 itens: arroz, feijão, leite, café, açúcar, óleo, macarrão, detergente,
    sabão em pó, papel higiênico, refrigerante e cerveja;
  - 3 ou mais ofertas por item, de lojas, preços e embalagens diferentes (ex.: arroz 1 kg e 5 kg);
  - frete grátis em algumas;
  - cervejas com `categorias_caminho` contendo "Bebidas" e "Cervejas", para os testes de idade.
- A busca não diferencia acentos nem maiúsculas (`unicodedata`): "feijao" encontra "Feijão".
- `catalogo/__init__.py`: `obter_catalogo()` devolve `current_app.extensions["catalogo"]` se já existir (os testes
  colocam um falso ali); senão cria pelo `current_app.config.get("CATALOGO_PROVEDOR", "fixo")` e guarda em
  `current_app.extensions["catalogo"]`.
**Testes** (`tests/test_catalogo.py`):
- `buscar("arroz")` só traz arroz e respeita `limite`;
- toda oferta passa em `validar_oferta`;
- "feijao" encontra feijão;
- termo desconhecido → lista vazia.
**Aceite:**
- [ ] Com `CATALOGO_PROVEDOR=fixo`, tudo funciona sem rede nem credencial.

## M2-03 — Conector do catálogo externo
Branch `feat/m2-catalogo-externo` · Quarta à tarde e quinta · Rubrica: API externa

**Opção A ou B — `catalogo/mercadolivre.py`:**
- Token na coleção `integracoes` (documento `_id: "mercadolivre"`). Na primeira vez, semeia com `ML_REFRESH_TOKEN`.
- Faltando menos de 5 minutos para vencer, renova com `grant_type=refresh_token`. O `refresh_token` é de **uso único**
  (a doc cita o erro "already used") e vale 6 meses.
- Grava o novo par com `find_one_and_update`, filtrando pelo `refresh_token` antigo; se nada casar, outro worker já
  renovou e basta reler. Use o `expires_in` da resposta.
- `401` da API → renova uma vez e repete a chamada.
- Categoria pelo `domain_discovery`; caminho por `GET /categories/{id}` (`path_from_root`), com cache em memória.
  Detalhes por `/items/bulk?ids=` (o multiget `/items?ids=` foi descontinuado).
- Normalização:
  - `preco` ← `price`; `frete_gratis` ← `shipping.free_shipping`; `frete` = 0 se grátis, senão `null`;
  - `prazo_dias` = 2 quando `shipping.logistic_type == "fulfillment"`, senão `null`;
  - `link`, `imagem` e `loja` da resposta.

**Opção C — `catalogo/dummyjson.py`:**
- `GET https://dummyjson.com/products/category/groceries` (27 produtos com `title`, `price`, `rating`, `stock`).
- Os títulos estão em inglês: use um dicionário PT→EN dos itens comuns (arroz→rice, leite→milk, ovos→eggs,
  café→coffee, água→water, suco→juice etc.).
- `fonte: "dummyjson"` e `categorias_caminho: ["Mercearia"]`.

**Nas duas opções:**
- `requests` com `timeout` = `HTTP_TIMEOUT_SEGUNDOS` (padrão 8).
- Timeout, erro de conexão, `429` ou `5xx` → `ErroApi(502, "Catálogo indisponível no momento. Tente novamente em
  instantes.")`.
- Tokens nunca aparecem em log nem em resposta.

**Testes:** com as fixtures do spike e `monkeypatch` em `requests` dentro do adaptador, sem rede. Toda oferta passa em
`validar_oferta`. Na opção A/B, cobrir a renovação de token (vencido → renova → grava o novo `refresh_token`) e o
`401` com uma única nova tentativa.
**Aceite:**
- [ ] Com o provedor externo configurado, `POST /solicitacoes` traz ofertas reais (checagem manual registrada no PR).

## M2-04 — Políticas da cesta
Branch `feat/m2-politicas-cesta` · Quinta · Arquivo: `app/politicas/regras.py`

**Especificação** (funções puras):
- **Categoria pelo caminho:** com `categorias` não vazia, a oferta passa se **algum** nome normalizado de
  `oferta["categorias_caminho"]` estiver na lista da política. Sem caminho, vale `[oferta["categoria"]]`, para que os
  testes atuais de `tests/test_regras.py` continuem válidos.
- **`avaliar_cesta(itens, frete_total, politicas) -> Avaliacao`**, com `itens` = [{`oferta`, `quantidade`}]:
  - permitida se **uma mesma** política ativa aceita todas as ofertas (categoria e loja) **e** `Σ preco × quantidade
    + frete_total ≤ teto_por_compra`;
  - compra automática se essa política for `automatica`;
  - sem política ativa: permitida, sempre manual;
  - `motivos` explicam cada recusa, por política (ex.: "Mercado: total de R$ 320,00 passa do teto de R$ 300,00").
- `avaliar_oferta` mantém assinatura e comportamento.
**Testes** (`tests/test_regras_cesta.py`):
- "bebidas" aceita oferta com caminho [..., "Bebidas", "Cervejas"];
- cesta acima do teto → motivo com o total;
- loja não permitida → recusa;
- duas políticas e só a automática aceita → compra automática;
- sem políticas → permitida e manual;
- `tests/test_regras.py` continua verde.

## M2-05 — Interpretação da lista de compras
Branch `feat/m2-intencao` · Quinta · Arquivo: `app/solicitacoes/intencao.py`

**Especificação:** `interpretar_intencao(texto) -> list[{"descricao", "quantidade"}]`, sem LLM:
- separa por vírgula, ponto e vírgula, quebra de linha e pela palavra " e ";
- quantidade no início, em dígitos ("2 leites", "2x leite") ou por extenso de um a dez ("duas caixas de leite");
  padrão 1;
- medidas ficam na descrição ("arroz 5kg" → quantidade 1);
- itens iguais (normalizados) somam as quantidades;
- descrição de até 80 caracteres; no máximo 20 itens.
**Testes** (`tests/test_intencao.py`): pelo menos 12 casos em tabela, incluindo texto vazio, só separadores, itens
repetidos e "e" dentro de palavra ("feijão" não pode ser cortado).

## M2-06 — Ranking explicável e preço por unidade
Branch `feat/m2-ranking` · Quinta–sexta · Arquivos: `app/solicitacoes/medidas.py` e `ranking.py`

**Especificação:**
- `extrair_medida(titulo)`: reconhece `kg`, `g`, `l`, `ml`, `un`, `unidades` e `rolos`, e também multipacks (`12x1L`,
  `6 x 350ml`, `kit 4 un`). Converte para `kg`, `l` ou `un`; sem medida → `None`. Com medida, a oferta ganha
  `preco_por_unidade` e `unidade`.
- `ranquear(ofertas, preferencias) -> list` de ofertas com `pontuacao` e `explicacao`:
  - critérios normalizados de 0 a 1 dentro do conjunto, com pesos em constantes nomeadas: preço por unidade (ou preço,
    quando não há medida) 0,50; frete 0,20; prazo 0,15; avaliação 0,15;
  - critério ausente vale 0,5 (neutro);
  - marca preferida +0,10; marca evitada −0,20;
  - desempate por menor preço e depois `id_externo`, com resultado determinístico.
- Explicação em frases prontas, com valores no formato de `regras._reais`: "Menor preço por kg entre 6 ofertas:
  R$ 5,58/kg", "Frete grátis", "Frete estimado (a loja não informou)", "Entrega estimada em 2 dias", "Avaliação 4,7",
  "Marca preferida".
**Testes** (`tests/test_ranking.py`, `tests/test_medidas.py`):
- a embalagem de 5 kg mais barata por kg vence a de 1 kg mais barata no total;
- frete grátis desempata ofertas de mesmo preço;
- a mesma entrada gera a mesma ordem;
- a recomendada tem explicação.

## M2-07 — Orquestrador e rotas de solicitações
Branch `feat/m2-solicitacoes` · Sexta · Arquivos: `orquestrador.py`, `rotas.py`, `validacao.py`, `repositorio.py`,
`auditoria.py` em `app/solicitacoes/`

**`POST /solicitacoes`:**
- Corpo com **exatamente um** de `{"texto": "..."}` (3 a 500 caracteres, interpretado pelo M2-05) ou
  `{"itens": [{"descricao", "quantidade"}]}` (1 a 20 itens; quantidade inteira de 1 a 99). Os dois ou nenhum → 400.
- Perfil lido de `usuarios` com projeção de `data_nascimento`, `preferencias` e `orcamento_mensal`; campo ausente =
  não informado.
- Para cada item:
  1. `obter_catalogo().buscar(descricao, limite=10)`;
  2. descartar ofertas recusadas por todas as políticas ativas (`avaliar_oferta` com `preco × quantidade`) e as
     bebidas alcoólicas se o usuário não tiver `data_nascimento` ou for menor de 18 (caminho com "Cervejas",
     "Vinhos", "Destilados" ou "Bebidas Alcoólicas"); guardar quantas foram descartadas e por quê;
  3. `ranquear`: a primeira é a `recomendada` e as 4 seguintes são as `alternativas`;
  4. status `com_oferta` ou `sem_oferta`.
- Cesta:
  - `subtotal` = Σ `preco × quantidade` das recomendadas;
  - `frete` = soma de um frete por loja: 0 se todas as ofertas da loja têm frete grátis; senão o maior frete informado
    ou a constante `FRETE_ESTIMADO = 15.0`, sinalizada na explicação;
  - `total` e `lojas`.
- `avaliacao` = `avaliar_cesta` (M2-04). Orçamento no MVP: se `cesta.total` > `orcamento_mensal`, a compra automática
  é desligada e entra um motivo (a soma do mês fica para depois).
- Status: `sem_resultado` se nenhum item tem oferta; senão `aguardando_aprovacao`.
- Gravar, emitir `solicitacao_criada` via `auditar` (seção 6.1 do contrato) e então tentar a compra automática pelo
  gancho, exatamente como na seção 6.2 do contrato (pré-condições, `try/except`, gravar o resultado e **reler** a
  solicitação).
- Resposta `201` + `Location: /solicitacoes/<id>` + documento (`documento_para_json`).
- Falha do catálogo em **todos** os itens → `502` e nada é gravado; falha em parte → o item fica `sem_oferta` com a
  explicação "Catálogo indisponível para este item".

**`GET /solicitacoes`:** resumo (`id`, `texto` ou descrições, `status`, `cesta.total`, `criada_em`), mais recentes
primeiro. **`GET /solicitacoes/<solicitacao_id>`:** documento completo; de outro usuário → 404.

**`DELETE /solicitacoes/<solicitacao_id>`:** só em `aguardando_aprovacao` ou `sem_resultado` (`204` + evento
`solicitacao_cancelada`). Em qualquer outro status → `409` "Esta solicitação já foi aprovada e não pode ser cancelada."

## M2-08 — Testes de contrato e coleção Postman
Branch: a mesma do M2-07 ou `chore/m2-contrato` · Sexta

**Testes** (`tests/test_solicitacoes.py`), usando um catálogo falso em `app.extensions["catalogo"]` e ganchos falsos
registrados no próprio teste:
- `201` com `Location`;
- texto e itens equivalentes geram a mesma cesta;
- `sem_resultado`;
- oferta fora da política é descartada com motivo;
- menor de idade não recebe cerveja;
- teto da cesta estourado → `permitida` falso;
- catálogo que lança 502 → 502 e coleção vazia;
- isolamento (404);
- `DELETE` → 204 e depois 404; `DELETE` de solicitação `aprovada` (inserida direto no banco) → 409;
- política automática + gancho falso → o gancho recebe a solicitação e o resultado é gravado;
- gancho ausente → a solicitação fica `aguardando_aprovacao`;
- gancho que lança exceção → 201 com o motivo.

`tests/test_contrato_solicitacoes.py`: as 4 rotas do M2 existem no `app.url_map` e respondem `401` sem token.

`docs/postman/solicitacoes.postman_collection.json`: as 4 rotas com exemplos de corpo; o "Criar solicitação" guarda
`solicitacaoId` como variável da coleção.

**Aceite:**
- [ ] Suíte inteira verde, sem rede.
- [ ] O documento gravado bate campo a campo com a seção 4 do contrato.
