"""Pruebas de pagos, saldos y deudas simplificadas: una por regla de negocio (#18)."""

import random
from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Division, Gasto, Pago
from app.services import grupos as grupos_servicio
from app.services import pagos as servicio
from app.services import saldos as saldos_servicio
from app.services import usuarios as usuarios_servicio


@pytest.fixture
def grupo(usuarios):
    """Grupo de Ana con Ana, Beto y Carla como miembros."""
    ana, beto, carla = usuarios
    g = grupos_servicio.crear("Viaje", ana.id)
    grupos_servicio.agregar_miembro(g.id, beto.id)
    grupos_servicio.agregar_miembro(g.id, carla.id)
    return g


def registrar_gasto(grupo, pagado_por, partes):
    """Inserta un gasto con sus divisiones directo en la base (la lógica de gastos es de otro componente).

    El monto del gasto es la suma de las partes, como lo garantiza dividir_gasto.
    """
    partes = {u: Decimal(m) for u, m in partes.items()}
    gasto = Gasto(grupo_id=grupo.id, pagado_por=pagado_por, descripcion="Gasto", monto=sum(partes.values()))
    gasto.divisiones = [Division(usuario_id=u, monto=m) for u, m in partes.items()]
    db.session.add(gasto)
    db.session.commit()


def saldos_de(client, grupo):
    r = client.get(f"/api/grupos/{grupo.id}/saldos")
    assert r.status_code == 200
    return {s["usuario_id"]: Decimal(s["saldo"]) for s in r.get_json()}


def deudas_de(client, grupo):
    r = client.get(f"/api/grupos/{grupo.id}/deudas-simplificadas")
    assert r.status_code == 200
    return [(d["de_usuario"], d["a_usuario"], Decimal(d["monto"])) for d in r.get_json()]


def pagar(client, grupo, de, a, monto, **extra):
    cuerpo = {"de_usuario": de, "a_usuario": a, "monto": monto, **extra}
    return client.post(f"/api/grupos/{grupo.id}/pagos", json=cuerpo)


# ---------- CRUD de pagos (#16) ----------

def test_registrar_pago(client, grupo, usuarios):
    ana, beto, _ = usuarios
    r = pagar(client, grupo, ana.id, beto.id, "150.50", fecha="2026-11-01")
    assert r.status_code == 201
    datos = r.get_json()
    assert datos == {"id": datos["id"], "grupo_id": grupo.id, "de_usuario": ana.id,
                     "a_usuario": beto.id, "monto": "150.50", "fecha": "2026-11-01"}


def test_pago_sin_fecha_usa_la_de_hoy(client, grupo, usuarios):
    ana, beto, _ = usuarios
    r = pagar(client, grupo, ana.id, beto.id, 20)
    assert r.get_json()["fecha"] == date.today().isoformat()
    assert r.get_json()["monto"] == "20.00"


def test_listar_obtener_y_eliminar_pagos(client, grupo, usuarios):
    ana, beto, carla = usuarios
    pago_id = pagar(client, grupo, ana.id, beto.id, 10, fecha="2026-11-02").get_json()["id"]
    pagar(client, grupo, carla.id, ana.id, 5, fecha="2026-11-01")

    lista = client.get(f"/api/grupos/{grupo.id}/pagos").get_json()
    assert [p["fecha"] for p in lista] == ["2026-11-01", "2026-11-02"]  # por fecha

    assert client.get(f"/api/pagos/{pago_id}").get_json()["monto"] == "10.00"
    assert client.delete(f"/api/pagos/{pago_id}").status_code == 204
    assert client.get(f"/api/pagos/{pago_id}").status_code == 404
    assert len(client.get(f"/api/grupos/{grupo.id}/pagos").get_json()) == 1


def test_actualizar_pago(client, grupo, usuarios):
    ana, beto, carla = usuarios
    pago_id = pagar(client, grupo, ana.id, beto.id, 10).get_json()["id"]

    cambios = {"monto": "12.5", "a_usuario": carla.id, "fecha": "2026-10-31"}
    r = client.put(f"/api/pagos/{pago_id}", json=cambios)
    assert r.status_code == 200
    assert r.get_json()["monto"] == "12.50"
    assert r.get_json()["a_usuario"] == carla.id
    assert r.get_json()["fecha"] == "2026-10-31"


def test_actualizar_pago_aplica_las_mismas_reglas(client, grupo, usuarios):
    ana, beto, _ = usuarios
    pago_id = pagar(client, grupo, ana.id, beto.id, 10).get_json()["id"]
    assert client.put(f"/api/pagos/{pago_id}", json={"monto": 0}).status_code == 400
    assert client.put(f"/api/pagos/{pago_id}", json={"a_usuario": ana.id}).status_code == 400
    assert client.get(f"/api/pagos/{pago_id}").get_json()["monto"] == "10.00"  # no cambió


