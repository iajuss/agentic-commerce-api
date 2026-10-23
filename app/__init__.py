"""App factory da API do Agentic Commerce."""

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from app.auditoria.rotas import bp as auditoria_bp
from app.autenticacao.rotas import bp as autenticacao_bp
from app.banco import iniciar_banco
from app.config import Config
from app.erros import registrar_tratadores
from app.json import ProvedorJson
from app.pagamento.rotas import bp as pagamento_bp
from app.politicas.rotas import bp as politicas_bp
from app.pos_compra.rotas import bp as pos_compra_bp
from app.saude import bp as saude_bp
from app.solicitacoes.rotas import bp as solicitacoes_bp

# Um blueprint por módulo do diagrama de pacotes.
BLUEPRINTS = (
    saude_bp,
    autenticacao_bp,
    politicas_bp,
    solicitacoes_bp,
    pagamento_bp,
    pos_compra_bp,
    auditoria_bp,
)


def create_app(config=None, cliente_mongo=None):
    """Monta a aplicação. `config` sobrescreve a Config; os testes usam os dois parâmetros."""
    app = Flask(__name__)
    app.json = ProvedorJson(app)
    app.config.from_object(Config)
    app.config.update(config or {})

    if not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError("JWT_SECRET_KEY não definida. Copie .env.example para .env e preencha.")

    CORS(app, origins=app.config["CORS_ORIGINS"], expose_headers=["Location"])
    registrar_tratadores(app, JWTManager(app))
    iniciar_banco(app, cliente_mongo)

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app
