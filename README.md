# Agentic Commerce — API

API Flask do Agentic Commerce: compra por intenção com autonomia controlada. O frontend
React fica no repositório `agentic-commerce-web` e só conversa com o banco e com as APIs
externas através desta API.

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

## Estrutura

Cada módulo do diagrama de pacotes é um blueprint em `app/`:

| Pasta | Módulo | Rotas |
|---|---|---|
| `autenticacao/` | Autenticação e perfil | `/usuarios`, `/sessoes` |
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

## Convenções da API

- Recursos no plural; `201` com cabeçalho `Location` ao criar, `204` ao excluir.
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

## APIs externas e limitações do MVP

Na EC2, configure `CATALOGO_PROVEDOR=combinado`. Ele reúne ofertas locais
(`fixo`) e produtos da API externa DummyJSON no mesmo ranking. O padrão
`fixo` funciona sem acesso à API externa no desenvolvimento local.

O Mercado Livre não integra o catálogo do MVP. As credenciais `ML_*` ficam
vazias; o sistema não consulta ofertas nem conclui compras nessa plataforma.

## Coleção de requisições

`docs/agentic-commerce.postman_collection.json` (importa no Postman ou no Insomnia).
Rode "Login" primeiro: o token fica guardado para as outras requisições.

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
