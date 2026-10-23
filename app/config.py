"""Configuração lida das variáveis de ambiente (arquivo .env em desenvolvimento)."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "agentic_commerce")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    # Origens do React autorizadas pelo CORS, separadas por vírgula.
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
