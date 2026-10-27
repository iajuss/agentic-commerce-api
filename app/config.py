"""Configuração lida das variáveis de ambiente (arquivo .env em desenvolvimento)."""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "agentic_commerce")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_EXPIRA_HORAS = int(os.getenv("JWT_EXPIRA_HORAS", "8"))
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=JWT_EXPIRA_HORAS)
    # Origens do React autorizadas pelo CORS, separadas por vírgula.
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    HTTP_TIMEOUT_SEGUNDOS = int(os.getenv("HTTP_TIMEOUT_SEGUNDOS", "8"))
    PROXY_FIX = int(os.getenv("PROXY_FIX", "0"))
    CATALOGO_PROVEDOR = os.getenv("CATALOGO_PROVEDOR", "fixo")
    ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "")
    ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")
    ML_REDIRECT_URI = os.getenv("ML_REDIRECT_URI", "")
    ML_REFRESH_TOKEN = os.getenv("ML_REFRESH_TOKEN", "")
    ML_VENDEDORES = os.getenv("ML_VENDEDORES", "")
    PIX_EXPIRACAO_MINUTOS = int(os.getenv("PIX_EXPIRACAO_MINUTOS", "30"))
    AUTORIZACAO_VALIDADE_MINUTOS = int(os.getenv("AUTORIZACAO_VALIDADE_MINUTOS", "15"))
    SIMULACAO_ENVIO_MINUTOS = int(os.getenv("SIMULACAO_ENVIO_MINUTOS", "2"))
    SIMULACAO_ENTREGA_MINUTOS = int(os.getenv("SIMULACAO_ENTREGA_MINUTOS", "5"))