def test_pago_en_grupo_inexistente(client, usuarios):
    ana, beto, _ = usuarios
    r = client.post("/api/grupos/999/pagos", json={"de_usuario": ana.id, "a_usuario": beto.id, "monto": 10})
    assert r.status_code == 404
    assert client.get("/api/grupos/999/pagos").status_code == 404


def test_pago_inexistente(client, usuarios):
    assert client.get("/api/pagos/999").status_code == 404
    assert client.put("/api/pagos/999", json={"monto": 5}).status_code == 404
    assert client.delete("/api/pagos/999").status_code == 404


def test_pago_sin_campos_obligatorios(client, grupo, usuarios):
    r = client.post(f"/api/grupos/{grupo.id}/pagos", json={"de_usuario": usuarios[0].id})
    assert r.status_code == 400
    assert "a_usuario" in r.get_json()["error"] and "monto" in r.get_json()["error"]


def test_pago_con_ids_no_numericos(client, grupo, usuarios):
    r = pagar(client, grupo, "ana", usuarios[1].id, 10)
    assert r.status_code == 400
    assert r.get_json()["error"] == "de_usuario debe ser el id numérico de un usuario"


def test_pago_con_fecha_invalida(client, grupo, usuarios):
    r = pagar(client, grupo, usuarios[0].id, usuarios[1].id, 10, fecha="31/10/2026")
    assert r.status_code == 400


# ---------- Reglas de negocio de pagos (#15) ----------

@pytest.mark.parametrize("monto", [0, -5, "0.00", "-1"])
def test_regla_monto_mayor_a_cero(client, grupo, usuarios, monto):
    r = pagar(client, grupo, usuarios[0].id, usuarios[1].id, monto)
    assert r.status_code == 400
    assert r.get_json()["error"] == "El monto debe ser mayor a 0"


@pytest.mark.parametrize("monto", ["abc", True, [10], "NaN", "Infinity", "10.001", "100000000"])
def test_monto_debe_ser_un_numero_valido(client, grupo, usuarios, monto):
    assert pagar(client, grupo, usuarios[0].id, usuarios[1].id, monto).status_code == 400


def test_regla_no_se_puede_pagar_a_uno_mismo(client, grupo, usuarios):
    ana = usuarios[0]
    r = pagar(client, grupo, ana.id, ana.id, 10)
    assert r.status_code == 400
    assert r.get_json()["error"] == "No se puede registrar un pago a uno mismo"


def test_regla_quien_paga_y_quien_recibe_son_miembros(client, grupo, usuarios):
    ana = usuarios[0]
    # Dani se registra pero no está en el grupo.
    dani = client.post("/api/usuarios", json={"nombre": "Dani", "email": "dani@test.com",
                                              "password": "secreto123"}).get_json()
    assert pagar(client, grupo, ana.id, dani["id"], 10).status_code == 400
    assert pagar(client, grupo, dani["id"], ana.id, 10).status_code == 400
    assert Pago.query.count() == 0


# ---------- Saldos (#17) ----------

def test_saldos_sin_movimientos_son_cero(client, grupo, usuarios):
    r = client.get(f"/api/grupos/{grupo.id}/saldos")
    assert r.get_json() == [{"usuario_id": u.id, "nombre": u.nombre, "saldo": "0.00"} for u in usuarios]


def test_saldos_con_gastos_y_pagos(client, grupo, usuarios):
    ana, beto, carla = usuarios
    registrar_gasto(grupo, ana.id, {ana.id: "100", beto.id: "100", carla.id: "100"})  # Ana pagó 300
    pagar(client, grupo, beto.id, ana.id, 60)

    # Ana: +300 − 100 − 60 recibidos = 140; Beto: −100 + 60 = −40; Carla: −100
    esperado = {ana.id: Decimal("140"), beto.id: Decimal("-40"), carla.id: Decimal("-100")}
    assert saldos_de(client, grupo) == esperado


def test_saldos_coinciden_con_saldo_miembro(client, grupo, usuarios):
    ana, beto, carla = usuarios
    registrar_gasto(grupo, beto.id, {ana.id: "33.34", beto.id: "33.33", carla.id: "33.33"})
    pagar(client, grupo, carla.id, beto.id, "10.50")
    for usuario_id, saldo in saldos_de(client, grupo).items():
        assert saldo == grupos_servicio.saldo_miembro(grupo.id, usuario_id)


def test_regla_la_suma_de_saldos_del_grupo_es_cero(client, grupo, usuarios):
    ana, beto, carla = usuarios
    registrar_gasto(grupo, ana.id, {ana.id: "33.34", beto.id: "33.33", carla.id: "33.33"})
    registrar_gasto(grupo, carla.id, {beto.id: "45.50", carla.id: "4.50"})
    pagar(client, grupo, beto.id, ana.id, "12.75")
    pagar(client, grupo, ana.id, carla.id, 3)

    assert sum(saldos_de(client, grupo).values()) == 0


