# Contrato de integração do MVP

Este arquivo é o **único ponto de acoplamento** entre os módulos M1, M2 e M3. Cada módulo pode ser implementado e
testado sozinho porque depende só deste contrato, e não do código dos outros. **Congelado na quarta, 28/10, às 12h.**
Depois disso, qualquer mudança exige PR neste arquivo aprovado pelos 3 devs (seção 9).

## 1. Convenções

**REST nível 2 de Richardson** (rubrica):
- URIs são substantivos no plural (exceções aceitas: `/health`, `/usuarios/me`, `/auditoria`). Nenhum verbo na URI:
  mudar estado é `PATCH` no recurso (ex.: cancelar pedido = `PATCH /pedidos/{id}` com `{"status": "cancelado"}`).
- `GET` não altera dados visíveis ao cliente. Exceção documentada: as transições simuladas do pedido (expiração,
  envio, entrega), aplicadas na leitura porque representam algo que já aconteceu "fora" do sistema.
- Criar = `201` + cabeçalho `Location` com a URI do recurso criado (via `url_for`). Excluir ou revogar = `204` sem
  corpo. `PUT` substitui o recurso inteiro; `PATCH` altera em parte.
- Erros sempre em JSON `{"erro": "mensagem para o usuário", "detalhes": {"campo": "problema"}}` (`detalhes` só quando
  houver), sempre via `raise ErroApi(status, mensagem, detalhes)` de `app/erros.py`. Significado: `400` corpo inválido ·
  `401` sem token, token inválido ou senha errada · `404` recurso inexistente **ou de outro usuário** · `405` método não
  permitido · `409` conflito com o estado atual · `422` regra de negócio violada · `502` serviço externo falhou ·
  `503` banco indisponível (só no `/health`).

**Código** (padrão do repositório; siga `app/politicas/` como modelo):
- Camadas por módulo: `rotas.py` (HTTP fino) → `validacao.py` (acumula todos os erros por campo e lança
  `ErroApi(400, ..., erros)`) → `repositorio.py` (único lugar que acessa a coleção; toda consulta filtra por
  `usuario_id`) → `regras.py` (funções puras, sem Flask nem banco).
- Utilitários existentes: `ler_json()` (`app/erros.py`), `banco()`, `para_object_id()` (id malformado → 404) e
  `documento_para_json()` (`_id` → `id`) em `app/banco.py`, `usuario_atual_id()` em `app/autenticacao/identidade.py`.
- Autenticação é global (`proteger_rotas`): rota nova já exige JWT; `@jwt_required()` é opcional. Só o M1 pode
  tornar uma rota pública.
- Tudo em português: módulos, funções, variáveis, mensagens, docstrings e nomes de testes. Docstring curta no topo de
  cada módulo; constantes em MAIÚSCULAS; linhas de até ~115 colunas; aspas duplas.
- Datas em UTC (`datetime.now(timezone.utc)`), por uma função `agora()` do módulo, que os testes trocam via
  `monkeypatch`. Campos de data concordam com o recurso: `criada_em`/`atualizada_em` (solicitação, autorização,
  política) e `criado_em`/`atualizado_em` (usuário, pedido, chamado, evento).
- Valores em reais são `float` arredondados a 2 casas.
- Testes: mongomock + fixtures `app`, `client`, `auth` e `cabecalho_de` de `tests/conftest.py`; um comportamento por
  teste; integrações externas sempre mockadas.

## 2. Rotas do MVP (27)

As regras de URL do Flask abaixo (com os nomes dos parâmetros) são as que o teste global de contrato vai conferir no
sábado. Rotas marcadas como públicas não exigem token; todas as outras também podem responder `401`.

