"""Pruebas UAT: se ejecutan contra una API desplegada (por defecto, el ambiente dev de Azure).

    UAT_BASE_URL=https://app-cc-api-dev-xxxx.azurewebsites.net pytest uat -o addopts=""

Usan HTTP real (requests), no el cliente de pruebas de Flask, y borran lo que crean.
"""

import os
import time
import uuid

import pytest
import requests

# El plan F1 de Azure no tiene Always On: la primera petición tras un rato inactivo puede tardar.
ESPERA_MAXIMA_S = int(os.getenv("UAT_ESPERA_MAXIMA", "300"))


@pytest.fixture(scope="session")
def base_url():
    url = os.getenv("UAT_BASE_URL", "").rstrip("/")
    if not url:
        pytest.fail("Falta la variable UAT_BASE_URL con la URL de la API a probar")

    limite = time.monotonic() + ESPERA_MAXIMA_S
    ultimo_error = None
    while time.monotonic() < limite:
        try:
            r = requests.get(f"{url}/health", timeout=30)
            if r.status_code == 200:
                return url
            ultimo_error = f"/health respondió {r.status_code}"
        except requests.RequestException as e:
            ultimo_error = str(e)
        time.sleep(10)
    pytest.fail(f"La API no respondió en {ESPERA_MAXIMA_S}s: {ultimo_error}")


@pytest.fixture(scope="session")
def api(base_url):
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "cuentas-claras-uat"

    class Api:
        def __call__(self, metodo, ruta, **kwargs):
            kwargs.setdefault("timeout", 30)
            return sesion.request(metodo, f"{base_url}{ruta}", **kwargs)

    return Api()


@pytest.fixture
def crear_usuario(api):
    """Crea usuarios con email único y los borra al terminar la prueba."""
    creados = []

    def _crear(nombre="UAT", password="secreto123"):
        email = f"uat-{uuid.uuid4().hex[:10]}@uat.test"
        r = api("POST", "/api/usuarios", json={"nombre": nombre, "email": email, "password": password})
        assert r.status_code == 201, r.text
        usuario = r.json()
        usuario["password"] = password
        creados.append(usuario["id"])
        return usuario

    yield _crear

    for usuario_id in creados:
        api("DELETE", f"/api/usuarios/{usuario_id}")


@pytest.fixture
def crear_grupo(api):
    """Crea grupos y los borra al terminar (antes que a los usuarios, por el orden de los fixtures)."""
    creados = []

    def _crear(creador_id, nombre="Grupo UAT"):
        r = api("POST", "/api/grupos", json={"nombre": nombre, "creado_por": creador_id})
        assert r.status_code == 201, r.text
        creados.append(r.json()["id"])
        return r.json()

    yield _crear

    for grupo_id in creados:
        api("DELETE", f"/api/grupos/{grupo_id}")
