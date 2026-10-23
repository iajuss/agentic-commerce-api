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

## Coleção de requisições

`docs/agentic-commerce.postman_collection.json` (importa no Postman ou no Insomnia).
Rode "Login" primeiro: o token fica guardado para as outras requisições.
