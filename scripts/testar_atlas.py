"""Confere se o .env aponta para um cluster do MongoDB Atlas acessível.

Uso (na raiz do repositório, com o ambiente virtual ativo):
    python scripts/testar_atlas.py
"""

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

load_dotenv()

uri = os.getenv("MONGO_URI")
nome_banco = os.getenv("MONGO_DB_NAME", "agentic_commerce")

if not uri or "<" in uri:
    sys.exit("MONGO_URI ausente ou ainda com <usuario>/<senha>. Copie .env.example para .env e preencha.")

try:
    cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
    cliente.admin.command("ping")
except OperationFailure:
    sys.exit("Usuário ou senha do banco recusados. Confira em Database Access no Atlas.")
except ServerSelectionTimeoutError:
    sys.exit("Sem resposta do cluster. Confira se seu IP está liberado em Network Access no Atlas.")
except ConfigurationError as erro:
    sys.exit(f"Connection string inválida: {erro}")

banco = cliente[nome_banco]
print(f"Conectado ao Atlas. Banco '{nome_banco}', coleções: {banco.list_collection_names() or 'nenhuma ainda'}")
