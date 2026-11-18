from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Division, Gasto, Grupo, Pago
from app.services import grupos as servicio


@pytest.fixture
def grupo(usuarios):
    """Grupo creado por Ana con Ana y Beto como miembros."""
    ana, beto, _ = usuarios
    g = servicio.crear("Viaje", ana.id, "Fin de semana")
    servicio.agregar_miembro(g.id, beto.id)
    return g


def registrar_gasto(grupo, pagado_por, monto, partes):
    """Inserta un gasto con sus divisiones directo en la base (la lógica de gastos es de otro componente)."""
    gasto = Gasto(grupo_id=grupo.id, pagado_por=pagado_por, descripcion="Gasto", monto=Decimal(monto))
    gasto.divisiones = [Division(usuario_id=u, monto=Decimal(m)) for u, m in partes.items()]
    db.session.add(gasto)
    db.session.commit()


# ---------- CRUD ----------

def test_crear_grupo_el_creador_queda_como_miembro(client, usuarios):
    ana = usuarios[0]
    cuerpo = {"nombre": "Casa", "descripcion": "Gastos del depa", "creado_por": ana.id}
    r = client.post("/api/grupos", json=cuerpo)
    assert r.status_code == 201
    datos = r.get_json()
    assert datos["creado_por"] == ana.id
    assert [m["id"] for m in datos["miembros"]] == [ana.id]


def test_crear_grupo_sin_nombre(client, usuarios):
    r = client.post("/api/grupos", json={"nombre": "  ", "creado_por": usuarios[0].id})
    assert r.status_code == 400


def test_crear_grupo_con_creador_inexistente(client, usuarios):
    r = client.post("/api/grupos", json={"nombre": "Casa", "creado_por": 999})
    assert r.status_code == 400
    assert r.get_json()["error"] == "El usuario creador no existe"


def test_crear_grupo_con_creador_no_numerico(client, usuarios):
    r = client.post("/api/grupos", json={"nombre": "Casa", "creado_por": "ana"})
    assert r.status_code == 400


def test_listar_y_obtener(client, grupo):
    assert len(client.get("/api/grupos").get_json()) == 1
    r = client.get(f"/api/grupos/{grupo.id}")
    assert r.status_code == 200
    assert r.get_json()["nombre"] == "Viaje"


def test_obtener_grupo_inexistente(client, usuarios):
    r = client.get("/api/grupos/999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "El grupo no existe"


def test_actualizar_grupo(client, grupo):
    cambios = {"nombre": "Viaje a la playa", "descripcion": "Puerto Vallarta"}
    r = client.put(f"/api/grupos/{grupo.id}", json=cambios)
    assert r.status_code == 200
    assert r.get_json()["nombre"] == "Viaje a la playa"
    assert r.get_json()["descripcion"] == "Puerto Vallarta"


def test_actualizar_grupo_con_nombre_vacio(client, grupo):
    assert client.put(f"/api/grupos/{grupo.id}", json={"nombre": ""}).status_code == 400


def test_eliminar_grupo_borra_gastos_y_pagos(client, grupo, usuarios):
    ana, beto, _ = usuarios
    registrar_gasto(grupo, ana.id, "100.00", {ana.id: "50.00", beto.id: "50.00"})
    db.session.add(Pago(grupo_id=grupo.id, de_usuario=beto.id, a_usuario=ana.id, monto=Decimal("50.00")))
    db.session.commit()

    assert client.delete(f"/api/grupos/{grupo.id}").status_code == 204
    assert client.get(f"/api/grupos/{grupo.id}").status_code == 404
    assert Gasto.query.count() == 0 and Pago.query.count() == 0


# ---------- miembros ----------

def test_agregar_miembro(client, grupo, usuarios):
    carla = usuarios[2]
    r = client.post(f"/api/grupos/{grupo.id}/miembros/{carla.id}")
    assert r.status_code == 201
    assert carla.id in [m["id"] for m in r.get_json()["miembros"]]


def test_no_se_puede_agregar_miembro_duplicado(client, grupo, usuarios):
    beto = usuarios[1]
    r = client.post(f"/api/grupos/{grupo.id}/miembros/{beto.id}")
    assert r.status_code == 409
    assert r.get_json()["error"] == "El usuario ya es miembro del grupo"


def test_agregar_usuario_inexistente(client, grupo):
    assert client.post(f"/api/grupos/{grupo.id}/miembros/999").status_code == 404


def test_agregar_miembro_a_grupo_inexistente(client, usuarios):
    assert client.post(f"/api/grupos/999/miembros/{usuarios[0].id}").status_code == 404


def test_quitar_miembro_sin_saldo(client, grupo, usuarios):
    beto = usuarios[1]
    r = client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}")
    assert r.status_code == 200
    assert beto.id not in [m["id"] for m in r.get_json()["miembros"]]


def test_no_se_puede_quitar_miembro_con_saldo(client, grupo, usuarios):
    ana, beto, _ = usuarios
    # Ana pagó 100 y se divide a la mitad: Beto debe 50.
    registrar_gasto(grupo, ana.id, "100.00", {ana.id: "50.00", beto.id: "50.00"})
    r = client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}")
    assert r.status_code == 400
    assert r.get_json()["error"] == "No se puede quitar a un miembro con saldo pendiente"


def test_se_puede_quitar_miembro_despues_de_saldar(client, grupo, usuarios):
    ana, beto, _ = usuarios
    registrar_gasto(grupo, ana.id, "100.00", {ana.id: "50.00", beto.id: "50.00"})
    db.session.add(Pago(grupo_id=grupo.id, de_usuario=beto.id, a_usuario=ana.id, monto=Decimal("50.00")))
    db.session.commit()
    assert client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}").status_code == 200


def test_no_se_puede_quitar_a_quien_no_es_miembro(client, grupo, usuarios):
    carla = usuarios[2]
    assert client.delete(f"/api/grupos/{grupo.id}/miembros/{carla.id}").status_code == 400


def test_no_se_puede_quitar_al_creador(client, grupo, usuarios):
    r = client.delete(f"/api/grupos/{grupo.id}/miembros/{usuarios[0].id}")
    assert r.status_code == 400
    assert r.get_json()["error"] == "No se puede quitar al creador del grupo"


# ---------- saldo de un miembro ----------

def test_saldo_miembro(grupo, usuarios):
    ana, beto, _ = usuarios
    registrar_gasto(grupo, ana.id, "100.00", {ana.id: "50.00", beto.id: "50.00"})
    assert servicio.saldo_miembro(grupo.id, ana.id) == Decimal("50.00")
    assert servicio.saldo_miembro(grupo.id, beto.id) == Decimal("-50.00")

    db.session.add(Pago(grupo_id=grupo.id, de_usuario=beto.id, a_usuario=ana.id, monto=Decimal("20.00")))
    db.session.commit()
    assert servicio.saldo_miembro(grupo.id, ana.id) == Decimal("30.00")
    assert servicio.saldo_miembro(grupo.id, beto.id) == Decimal("-30.00")


def test_saldo_de_miembro_sin_movimientos_es_cero(grupo, usuarios):
    assert servicio.saldo_miembro(grupo.id, usuarios[1].id) == Decimal("0.00")


def test_grupo_existe_en_la_base(grupo):
    assert db.session.get(Grupo, grupo.id).es_miembro(grupo.creado_por)