| Módulo | Método e regra Flask | Pública | O que faz | Sucesso | Erros |
|---|---|---|---|---|---|
| M1 | `GET /health` | sim | API e ping no Atlas (pronta) | 200 | 503 |
| M1 | `POST /usuarios` | sim | Cadastro (pronta) | 201 | 400, 409 |
| M1 | `POST /sessoes` | sim | Login; devolve o JWT (pronta) | 200 | 400, 401 |
| M1 | `GET /usuarios/me` | | Perfil completo | 200 | — |
| M1 | `PATCH /usuarios/me` | | Atualiza o perfil; endereço via ViaCEP | 200 | 400, 502 |
| M1 | `GET /politicas` | | Lista as políticas (pronta) | 200 | — |
| M1 | `POST /politicas` | | Cria política (pronta) | 201 | 400 |
| M1 | `GET /politicas/<politica_id>` | | Obtém política (pronta) | 200 | 404 |
| M1 | `PUT /politicas/<politica_id>` | | Substitui política (pronta) | 200 | 400, 404 |
| M1 | `DELETE /politicas/<politica_id>` | | Remove política (pronta) | 204 | 404 |
| M1 | `GET /auditoria` | | Trilha de eventos do usuário, paginada | 200 | 400 |
| M2 | `POST /solicitacoes` | | Lista de compras → catálogo → políticas → ranking → cesta | 201 | 400, 502 |
| M2 | `GET /solicitacoes` | | Histórico (resumo) | 200 | — |
| M2 | `GET /solicitacoes/<solicitacao_id>` | | Solicitação completa, com a explicação | 200 | 404 |
| M2 | `DELETE /solicitacoes/<solicitacao_id>` | | Cancela antes da aprovação | 204 | 404, 409 |
| M3 | `POST /solicitacoes/<solicitacao_id>/autorizacoes` | | Aprova com senha e gera a autorização limitada | 201 | 400, 401, 404, 409, 422 |
| M3 | `GET /autorizacoes` | | Autorizações ativas | 200 | — |
| M3 | `GET /autorizacoes/<autorizacao_id>` | | Uma autorização | 200 | 404 |
| M3 | `DELETE /autorizacoes/<autorizacao_id>` | | Revoga | 204 | 404, 409 |
| M3 | `POST /pedidos` | | Usa a autorização (uso único) e gera a cobrança Pix | 201 | 400, 404, 409 |
| M3 | `GET /pedidos` | | Lista os pedidos | 200 | — |
| M3 | `POST /simulador-pix/pagamentos` | | Simula o pagamento de um Pix; devolve o pedido atualizado | 200 | 400, 404, 409 |
| M3 | `GET /pedidos/<pedido_id>` | | Comprovante e status atual | 200 | 404 |
| M3 | `PATCH /pedidos/<pedido_id>` | | Pede cancelamento ou devolução | 200 | 400, 404, 409 |
| M3 | `POST /pedidos/<pedido_id>/chamados` | | Abre chamado de pós-venda | 201 | 400, 404 |
| M3 | `GET /pedidos/<pedido_id>/chamados` | | Lista os chamados do pedido | 200 | 404 |
| M3 | `GET /pedidos/<pedido_id>/chamados/<chamado_id>` | | Um chamado | 200 | 404 |

Blueprints: as rotas do M3 ficam em `app/pagamento/rotas.py` (autorizações, `POST/GET /pedidos`, simulador) e
`app/pos_compra/rotas.py` (`GET/PATCH /pedidos/<pedido_id>` e chamados). Todos os blueprints já estão registrados em
`app/__init__.py`; ninguém precisa editar esse arquivo para criar rota.

## 3. Coleções: quem escreve e quem lê

| Coleção | Escreve | Lê | Observação |
|---|---|---|---|
| `usuarios` | M1 | M2 (`data_nascimento`, `preferencias`, `orcamento_mensal`), M3 (`senha_hash`) | Leitura direta com projeção, só dos campos listados |
| `politicas` | M1 (rotas prontas) | M2, via `app.politicas.repositorio.listar(usuario_id)` (já existe) | O M3 não lê políticas |
| `solicitacoes` | M2 (documento inteiro); M3 (**só** `status` e `atualizada_em`, ver seção 5) | M2, M3 | Esquema na seção 4 |
| `autorizacoes`, `pedidos`, `chamados` | M3 | M3 | Internas do M3 |
| `auditoria` | M1, pelo gancho `registrar_evento` | M1 | Só inserção; nunca alterar nem apagar |
| `integracoes` | M2 | M2 | Tokens do Mercado Livre; nunca expostos pela API. Fora do MVP: só existe com o conector `mercadolivre` (o spike M2-01 escolheu a opção C) |