def test_saldos_ignoran_otros_grupos(client, grupo, usuarios):
    ana, beto, _ = usuarios
    otro = grupos_servicio.crear("Casa", ana.id)
    grupos_servicio.agregar_miembro(otro.id, beto.id)
    registrar_gasto(otro, ana.id, {beto.id: "50"})
    pagar(client, otro, beto.id, ana.id, 20)

    assert set(saldos_de(client, grupo).values()) == {Decimal(0)}


def test_saldos_de_grupo_inexistente(client, usuarios):
    assert client.get("/api/grupos/999/saldos").status_code == 404
    assert client.get("/api/grupos/999/deudas-simplificadas").status_code == 404


# ---------- Deudas simplificadas (#17) ----------

def test_regla_deudas_en_cadena_se_simplifican(client, grupo, usuarios):
    """A→B 100 y B→C 100 se simplifica a A→C 100."""
    ana, beto, carla = usuarios
    registrar_gasto(grupo, beto.id, {ana.id: "100"})    # Ana le debe 100 a Beto
    registrar_gasto(grupo, carla.id, {beto.id: "100"})  # Beto le debe 100 a Carla

    assert deudas_de(client, grupo) == [(ana.id, carla.id, Decimal("100"))]


def test_deudas_sin_movimientos_es_lista_vacia(client, grupo):
    assert deudas_de(client, grupo) == []


def test_pagar_lo_indicado_deja_a_todos_en_cero(client, grupo, usuarios):
    ana, beto, carla = usuarios
    registrar_gasto(grupo, ana.id, {ana.id: "100", beto.id: "100", carla.id: "100"})
    registrar_gasto(grupo, beto.id, {ana.id: "20", carla.id: "40"})

    for de, a, monto in deudas_de(client, grupo):
        assert pagar(client, grupo, de, a, str(monto)).status_code == 201

    assert set(saldos_de(client, grupo).values()) == {Decimal(0)}
    assert deudas_de(client, grupo) == []


def test_un_pago_parcial_reduce_la_deuda(client, grupo, usuarios):
    ana, beto, _ = usuarios
    registrar_gasto(grupo, ana.id, {beto.id: "80"})
    pagar(client, grupo, beto.id, ana.id, 30)
    assert deudas_de(client, grupo) == [(beto.id, ana.id, Decimal("50"))]


def test_quien_paga_de_mas_queda_como_acreedor(client, grupo, usuarios):
    ana, beto, _ = usuarios
    registrar_gasto(grupo, ana.id, {beto.id: "50"})
    pagar(client, grupo, beto.id, ana.id, 70)
    assert deudas_de(client, grupo) == [(ana.id, beto.id, Decimal("20"))]


def test_simplificacion_usa_a_lo_mas_n_menos_1_transferencias_y_salda_todo(app, usuarios):
    """Con datos aleatorios: como máximo n − 1 transferencias y, al aplicarlas, todos quedan en 0."""
    rng = random.Random(2026)
    miembros = list(usuarios)
    for i in range(7):  # 3 + 7 = 10 miembros
        miembros.append(usuarios_servicio.crear(f"Extra{i}", f"extra{i}@test.com", "secreto123"))
    grupo = grupos_servicio.crear("Grande", miembros[0].id)
    for m in miembros[1:]:
        grupos_servicio.agregar_miembro(grupo.id, m.id)

    for _ in range(25):
        pagador = rng.choice(miembros)
        participantes = rng.sample(miembros, rng.randint(1, 10))
        partes = {m.id: Decimal(rng.randint(1, 50000)) / 100 for m in participantes}
        registrar_gasto(grupo, pagador.id, partes)
    for _ in range(10):
        de, a = rng.sample(miembros, 2)
        servicio.crear(grupo.id, de.id, a.id, str(Decimal(rng.randint(1, 30000)) / 100))

    saldos = {s["usuario_id"]: s["saldo"] for s in saldos_servicio.calcular_saldos(grupo.id)}
    assert sum(saldos.values()) == 0
    con_saldo = sum(1 for s in saldos.values() if s != 0)

    transferencias = saldos_servicio.simplificar_deudas(grupo.id)
    assert len(transferencias) <= con_saldo - 1
    assert all(t["monto"] > 0 and t["de_usuario"] != t["a_usuario"] for t in transferencias)

    for t in transferencias:
        saldos[t["de_usuario"]] += t["monto"]
        saldos[t["a_usuario"]] -= t["monto"]
    assert set(saldos.values()) == {Decimal(0)}


# ---------- Integración con grupos ----------

def test_pagos_cuentan_para_poder_quitar_un_miembro(client, grupo, usuarios):
    ana, beto, _ = usuarios
    pagar(client, grupo, beto.id, ana.id, 25)  # Beto adelantó un pago: le deben 25
    assert client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}").status_code == 400

    pagar(client, grupo, ana.id, beto.id, 25)
    assert client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}").status_code == 200


def test_eliminar_grupo_borra_sus_pagos(client, grupo, usuarios):
    pagar(client, grupo, usuarios[0].id, usuarios[1].id, 10)
    assert client.delete(f"/api/grupos/{grupo.id}").status_code == 204
    assert Pago.query.count() == 0
