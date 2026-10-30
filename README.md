# Agentic Commerce — API

O Agentic Commerce transforma uma lista de compras em ofertas comparadas e uma cesta
explicável. O usuário define políticas de preço e autonomia; a API pode preparar uma
compra para aprovação manual ou aprová-la automaticamente quando a política permitir.

A API Flask recebe o cliente React do repositório separado `agentic-commerce-web`,
guarda os dados no MongoDB Atlas e protege as rotas com JWT. Endereço por CEP, catálogo,
autorização, Pix simulado, pós-compra e auditoria participam do mesmo fluxo.

**Disponibilidade:** a implantação na EC2 está pendente; por enquanto, execute a API
localmente com as instruções abaixo.

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (no Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # preencha com os valores do Blackboard
python scripts/testar_atlas.py  # opcional: confere a conexão com o Atlas
flask --app wsgi run --debug    # http://localhost:5000/health
```

Testes (usam um banco em memória, não precisam do Atlas):

```bash
pytest
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha os valores no arquivo ignorado pelo Git.
`MONGO_URI` e `JWT_SECRET_KEY` são obrigatórias. As demais chaves do contrato são:

- Banco e autenticação: `MONGO_DB_NAME`, `JWT_EXPIRA_HORAS`.
- HTTP e hospedagem: `CORS_ORIGINS`, `HTTP_TIMEOUT_SEGUNDOS`, `PROXY_FIX`.
- Catálogo: `CATALOGO_PROVEDOR`, `ML_CLIENT_ID`, `ML_CLIENT_SECRET`,
  `ML_REDIRECT_URI`, `ML_REFRESH_TOKEN`, `ML_VENDEDORES`.
- Simulação e autorização: `PIX_EXPIRACAO_MINUTOS`,
  `AUTORIZACAO_VALIDADE_MINUTOS`, `SIMULACAO_ENVIO_MINUTOS`,
  `SIMULACAO_ENTREGA_MINUTOS`.

O arquivo `.env.example` documenta os padrões sem guardar credenciais reais.

## Estrutura

Cada módulo do diagrama de pacotes é um blueprint em `app/`:

| Pasta | Módulo | Rotas |
|---|---|---|
| `autenticacao/` | Autenticação e perfil | `/usuarios`, `/usuarios/me`, `/sessoes` |
| `politicas/` | Políticas e governança | `/politicas` |
| `solicitacoes/` | Orquestrador de solicitações | `/solicitacoes` |
| `pagamento/` | Aprovação e pagamento | `/autorizacoes`, `/pedidos` |
| `pos_compra/` | Pós-compra | `/pedidos/{id}`, `/pedidos/{id}/chamados` |
| `auditoria/` | Auditoria | `/auditoria` |

Arquivos compartilhados:

- `app/__init__.py`: `create_app`, que carrega a configuração, o CORS, o JWT e registra os blueprints.
- `app/erros.py`: padrão de erros. Para responder com erro, use `raise ErroApi(status, "mensagem")`.
- `app/banco.py`: `banco()` devolve o banco do Atlas; `para_object_id` e `documento_para_json` convertem ids.
- `app/autenticacao/identidade.py`: `usuario_atual_id()` devolve o id de quem fez a requisição.

## Rotas do MVP

| Módulo | Método | Caminho |
|---|---|---|
| Conta | GET | `/health` |
| Conta | POST | `/usuarios` |
| Conta | POST | `/sessoes` |
| Conta | GET | `/usuarios/me` |
| Conta | PATCH | `/usuarios/me` |
| Políticas | GET | `/politicas` |
| Políticas | POST | `/politicas` |
| Políticas | GET | `/politicas/<politica_id>` |
| Políticas | PUT | `/politicas/<politica_id>` |
| Políticas | DELETE | `/politicas/<politica_id>` |
| Auditoria | GET | `/auditoria` |
| Solicitações | POST | `/solicitacoes` |
| Solicitações | GET | `/solicitacoes` |
| Solicitações | GET | `/solicitacoes/<solicitacao_id>` |
| Solicitações | DELETE | `/solicitacoes/<solicitacao_id>` |
| Pagamento | POST | `/solicitacoes/<solicitacao_id>/autorizacoes` |
| Pagamento | GET | `/autorizacoes` |
| Pagamento | GET | `/autorizacoes/<autorizacao_id>` |
| Pagamento | DELETE | `/autorizacoes/<autorizacao_id>` |
| Pagamento | POST | `/pedidos` |
| Pagamento | GET | `/pedidos` |
| Pagamento | POST | `/simulador-pix/pagamentos` |
| Pós-compra | GET | `/pedidos/<pedido_id>` |
| Pós-compra | PATCH | `/pedidos/<pedido_id>` |
| Pós-compra | POST | `/pedidos/<pedido_id>/chamados` |
| Pós-compra | GET | `/pedidos/<pedido_id>/chamados` |
| Pós-compra | GET | `/pedidos/<pedido_id>/chamados/<chamado_id>` |

## Convenções da API

- Recursos no plural; `201` com `Location` ao criar, `204` ao excluir.
- `PATCH` muda estados; conflitos respondem `409` e compras recusadas pela política, `422`.
- Erros sempre em JSON: `{"erro": "mensagem para o usuário", "detalhes": {"campo": "problema"}}`.
- Toda rota, exceto `/health`, `POST /usuarios` e `POST /sessoes`, exige `Authorization: Bearer <token>`.
- Os documentos guardam `usuario_id` e toda consulta filtra por ele: o recurso de outra pessoa responde 404.

## Políticas de compra

```json
{
  "nome": "Eletrônicos",
  "teto_por_compra": 500,
  "categorias": ["smartphones", "laptops"],
  "lojas": [],
  "nivel_autonomia": "automatica",
  "ativa": true
}
```

- `categorias` e `lojas` vazias aceitam qualquer uma; a comparação ignora maiúsculas.
- `nivel_autonomia`: `manual` (o usuário aprova cada compra com a senha, padrão) ou
  `automatica` (o agente compra sozinho quando a oferta cabe na política).

O validador fica em `app/politicas/regras.py`. O orquestrador e a aprovação usam assim:

```python
from app.politicas import repositorio
from app.politicas.regras import avaliar_oferta

avaliacao = avaliar_oferta(oferta, repositorio.listar(usuario_id))
avaliacao.permitida          # alguma política ativa aceita a oferta?
avaliacao.compra_automatica  # o agente pode comprar sem pedir a senha?
avaliacao.motivos            # por que as políticas recusaram (para a explicação)
```

A oferta precisa de `preco`, `categoria` e `loja`; `frete` é opcional e entra no teto.
Sem nenhuma política ativa, tudo é permitido, mas sempre com aprovação manual.

## APIs externas e limites do MVP

O `PATCH /usuarios/me` consulta o ViaCEP para completar o endereço. O catálogo
`combinado` reúne ofertas locais (`fixo`) e produtos da API externa DummyJSON
no mesmo ranking. Na EC2, configure `CATALOGO_PROVEDOR=combinado`; para
desenvolvimento local, `fixo` funciona sem acesso à API externa. O React
chama somente esta API Flask.

O Mercado Livre não integra o catálogo do MVP; as credenciais `ML_*` ficam
vazias. A cobrança Pix e a compra são simuladas: o sistema não movimenta
dinheiro nem conclui compra no Mercado Livre.
`POST /simulador-pix/pagamentos` demonstra a transição de estados do pedido.

## Coleção de requisições

`docs/agentic-commerce.postman_collection.json` (importa no Postman ou no Insomnia).
A coleção cobre as 27 rotas em pastas por módulo e cria recursos de teste
separados para revogação, cancelamento e devolução. Cadastro e Login guardam
o token para as requisições seguintes. `baseUrl` começa em
`http://localhost:5000`; troque pelo endereço de produção quando existir.

Para executar a coleção inteira, use o Runner com intervalo de 5 segundos
entre requisições: ele consulta o pedido até a entrega simulada, por até
nove minutos. Com as simulações zeradas apenas no ambiente local, o
intervalo pode ser menor. A execução cria contas e pedidos de teste no
banco configurado.

## Ensaio ponta a ponta local

Com a API Flask em execução e o Atlas de desenvolvimento configurado, rode:

```bash
python scripts/ensaio_ponta_a_ponta.py --base-url http://localhost:5000
```

Para exercitar também o catálogo externo, inicie a API com
`CATALOGO_PROVEDOR=dummyjson` no ambiente do processo; o padrão `fixo`
usa ofertas locais.

O ensaio cria duas contas de teste, consulta o ViaCEP pelo CEP `01001000`,
percorre os fluxos automático e manual e aguarda a entrega simulada por até
oito minutos. Use `--item` para escolher um produto existente no catálogo
configurado. O script sai com código diferente de zero se algum passo falhar.

## Deploy na EC2

O deploy usa Ubuntu 24.04 LTS, Gunicorn e nginx. Os arquivos em `deploy/`
pressupõem o clone em `/opt/agentic-commerce-api` e o build do React em
`/var/www/agentic-commerce-web`. A equipe do frontend publica o build
nesse segundo caminho.

1. No console da AWS, crie uma instância t2.micro ou t3.micro com Ubuntu
   24.04 LTS. Restrinja SSH (porta 22) ao IP de administração e abra HTTP
   (porta 80). Anote o IP público; use Elastic IP se a conta permitir.
2. Entre por SSH como `ubuntu` e prepare o clone da branch `main`:

   ```bash
   sudo apt update
   sudo apt install -y python3-venv git nginx curl
   sudo mkdir -p /opt/agentic-commerce-api
   sudo chown ubuntu:ubuntu /opt/agentic-commerce-api
   git clone URL_DO_REPOSITORIO /opt/agentic-commerce-api
   cd /opt/agentic-commerce-api
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

   Substitua `URL_DO_REPOSITORIO` pela URL do repositório da API.
3. Crie o arquivo de ambiente fora do clone e edite-o diretamente na
   instância:

   ```bash
   sudo touch /etc/agentic-commerce-api.env
   sudo chown root:root /etc/agentic-commerce-api.env
   sudo chmod 600 /etc/agentic-commerce-api.env
   sudoedit /etc/agentic-commerce-api.env
   ```

   Preencha `MONGO_URI`, `JWT_SECRET_KEY`,
   `MONGO_DB_NAME=agentic_commerce`, `PROXY_FIX=1`,
   `CATALOGO_PROVEDOR=combinado` e `CORS_ORIGINS` com a origem do frontend.
   Mantenha as variáveis `ML_*` vazias. Não coloque valores reais no Git.
4. Libere o IP público da instância no *Network Access* do Atlas. Instale
   e ative o serviço da API:

   ```bash
   sudo cp deploy/agentic-commerce-api.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now agentic-commerce-api
   ```

5. Instale e ative o site nginx:

   ```bash
   sudo cp deploy/nginx-agentic-commerce.conf /etc/nginx/sites-available/agentic-commerce
   sudo ln -s /etc/nginx/sites-available/agentic-commerce /etc/nginx/sites-enabled/agentic-commerce
   if [ -L /etc/nginx/sites-enabled/default ]; then
       sudo unlink /etc/nginx/sites-enabled/default
   fi
   sudo nginx -t
   sudo systemctl enable --now nginx
   sudo systemctl reload nginx
   ```
6. Fora da AWS, confira `http://IP_PUBLICO_DA_EC2/api/health`: deve
   responder `200` com `"banco": "ok"`. Autentique-se e confira se
   `POST /api/politicas` devolve um `Location` iniciado por `/api`.
   Repita o teste de saúde depois de reiniciar a instância.

Para atualizar o clone em produção, execute `bash deploy/atualizar.sh` como
`ubuntu`. O script exige a branch `main`, faz `git pull --ff-only`, instala
as dependências, reinicia o serviço e verifica `/health` localmente.
Consulte os logs com
`sudo journalctl -u agentic-commerce-api -n 50 --no-pager`.