**Esquema de `usuarios`** (o M1 garante): `_id`, `nome`, `email` (minúsculo), `senha_hash`, `criado_em` (já existem);
o M1-04 acrescenta `data_nascimento` (texto `AAAA-MM-DD`), `endereco` {`cep` (só os 8 dígitos), `logradouro`,
`numero`, `complemento`, `bairro`, `cidade`, `uf`} ou `null` (apagado pelo `PATCH`), `preferencias`
{`marcas_preferidas`: [textos], `marcas_evitadas`: [textos]},
`orcamento_mensal` (número ou `null`) e `atualizado_em`. **Campo ausente = não informado**: M2 e M3 devem tratar a
falta de qualquer um desses campos sem erro.

**Índices** (só o M1 cria, no boot; nenhum módulo depende de índice para estar correto, exceto o e-mail único):
`usuarios.email` (único); `politicas` (`usuario_id`, `criada_em`); `solicitacoes` (`usuario_id`, `criada_em`
decrescente); `autorizacoes` (`usuario_id`, `status`); `pedidos` (`usuario_id`, `criado_em` decrescente) e
`pedidos.autorizacao_id` (único); `chamados` (`pedido_id`, `criado_em`); `auditoria` (`usuario_id`, `criado_em`
decrescente).

## 4. Documento de solicitação (escrito pelo M2, lido pelo M3)

```json
{
  "_id": "ObjectId", "usuario_id": "ObjectId",
  "texto": "arroz 5kg, 2 leites integrais e detergente",
  "itens": [
    {
      "descricao": "arroz 5kg", "quantidade": 1, "status": "com_oferta",
      "recomendada": {
        "id_externo": "MLB123", "fonte": "mercadolivre", "titulo": "Arroz Branco Tipo 1 5kg",
        "marca": "Marca Exemplo", "preco": 27.9, "frete": 0.0, "frete_gratis": true, "prazo_dias": 2, "estoque": 50,
        "categoria": "Arroz", "categorias_caminho": ["Alimentos e Bebidas", "Arroz"], "loja": "Loja Exemplo",
        "avaliacao": 4.7, "preco_por_unidade": 5.58, "unidade": "kg", "link": "https://...", "imagem": "https://...",
        "pontuacao": 0.91, "explicacao": ["Menor preço por kg entre 6 ofertas: R$ 5,58/kg", "Frete grátis"]
      },
      "alternativas": ["até 4 ofertas no mesmo formato da recomendada"],
      "descartadas": 2,
      "explicacao": ["2 ofertas descartadas: loja não permitida pela política Mercado do mês"]
    }
  ],
  "cesta": {"subtotal": 27.9, "frete": 0.0, "total": 27.9, "lojas": ["Loja Exemplo"]},
  "avaliacao": {"permitida": true, "compra_automatica": false, "politica_id": "ObjectId ou null", "motivos": []},
  "status": "aguardando_aprovacao",
  "compra_automatica": null,
  "criada_em": "datetime", "atualizada_em": "datetime"
}
```

- **O M3 só usa estes campos:** `_id`, `usuario_id`, `status`, `itens[].quantidade`, `itens[].status`,
  `itens[].recomendada.{id_externo, titulo, preco, frete, loja}`, `cesta.{total, lojas}` e
  `avaliacao.{permitida, compra_automatica, politica_id, motivos}`. O M2 não pode renomear nem mudar o tipo deles.
- Oferta: os campos obrigatórios são `id_externo`, `fonte`, `titulo`, `preco`, `categoria`, `categorias_caminho` e
  `loja`; os demais podem ser `null` quando a fonte não informa. `marca` alimenta as marcas preferidas e evitadas do
  perfil; `estoque` é a quantidade disponível (aproximada quando a fonte só informa faixas).
- `fonte` no MVP é `fixo` (catálogo local) ou `dummyjson` (catálogo externo); `mercadolivre` fica para depois do MVP.
  O exemplo acima mostra o formato que o conector do Mercado Livre vai ter.
