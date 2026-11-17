import pytest

from app import create_app
from app.extensions import db
from app.models import Usuario


@pytest.fixture
def app():
    """App con TestConfig (SQLite en memoria); la base se recrea en cada prueba."""
    app = create_app("test")
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def usuarios(app):
    """Tres usuarios listos para usar en pruebas de grupos, gastos y pagos."""
    lista = []
    for nombre in ("Ana", "Beto", "Carla"):
        u = Usuario(nombre=nombre, email=f"{nombre.lower()}@test.com")
        u.set_password("secreto123")
        db.session.add(u)
        lista.append(u)
    db.session.commit()
    return lista
