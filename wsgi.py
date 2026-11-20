import os

from app import create_app

# Punto de entrada para Gunicorn: gunicorn --preload -b 0.0.0.0:8000 wsgi:app
app = create_app(os.getenv("FLASK_CONFIG", "prod"))