- `texto` é `null` quando a solicitação chega com `itens` já separados.
- `itens[].quantidade` é o número de embalagens da `recomendada` a comprar, o mesmo que entra em `cesta.subtotal`.
  O M2 ajusta a quantidade pedida ao tamanho da embalagem: "2 kg de feijão" com a oferta de 1 kg vira
  `quantidade: 2`, e "Dez ovos" com a caixa de 12 vira `quantidade: 1`. A explicação do item conta o ajuste
  ("Você pediu 2 kg: 2 embalagens de 1 kg").
- Item `sem_oferta` tem `recomendada: null` e fica fora da cesta. `cesta.total` = `subtotal` + `frete`.
- `avaliacao` é calculada pelo M2 sobre a cesta inteira; o M3 confia nela (não reavalia políticas no MVP).
- `compra_automatica` é escrito pelo M2 com o retorno do gancho da seção 6.2 (ou `null`).

## 5. Status da solicitação

| Status | Quem define | Quando | Próximos status |
|---|---|---|---|
| `aguardando_aprovacao` | M2 (criação); M3 (ao revogar a autorização ou quando ela vence sem virar pedido) | Há pelo menos um item com oferta | `aprovada` (M3); removida pelo `DELETE` do M2 |
| `sem_resultado` | M2 (criação) | Nenhum item com oferta | removida pelo `DELETE` do M2 |
| `aprovada` | M3 | Autorização emitida (manual ou automática) | `concluida`, `expirada`, `aguardando_aprovacao` |
| `concluida` | M3 | Pagamento confirmado | — |
| `expirada` | M3 | Pix venceu ou pedido cancelado antes do pagamento | — |

O M3 muda o status com `find_one_and_update`, colocando o status esperado no filtro (ex.:
`{"_id": ..., "usuario_id": ..., "status": "aguardando_aprovacao"}`), e atualiza `atualizada_em`. O `DELETE` do M2 só
remove em `aguardando_aprovacao` ou `sem_resultado`; nos outros status responde `409`.

**Autorização vencida sem pedido.** A autorização tem os status `ativa`, `usada`, `revogada` e `expirada`. Quando uma
autorização `ativa` passa de `expira_em` sem virar pedido, o M3 a marca `expirada` (com `expirada_em` = `expira_em`)
e devolve a solicitação de `aprovada` para `aguardando_aprovacao`: a pessoa pode aprovar de novo ou cancelar. Como as
transições simuladas do pedido, isso é aplicado na leitura: o M3 aplica nas próprias rotas de autorizações e pedidos, e
o M2 pede o mesmo pelo gancho `expirar_autorizacoes` (seção 6.3) antes de ler ou cancelar solicitações.

## 6. Ganchos entre módulos

Cada gancho é registrado pelo módulo que o fornece, no próprio blueprint, com `Blueprint.record_once`, sem editar
`create_app`. Quem consome busca em `current_app.extensions`; gancho ausente = `None` = o consumidor segue sem ele. Nos
testes, o consumidor pode registrar uma versão falsa: `app.extensions["registrar_evento"] = falso`.

### 6.1 `registrar_evento` (fornecido pelo M1, consumido por M2 e M3)

```python
# M1 — app/auditoria/registro.py
def registrar_evento(usuario_id, tipo, recurso_tipo=None, recurso_id=None, dados=None):
    """Grava um evento na trilha de auditoria (só inserção)."""

# M1 — app/auditoria/rotas.py
bp.record_once(lambda estado: estado.app.extensions.setdefault("registrar_evento", registrar_evento))

# M2 e M3 — cada um no próprio módulo (ex.: app/solicitacoes/auditoria.py, app/pagamento/auditoria.py)
from flask import current_app

def auditar(usuario_id, tipo, recurso_tipo=None, recurso_id=None, dados=None):
    """Registra o evento se a auditoria (M1) estiver ativa."""
    registrar = current_app.extensions.get("registrar_evento")
    if registrar is not None:
        registrar(usuario_id, tipo, recurso_tipo, recurso_id, dados)
```

Regras: chame só **depois** de a ação dar certo; `usuario_id` é `ObjectId`; `dados` é um dicionário pequeno e
**nunca** contém senha, hash, token nem `copia_e_cola`.

