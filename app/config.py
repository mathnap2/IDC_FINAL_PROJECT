import os


class Config:
    """Configuración común. Todo lo sensible viene de variables de entorno."""

    SECRET_KEY = os.getenv("SECRET_KEY", "solo-para-desarrollo")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Orígenes permitidos para el frontend (separados por coma). "*" = cualquiera.
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")


class DevConfig(Config):
    # Sin DATABASE_URL usa un archivo SQLite local para poder correr sin Docker.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///dev.db")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProdConfig(Config):
    # En Azure (dev y prod) DATABASE_URL apunta a PostgreSQL.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")


CONFIGS = {"dev": DevConfig, "test": TestConfig, "prod": ProdConfig}
