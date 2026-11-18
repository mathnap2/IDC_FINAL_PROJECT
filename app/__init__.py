import os

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from app.config import CONFIGS
from app.errores import ErrorAPI
from app.extensions import db


def create_app(config_name=None):
    """App factory: crea la app con la configuración indicada ("dev", "test" o "prod")."""
    config_name = config_name or os.getenv("FLASK_CONFIG", "dev")
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"].split(",")}})

    _registrar_blueprints(app)
    _registrar_errores(app)

    @app.get("/health")
    def health():
        # Azure usa este endpoint para saber si el contenedor está vivo.
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}

    with app.app_context():
        from app import models  # noqa: F401  (registra las tablas en db.metadata)
        db.create_all()

    return app


def _registrar_blueprints(app):
    from app.routes.usuarios import bp as usuarios_bp

    app.register_blueprint(usuarios_bp)
    # Cada integrante registra aquí su blueprint (grupos, gastos, pagos).


def _registrar_errores(app):
    @app.errorhandler(ErrorAPI)
    def error_api(e):
        return jsonify(error=e.mensaje), e.codigo

    @app.errorhandler(HTTPException)
    def error_http(e):
        mensajes = {404: "Recurso no encontrado", 405: "Método no permitido"}
        return jsonify(error=mensajes.get(e.code, e.description)), e.code

    @app.errorhandler(Exception)
    def error_interno(e):
        app.logger.exception("Error no controlado")
        return jsonify(error="Error interno del servidor"), 500
