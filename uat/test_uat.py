"""Escenarios de aceptación desde el punto de vista de quien usa la API."""


def test_la_api_esta_viva(api):
    r = api("GET", "/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_registro_e_inicio_de_sesion(api, crear_usuario):
    usuario = crear_usuario("Ana UAT")

    r = api("POST", "/api/auth/login", json={"email": usuario["email"], "password": usuario["password"]})
    assert r.status_code == 200
    assert r.json()["id"] == usuario["id"]
    assert "password_hash" not in r.json()


def test_login_con_contrasena_incorrecta_es_rechazado(api, crear_usuario):
    usuario = crear_usuario()

    r = api("POST", "/api/auth/login", json={"email": usuario["email"], "password": "incorrecta"})
    assert r.status_code == 401
    assert "error" in r.json()


def test_no_se_puede_registrar_el_mismo_email_dos_veces(api, crear_usuario):
    usuario = crear_usuario()

    datos = {"nombre": "Otro", "email": usuario["email"], "password": "secreto123"}
    r = api("POST", "/api/usuarios", json=datos)
    assert r.status_code == 409


def test_crear_grupo_y_administrar_miembros(api, crear_usuario, crear_grupo):
    ana = crear_usuario("Ana UAT")
    beto = crear_usuario("Beto UAT")

    grupo = crear_grupo(ana["id"], "Viaje UAT")
    assert [m["id"] for m in grupo["miembros"]] == [ana["id"]]  # el creador entra solo

    r = api("POST", f"/api/grupos/{grupo['id']}/miembros/{beto['id']}")
    assert r.status_code == 201
    assert {m["id"] for m in r.json()["miembros"]} == {ana["id"], beto["id"]}

    r = api("POST", f"/api/grupos/{grupo['id']}/miembros/{beto['id']}")
    assert r.status_code == 409  # ya es miembro

    r = api("DELETE", f"/api/grupos/{grupo['id']}/miembros/{ana['id']}")
    assert r.status_code == 400  # no se puede quitar al creador

    r = api("DELETE", f"/api/grupos/{grupo['id']}/miembros/{beto['id']}")
    assert r.status_code == 200
    assert [m["id"] for m in r.json()["miembros"]] == [ana["id"]]


def test_recurso_inexistente_responde_404_en_json(api):
    r = api("GET", "/api/grupos/999999999")
    assert r.status_code == 404
    assert "error" in r.json()