### 6.2 `compra_automatica` (fornecido pelo M3, consumido pelo M2)

```python
# M3 — app/pagamento/servicos.py
def executar_compra_automatica(solicitacao):
    """Emite a autorização automática e cria o pedido com Pix.

    Devolve {"autorizacao_id": "<id>", "pedido_id": "<id>"} ou None se não foi possível.
    """

# M3 — app/pagamento/rotas.py
bp.record_once(lambda estado: estado.app.extensions.setdefault("compra_automatica", executar_compra_automatica))

# M2 — final de POST /solicitacoes, depois de gravar a solicitação
executar = current_app.extensions.get("compra_automatica")
if executar is not None and pode_comprar_sozinho(solicitacao):
    try:
        resultado = executar(solicitacao)
    except Exception:
        current_app.logger.exception("Falha na compra automática")
        resultado = None
    repositorio.registrar_compra_automatica(usuario_id, solicitacao["_id"], resultado)
solicitacao = repositorio.obter(usuario_id, solicitacao["_id"])  # relê: o M3 pode ter mudado o status
```

- **Pré-condições (`pode_comprar_sozinho`, verificadas pelo M2):** solicitação gravada, `status` =
  `aguardando_aprovacao`, `avaliacao.permitida` e `avaliacao.compra_automatica` verdadeiros e todos os itens
  `com_oferta`.
- **O M3:** confirma o status de forma atômica, cria a autorização (`origem: "automatica"`, sem senha) e o pedido
  (`aguardando_pagamento`, com Pix), muda a solicitação para `aprovada` e devolve os ids como texto. Por motivo de
  negócio devolve `None`, sem lançar exceção.
- **O M2, com resultado `None`:** acrescenta a `avaliacao.motivos` o texto "Não foi possível concluir a compra
  automática; aprove manualmente." e deixa `compra_automatica: null`.
- **Gancho ausente:** a solicitação fica `aguardando_aprovacao` com `avaliacao.compra_automatica: true`, e o usuário
  pode aprovar manualmente.

### 6.3 `expirar_autorizacoes` (fornecido pelo M3, consumido pelo M2)

```python
# M3 — app/pagamento/servicos.py
def expirar_autorizacoes_vencidas(usuario_id, solicitacao_id=None):
    """Expira as autorizações ativas vencidas sem pedido e devolve as solicitações para aprovação."""

# M3 — app/pagamento/rotas.py
bp.record_once(lambda estado: estado.app.extensions.setdefault("expirar_autorizacoes", expirar_autorizacoes_vencidas))

# M2 — no começo de GET /solicitacoes (solicitacao_id=None), GET e DELETE /solicitacoes/<solicitacao_id>
expirar = current_app.extensions.get("expirar_autorizacoes")
if expirar is not None:
    try:
        expirar(usuario_id, solicitacao_id)
    except Exception:
        current_app.logger.exception("Falha ao expirar autorizações vencidas")
```

- **O M3:** muda cada autorização com o status esperado no filtro (`ativa` e vencida), então chamadas repetidas ou
  simultâneas não duplicam nada; para cada uma, devolve a solicitação para `aguardando_aprovacao` e emite
  `autorizacao_expirada`. `solicitacao_id=None` regulariza todas as do usuário.
- **Gancho ausente:** a solicitação continua `aprovada` até a pessoa revogar a autorização ou até uma rota do M3
  aplicar a expiração.
- `DELETE /autorizacoes/<autorizacao_id>` de uma autorização `expirada` responde `204`, como a já revogada: não há mais
  valor reservado.

## 7. Eventos de auditoria

`recurso_tipo` ∈ {`usuario`, `politica`, `solicitacao`, `autorizacao`, `pedido`, `chamado`}.

| Módulo | Tipos de evento |
|---|---|
| M1 | `usuario_cadastrado`, `sessao_iniciada`, `login_recusado` (só quando o e-mail existe), `perfil_atualizado`, `politica_criada`, `politica_substituida`, `politica_removida` |
| M2 | `solicitacao_criada`, `solicitacao_cancelada` |
| M3 | `autorizacao_emitida` (`dados.origem`: `manual` ou `automatica`), `reautenticacao_recusada`, `autorizacao_revogada`, `autorizacao_expirada`, `pedido_criado`, `pagamento_confirmado`, `pedido_expirado`, `pedido_cancelado`, `pedido_entregue`, `devolucao_solicitada`, `chamado_aberto` |

