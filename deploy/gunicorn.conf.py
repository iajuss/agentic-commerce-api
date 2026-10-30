"""Configuração do Gunicorn para a API na EC2."""

bind = "127.0.0.1:8000"
workers = 2
timeout = 60
accesslog = "-"
errorlog = "-"
