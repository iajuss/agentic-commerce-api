"""Ponto de entrada. Desenvolvimento: flask --app wsgi run --debug. Produção: gunicorn wsgi:app."""

from app import create_app

app = create_app()
