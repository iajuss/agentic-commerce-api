# M1 — Conta, Auditoria e Plataforma (Dev 1)

Leia antes: [README](README.md) (protocolo e cronograma) e [contrato](00-contrato-de-integracao.md).

**Objetivo:** fechar a conta do usuário (perfil com ViaCEP, a API externa garantida da rubrica), criar a trilha de
auditoria que os outros módulos usam pelo gancho `registrar_evento`, corrigir a configuração (token de 15 min), subir a
API na EC2 e liderar a integração de sábado.

**É dono de:** `app/autenticacao/`, `app/auditoria/`, `app/saude.py`, `app/__init__.py`, `app/config.py`,
`app/banco.py`, `tests/conftest.py`, `deploy/`, `scripts/testar_atlas.py`, `scripts/ensaio_ponta_a_ponta.py`,
`requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `docs/agentic-commerce.postman_collection.json` e as
linhas de auditoria em `app/politicas/rotas.py`.

**Entrega ao contrato:** gancho `registrar_evento` (seção 6.1), esquema de `usuarios` (seção 3), todas as chaves de
configuração (seção 8), índices (seção 3) e o deploy.

| Tarefa | Dia | Prioridade |
|---|---|---|
| M1-01 Configuração do MVP e token | Qua (merge até 12h) | Obrigatória |
| M1-02 Índices no boot | Qua | Obrigatória |
| M1-03 Auditoria e gancho `registrar_evento` | Qua–Qui | Obrigatória |
| M1-04 Perfil `GET/PATCH /usuarios/me` com ViaCEP | Qui | Obrigatória |
| M1-05 Refatoração de cadastro e login | Qui–Sex | Desejável |
| M1-06 Guarda-corpos de teste | Sex | Obrigatória |
| M1-07 Deploy na EC2 | Sex | Obrigatória |
| M1-08 Integração e entrega | Sáb–Dom | Obrigatória |

## M1-01 — Configuração do MVP e correção do token
Branch `fix/m1-configuracao-token` · Quarta, merge até 12h (PR pequeno; os outros módulos só ganham com ele)

**Problema atual:** `JWT_ACCESS_TOKEN_EXPIRES` não está configurado, então o token vale 15 minutos (padrão do
flask-jwt-extended) e o front desloga o usuário a cada 15 minutos.
**Especificação:**
- `app/config.py`: todas as chaves da seção 8 do contrato, com os mesmos padrões; números convertidos com `int(...)`;
  `JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=JWT_EXPIRA_HORAS)`.
- `app/__init__.py`:
  - constante de módulo `ENDPOINTS_PUBLICOS = frozenset({"saude.health", "autenticacao.cadastrar_usuario",
    "autenticacao.criar_sessao"})` usada pelo `proteger_rotas` no lugar do conjunto local;
  - com `PROXY_FIX` verdadeiro, `app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)`
    (`werkzeug.middleware.proxy_fix`);
  - `CATALOGO_PROVEDOR` fora de {`fixo`, `mercadolivre`, `dummyjson`} → `RuntimeError` com mensagem clara.
**Testes** (`tests/test_config.py`):
- o token de `POST /sessoes` tem `exp - iat` = 8 h (`decode_token`);
- com `PROXY_FIX=1` e o cabeçalho `X-Forwarded-Prefix: /api`, `POST /politicas` devolve `Location: /api/politicas/<id>`;
- provedor desconhecido → `RuntimeError`.
**Aceite:**
- [x] Os 48 testes atuais continuam passando.
- [x] Token válido por 8 h.
- [x] Todas as chaves do contrato estão no `Config`.

## M1-02 — Índices no boot
Branch `chore/m1-indices` · Quarta

**Especificação:** `criar_indices(db)` em `app/banco.py`, chamada por `iniciar_banco`, cria com `create_index`
(idempotente) todos os índices da seção 3 do contrato. Remover o `create_index("email", unique=True)` de
`app/autenticacao/repositorio.py::criar` (e a docstring que o justifica): índice só no boot.
**Testes:** dois usuários com o mesmo e-mail → `DuplicateKeyError` (o mongomock respeita índice único); chamar
`criar_indices` duas vezes não falha; `test_cadastro_duplicado_ignora_maiusculas` continua passando.
**Aceite:**
- [x] Nenhum repositório cria índice.

## M1-03 — Auditoria e gancho `registrar_evento`
Branch `feat/m1-auditoria` · Quarta–quinta

**Especificação:**
- `app/auditoria/repositorio.py`: só `inserir(evento)` e `listar(usuario_id, limite, antes_de)`, ordenado por `_id`
  decrescente (ordem de criação). Nenhuma função de alterar ou apagar.
- `app/auditoria/registro.py`: `registrar_evento(usuario_id, tipo, recurso_tipo=None, recurso_id=None, dados=None)`
  grava `{usuario_id, tipo, recurso: {tipo, id}, dados, criado_em}`. Remove de `dados` as chaves `senha`,
  `senha_hash`, `token` e `copia_e_cola` (constante `CHAVES_SENSIVEIS`).
- `app/auditoria/rotas.py`:
  - registra o gancho com
    `bp.record_once(lambda estado: estado.app.extensions.setdefault("registrar_evento", registrar_evento))`;
  - `GET /auditoria?limite=50&antes_de=<id>`: `limite` de 1 a 100 (padrão 50); `antes_de` é o id do último evento da
    página anterior; inválido → `400` com `detalhes`;
  - resposta `{"eventos": [...], "proximo": "<id>" | null}`, só do dono do token.
- Instrumentar o que já existe (chamada direta a `registrar_evento`, que é do próprio M1):
  - `usuario_cadastrado` em `POST /usuarios`;
  - `sessao_iniciada` em `POST /sessoes`; `login_recusado` quando o e-mail existe e a senha está errada;
  - `politica_criada`, `politica_substituida` e `politica_removida` em `app/politicas/rotas.py`.
**Testes** (`tests/test_auditoria.py`):
- inserção e ordem;
- isolamento por usuário;
- paginação com `proximo`;
- parâmetros inválidos → 400;
- chaves sensíveis removidas;
- o repositório não expõe `update`/`delete` (inspeção com `dir()`);
- o gancho existe em `app.extensions`;
- há um evento depois de cadastro, login certo, login errado e de cada operação de política.
**Aceite:**
- [x] O gancho funciona para M2 e M3 sem que eles importem nada do M1.

## M1-04 — Perfil `GET/PATCH /usuarios/me` com ViaCEP
Branch `feat/m1-perfil-viacep` · Quinta · Rubrica: API externa

**Problema atual:** o `Location: /usuarios/me` devolvido pelo cadastro aponta para uma rota que ainda não existe (404).
**Especificação:**
- `repositorio.py`: `obter(usuario_id)` e `atualizar(usuario_id, campos)` (grava `atualizado_em`). O
  `_usuario_publico` de `rotas.py` (`{id, nome, email}`, usado por cadastro e login) **não muda**.
- `validacao.py`: `validar_perfil(corpo)` para o `PATCH`. Aceita qualquer subconjunto de:
  - `nome` (1 a 80);
  - `data_nascimento` (`AAAA-MM-DD`, no passado);
  - `endereco` {`cep` (8 dígitos depois de remover o que não é dígito), `numero` (1 a 20), `complemento` (até 60)};
  - `preferencias` {`marcas_preferidas`, `marcas_evitadas`: listas de textos normalizados com `strip().lower()`, sem
    repetição};
  - `orcamento_mensal` (número > 0 ou `null`).

  Campos desconhecidos são ignorados. Inválido → `400` "Perfil inválido." com `detalhes`.
- `viacep.py`: `consultar_cep(cep)` chama `requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=...)` com
  `HTTP_TIMEOUT_SEGUNDOS`. Comportamento do ViaCEP, verificado em 27/10/2026:
  - CEP válido → 200 com `logradouro`, `bairro`, `localidade` e `uf`;
  - CEP inexistente → **200** com `{"erro": "true"}` (trate texto e booleano);
  - formato inválido → 400.

  Tradução: inexistente ou malformado → `ErroApi(400, "CEP não encontrado.", {"cep": "Confira o CEP."})`; timeout, erro
  de conexão ou `5xx` → `ErroApi(502, "Serviço de CEP indisponível no momento. Tente novamente em instantes.")`.
  Mapeamento: `localidade` → `cidade`.
- Rotas:
  - `GET /usuarios/me` → perfil da seção 10 do contrato (sem `senha_hash`; campos não preenchidos como `null`);
    usuário do token inexistente → `401` "Sessão inválida. Faça login novamente.";
  - `PATCH /usuarios/me` → aplica os campos enviados; o endereço junta o que veio do ViaCEP com `numero` e
    `complemento`; devolve o perfil atualizado; evento `perfil_atualizado` com `dados: {"campos": [...]}`.
**Testes** (`tests/test_perfil.py`, com `monkeypatch` em `app.autenticacao.viacep.requests.get` e fixtures em
`tests/fixtures/viacep_*.json`):
- `GET` de usuário recém-cadastrado;
- seguir o `Location` do cadastro com o token do login → 200;
- `PATCH` só de `nome` preserva o endereço;
- CEP inexistente → 400; timeout → 502;
- `data_nascimento` futura → 400;
- o perfil é sempre o do token.
**Aceite:**
- [x] Nenhum teste acessa o ViaCEP de verdade.
- [x] Cadastro e login continuam com o mesmo formato de resposta.

## M1-05 — Refatoração de cadastro e login (desejável)
Branch `fix/m1-ajustes-autenticacao` · Quinta–sexta, se o resto estiver em dia

**Especificação:**
- Mover para `app/autenticacao/validacao.py` (`validar_cadastro`, `validar_login`) as regras e a constante `EMAIL` que
  estão em `rotas.py`, **sem mudar** status, mensagens nem formato.
- Quando o e-mail não existe, rodar `check_password_hash` contra um hash fixo gerado no carregamento do módulo. Hoje o
  login responde em ~0,7 ms com e-mail inexistente contra ~89 ms com e-mail existente, o que revela quais e-mails estão
  cadastrados.
- Quebrar as linhas 57 e 99 de `tests/test_autenticacao.py` (mais de 115 colunas).
**Aceite:**
- [x] Os testes atuais de autenticação passam sem mudar as asserções.
- [x] Novo teste confirma que `check_password_hash` é chamado mesmo com e-mail inexistente.

## M1-06 — Guarda-corpos de teste
Branch `chore/m1-guarda-corpos` · Sexta

**Especificação:**
- `tests/conftest.py`: fixture `autouse` que troca `requests.sessions.Session.request` por uma função que lança
  `RuntimeError("Chamada HTTP real em teste: mocke o adaptador.")`. Os testes que fazem `monkeypatch` da função do
  adaptador (ex.: `requests.get` dentro de `viacep.py`) continuam funcionando.
- `tests/test_contrato_conta.py`: as rotas do M1 no contrato existem no `app.url_map`; as públicas são exatamente as de
  `ENDPOINTS_PUBLICOS`; as demais respondem `401` sem token.
**Aceite:**
- [x] Suíte inteira verde.
- [x] Um teste que tente acessar a rede falha com a mensagem acima.

## M1-07 — Deploy na EC2
Branch `feat/m1-deploy-ec2` · Sexta (sobe o que já estiver no `main`; no sábado entra o resto) · Rubrica: EC2 e Atlas

**Entregáveis no repositório:**
- `gunicorn==26.2.0` no `requirements.txt`;
- `deploy/gunicorn.conf.py` (`bind = "127.0.0.1:8000"`, `workers = 2`, `timeout = 60`, logs no stdout);
- `deploy/agentic-commerce-api.service` (systemd): `EnvironmentFile=/etc/agentic-commerce-api.env`,
  `ExecStart=<clone>/.venv/bin/gunicorn -c deploy/gunicorn.conf.py wsgi:app`, `Restart=always`;
- `deploy/nginx-agentic-commerce.conf`:
  - `location /api/ { proxy_pass http://127.0.0.1:8000/; }` com os cabeçalhos `Host`, `X-Forwarded-For`,
    `X-Forwarded-Proto` e `X-Forwarded-Prefix /api`;
  - `location /` servindo o build do React (`try_files $uri /index.html`), que o front publica;
- `deploy/atualizar.sh`: `git pull --ff-only`, `pip install -r requirements.txt`, `systemctl restart` e
  `curl -fsS http://127.0.0.1:8000/health`.

**Passos na AWS:**
- Ubuntu 24.04 LTS (t2.micro ou t3.micro), com Elastic IP se a conta permitir.
- Security group com 22 (só o IP de quem administra) e 80 (público).
- Instalar `python3-venv`, `git` e `nginx`.
- Clonar o repositório e criar o `.venv`.
- Criar `/etc/agentic-commerce-api.env` (dono root, `chmod 600`, **fora** do clone) com `MONGO_DB_NAME=agentic_commerce`,
  `PROXY_FIX=1`, `CORS_ORIGINS=http://<ip-publico>` (mais `http://localhost:5173`, se o front local for usar a
  produção) e os demais valores reais.
- No Atlas, liberar o IP da EC2 em *Network Access*.
- `systemctl enable --now agentic-commerce-api` e ativar o site do nginx.

**Aceite:**
- [x] De fora da AWS, `curl -i http://<ip>/api/health` → `200` com `"banco": "ok"`.
- [x] `POST /api/politicas` devolve `Location` com `/api`.
- [x] Depois de reiniciar a instância, a API volta sozinha.
- [x] O README tem o link de produção e o passo a passo, sem nenhum segredo.

## M1-08 — Integração e entrega
Sábado e domingo · Lidera o roteiro de [04-integracao-e-entrega.md](04-integracao-e-entrega.md): teste global de
contrato, ensaio ponta a ponta, Postman unificado, README final, deploy final e envio das credenciais pelo Blackboard.
