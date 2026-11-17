import pytest

from app.errores import DatosInvalidos
from app.extensions import db
from app.models import Grupo
from app.services import usuarios as servicio

NUEVO = {"nombre": "Ana", "email": "ana@test.com", "password": "secreto123"}


def crear(client, **cambios):
    return client.post("/api/usuarios", json={**NUEVO, **cambios})


def test_crear_usuario(client):
    r = crear(client)
    assert r.status_code == 201
    datos = r.get_json()
    assert datos["email"] == "ana@test.com"
    assert "password_hash" not in datos


def test_email_duplicado_es_rechazado(client):
    crear(client)
    r = crear(client, email="ANA@test.com ")
    assert r.status_code == 409
    assert r.get_json()["error"] == "Ya existe un usuario con ese email"


@pytest.mark.parametrize("cambios", [
    {"email": "sin-arroba"},
    {"password": "123"},
    {"nombre": "   "},
])
def test_datos_invalidos(client, cambios):
    assert crear(client, **cambios).status_code == 400


def test_faltan_campos(client):
    r = client.post("/api/usuarios", json={"nombre": "Ana"})
    assert r.status_code == 400
    assert "email" in r.get_json()["error"]


def test_cuerpo_no_json(client):
    r = client.post("/api/usuarios", data="hola")
    assert r.status_code == 400


def test_listar_y_obtener(client):
    id_ana = crear(client).get_json()["id"]
    crear(client, email="beto@test.com", nombre="Beto")
    assert len(client.get("/api/usuarios").get_json()) == 2
    assert client.get(f"/api/usuarios/{id_ana}").get_json()["nombre"] == "Ana"


def test_obtener_inexistente(client):
    r = client.get("/api/usuarios/999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "El usuario no existe"


def test_actualizar(client):
    id_ana = crear(client).get_json()["id"]
    r = client.put(f"/api/usuarios/{id_ana}", json={"nombre": "Ana María", "password": "nueva123"})
    assert r.status_code == 200
    assert r.get_json()["nombre"] == "Ana María"
    login = client.post("/api/auth/login", json={"email": "ana@test.com", "password": "nueva123"})
    assert login.status_code == 200


def test_actualizar_a_email_de_otro_es_rechazado(client):
    crear(client)
    id_beto = crear(client, email="beto@test.com").get_json()["id"]
    r = client.put(f"/api/usuarios/{id_beto}", json={"email": "ana@test.com"})
    assert r.status_code == 409


def test_actualizar_con_datos_invalidos(client):
    id_ana = crear(client).get_json()["id"]
    assert client.put(f"/api/usuarios/{id_ana}", json={"nombre": " "}).status_code == 400
    assert client.put(f"/api/usuarios/{id_ana}", json={"password": "1"}).status_code == 400


def test_eliminar(client):
    id_ana = crear(client).get_json()["id"]
    assert client.delete(f"/api/usuarios/{id_ana}").status_code == 204
    assert client.get(f"/api/usuarios/{id_ana}").status_code == 404


def test_no_se_elimina_usuario_que_pertenece_a_un_grupo(usuarios):
    ana = usuarios[0]
    db.session.add(Grupo(nombre="Casa", creado_por=ana.id, miembros=[ana]))
    db.session.commit()
    with pytest.raises(DatosInvalidos):
        servicio.eliminar(ana.id)


def test_login_correcto(client):
    crear(client)
    r = client.post("/api/auth/login", json={"email": "ana@test.com", "password": "secreto123"})
    assert r.status_code == 200
    assert r.get_json()["nombre"] == "Ana"


@pytest.mark.parametrize("email,password", [
    ("ana@test.com", "incorrecta"),
    ("nadie@test.com", "secreto123"),
])
def test_login_incorrecto(client, email, password):
    crear(client)
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 401
    assert r.get_json()["error"] == "Email o contraseña incorrectos"