## 8. Configuração

O M1 carrega todas as chaves em `app/config.py` (M1-01), lendo do `.env` e convertendo os números. Os outros módulos
**sempre** leem com o padrão do contrato, para funcionar antes e depois do merge do M1:
`int(current_app.config.get("PIX_EXPIRACAO_MINUTOS", 30))`. Nos testes, passe as chaves em `create_app(config)`.

| Chave | Padrão | Usada por | Para quê |
|---|---|---|---|
| `MONGO_URI` | — (obrigatória) | todos | String `mongodb+srv://` do Atlas |
| `MONGO_DB_NAME` | `agentic_commerce` | todos | Um banco por dev em desenvolvimento |
| `JWT_SECRET_KEY` | — (obrigatória) | M1 | Assinatura dos tokens |
| `JWT_EXPIRA_HORAS` | `8` | M1 | Validade do token (hoje é 15 min, desvio corrigido no M1-01) |
| `CORS_ORIGINS` | `http://localhost:5173` | M1 | Origens do front |
| `HTTP_TIMEOUT_SEGUNDOS` | `8` | M1, M2 | Timeout de ViaCEP e catálogo |
| `PROXY_FIX` | `0` | M1 | `1` na EC2, atrás do nginx (gera `Location` com `/api`) |
| `CATALOGO_PROVEDOR` | `fixo` | M2 | `fixo`, `dummyjson` ou `combinado` (fixo + DummyJSON no mesmo ranking: o da demonstração e da produção). `mercadolivre` fica para depois do MVP e, até lá, impede a API de subir |
| `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, `ML_REFRESH_TOKEN` | vazio | M2 | App do Mercado Livre (só com `mercadolivre`; fora do MVP, ficam vazias) |
| `ML_VENDEDORES` | vazio | M2 | IDs de vendedores, se o spike escolher busca por vendedor (fora do MVP) |
| `PIX_EXPIRACAO_MINUTOS` | `30` | M3 | Validade da cobrança Pix |
| `AUTORIZACAO_VALIDADE_MINUTOS` | `15` | M3 | Validade da autorização limitada |
| `SIMULACAO_ENVIO_MINUTOS`, `SIMULACAO_ENTREGA_MINUTOS` | `2`, `5` | M3 | Ritmo do envio e da entrega simulados |

## 9. Mudanças neste contrato

1. Abra um PR que altere **só** este arquivo, explicando o motivo e o impacto em cada módulo.
2. Os 3 devs aprovam o PR antes do merge; quem é afetado ajusta o próprio módulo em outro PR.
3. Anote a mudança no histórico abaixo.

| Data | Mudança | Aprovada por |
|---|---|---|
| 27/10/2026 | Versão inicial do contrato do MVP | — |
| 27/10/2026 | Seção 4: oferta com `marca` e `estoque`, `texto` nulo quando vierem `itens` e `itens[].quantidade` = embalagens a comprar. Seção 10: corpo de `POST /solicitacoes` e resumo de `GET /solicitacoes` | pendente (3 devs); conferida em 31/10: implementada no `main` e coberta por `tests/test_solicitacoes.py` e `tests/test_contrato_solicitacoes.py` |
| 30/10/2026 | Opção C do spike M2-01 (MVP sem a API do Mercado Livre). Seção 8: `CATALOGO_PROVEDOR=combinado`; `mercadolivre` e as chaves `ML_*` ficam fora do MVP. Seção 3: `integracoes` fora do MVP. Seção 4: valores de `fonte` | pendente (3 devs); conferida em 31/10: implementada no `main` e coberta por `tests/test_config.py` e `tests/test_catalogo_combinado.py` |
| 31/10/2026 | Seções 5, 6.3 e 7: autorização vencida sem pedido vira `expirada` e devolve a solicitação para `aguardando_aprovacao` (gancho `expirar_autorizacoes` e evento `autorizacao_expirada`). Seção 10: 401 da aprovação com `detalhes.senha`; perfil aceita `endereco: null`, devolve o CEP com máscara e aponta o erro do CEP em `endereco.cep`. Seção 3: `endereco` pode ser `null` | pendente (3 devs) |

## 10. Exemplos de resposta para o front

Ids são texto e datas vêm em ISO 8601 (`app/json.py`). Erro, em qualquer rota:
`{"erro": "Política inválida.", "detalhes": {"teto_por_compra": "Informe um valor maior que zero."}}`.

`POST /solicitacoes` recebe **exatamente um** de `{"texto": "arroz 5kg, 2 leites e detergente"}` (3 a 500
caracteres) ou `{"itens": [{"descricao": "arroz 5kg", "quantidade": 1}]}` (1 a 20 itens; `quantidade` inteira de 1 a
99, padrão 1). Corpo inválido responde `400` com o problema de cada campo em `detalhes`.

`POST /solicitacoes` (`201`, `Location: /solicitacoes/<id>`): o documento da seção 4 com `id` no lugar de `_id`.
Quando a compra automática acontece, vem `status: "aprovada"` e
`"compra_automatica": {"autorizacao_id": "...", "pedido_id": "..."}`.

`GET /solicitacoes` (`200`): o resumo de cada solicitação, das mais recentes para as mais antigas:
`[{"id", "texto", "itens": ["arroz 5kg", "leites"], "status", "total", "criada_em"}]`, em que `itens` são as
descrições e `total` é o `cesta.total`. O documento completo vem em `GET /solicitacoes/<solicitacao_id>`.

`POST /pedidos` (`201`, `Location: /pedidos/<id>`):

```json
{
  "id": "6720...", "solicitacao_id": "671f...", "autorizacao_id": "6720...", "status": "aguardando_pagamento",
  "itens": [{"id_externo": "MLB123", "titulo": "Arroz Branco Tipo 1 5kg", "preco": 27.9, "quantidade": 1,
             "loja": "Loja Exemplo"}],
  "total": 27.9,
  "pix": {"txid": "9f1c...", "copia_e_cola": "PIX-SIMULADO-9f1c...", "qr_code_base64": null,
          "expira_em": "2026-10-31T15:30:00+00:00", "pago_em": null},
  "historico": [{"status": "aguardando_pagamento", "em": "2026-10-31T15:00:00+00:00"}],
  "entrega": {"simulada": true},
  "criado_em": "2026-10-31T15:00:00+00:00"
}
```

`GET /pedidos/<id>` tem o mesmo formato, com o status atual (`pago`, `enviado`, `entregue`, `expirado`, `cancelado`,
`devolucao_solicitada` ou `devolvido`) e, quando houver, `reembolso: {"valor", "status": "simulado", "em"}`.

`GET /auditoria?limite=50&antes_de=<id>`:
`{"eventos": [{"id", "tipo", "recurso": {"tipo", "id"}, "dados", "criado_em"}], "proximo": "<id> ou null"}`.

`GET /usuarios/me`: `{"id", "nome", "email", "data_nascimento", "endereco", "preferencias", "orcamento_mensal",
"criado_em"}`, com `null` (ou listas vazias em `preferencias`) nos campos ainda não preenchidos. O `endereco.cep` volta
com máscara (`"01001-000"`); o banco guarda só os dígitos.

`PATCH /usuarios/me`: `"endereco": null` apaga o endereço (o formulário inteiro pode ser enviado sem endereço). CEP
inexistente responde `400` `{"erro": "CEP não encontrado.", "detalhes": {"endereco.cep": "Confira o CEP."}}`, a mesma
chave da validação; ViaCEP fora do ar, lento ou limitando requisições (`429`) responde `502`.

`POST /solicitacoes/<solicitacao_id>/autorizacoes` com senha errada responde `401`
`{"erro": "Senha incorreta.", "detalhes": {"senha": "Senha incorreta. Confira e tente de novo."}}`: é o `detalhes.senha`
que diz ao front que a sessão continua. Um `401` sem `detalhes` (token inválido, vencido ou de usuário inexistente)
encerra a sessão.
