"""App factory da API do Agentic Commerce."""

from flask import Flask, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request
from werkzeug.middleware.proxy_fix import ProxyFix

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

ENDPOINTS_PUBLICOS = frozenset({"saude.health", "autenticacao.cadastrar_usuario", "autenticacao.criar_sessao"})


def create_app(config=None, cliente_mongo=None):
    """Monta a aplicação. `config` sobrescreve a Config; os testes usam os dois parâmetros."""
    app = Flask(__name__)
    app.json = ProvedorJson(app)
    app.config.from_object(Config)
    app.config.update(config or {})

    if app.config["CATALOGO_PROVEDOR"] not in {"fixo", "mercadolivre", "dummyjson"}:
        raise RuntimeError("CATALOGO_PROVEDOR deve ser fixo, mercadolivre ou dummyjson.")

    if app.config["PROXY_FIX"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    if not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError("JWT_SECRET_KEY não definida. Copie .env.example para .env e preencha.")

    CORS(app, origins=app.config["CORS_ORIGINS"], expose_headers=["Location"])
    registrar_tratadores(app, JWTManager(app))
    iniciar_banco(app, cliente_mongo)

    @app.before_request
    def proteger_rotas():
        # Um endpoint novo também fica protegido, mesmo sem @jwt_required().
        if (
            request.method != "OPTIONS"
            and request.endpoint is not None
            and request.endpoint not in ENDPOINTS_PUBLICOS
        ):
            verify_jwt_in_request()

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app
