"""Pruebas de gastos y su división: al menos una por regla de negocio (#14)."""

from datetime import date
from decimal import Decimal

import pytest

from app.errores import DatosInvalidos
from app.extensions import db
from app.models import Usuario
from app.services import gastos as servicio
from app.services import grupos as grupos_servicio


@pytest.fixture
def grupo(usuarios):
    """Grupo de Ana con Ana, Beto y Carla como miembros."""
    ana, beto, carla = usuarios
    g = grupos_servicio.crear("Viaje", ana.id)
    grupos_servicio.agregar_miembro(g.id, beto.id)
    grupos_servicio.agregar_miembro(g.id, carla.id)
    return g


@pytest.fixture
def externo(app):
    """Usuario que existe pero no es miembro del grupo."""
    u = Usuario(nombre="Diego", email="diego@test.com")
    u.set_password("secreto123")
    db.session.add(u)
    db.session.commit()
    return u


def todos(usuarios, valores=None):
    valores = valores or [None] * len(usuarios)
    return [{"usuario_id": u.id, "valor": v} for u, v in zip(usuarios, valores)]


def registrar(client, grupo, pagado_por, participantes, monto="100", **extra):
    cuerpo = {"descripcion": "Cena", "monto": monto, "pagado_por": pagado_por,
              "participantes": participantes, **extra}
    return client.post(f"/api/grupos/{grupo.id}/gastos", json=cuerpo)


def partes(respuesta):
    return {d["usuario_id"]: d["monto"] for d in respuesta.get_json()["divisiones"]}


def error(respuesta):
    assert respuesta.status_code == 400
    return respuesta.get_json()["error"]


# ---------- crear y dividir (#13) ----------

def test_crear_gasto_iguales_reparte_centavos_a_los_primeros(client, grupo, usuarios):
    ana, beto, carla = usuarios
    r = registrar(client, grupo, ana.id, todos(usuarios), fecha="2026-11-18")
    assert r.status_code == 201
    datos = r.get_json()
    assert datos["monto"] == "100.00"
    assert datos["tipo_division"] == "iguales"  # valor por defecto
    assert datos["fecha"] == "2026-11-18"
    assert datos["pagado_por"] == ana.id and datos["grupo_id"] == grupo.id
    assert partes(r) == {ana.id: "33.34", beto.id: "33.33", carla.id: "33.33"}


def test_gasto_sin_fecha_usa_la_de_hoy_y_acepta_monto_numerico(client, grupo, usuarios):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios[:2]), monto=50)
    assert r.status_code == 201
    assert r.get_json()["fecha"] == date.today().isoformat()
    assert set(partes(r).values()) == {"25.00"}


def test_crear_gasto_porcentaje(client, grupo, usuarios):
    ana, beto, _ = usuarios
    r = registrar(client, grupo, ana.id, todos(usuarios[:2], ["60", "40"]), monto="300.00",
                  tipo_division="porcentaje")
    assert r.status_code == 201
    assert partes(r) == {ana.id: "180.00", beto.id: "120.00"}


def test_porcentaje_con_redondeo_suma_exacto_el_monto(client, grupo, usuarios):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios, ["33.33", "33.33", "33.34"]),
                  monto="100", tipo_division="porcentaje")
    assert r.status_code == 201
    assert sum(Decimal(m) for m in partes(r).values()) == Decimal("100.00")


def test_porcentajes_que_no_suman_100(client, grupo, usuarios):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios[:2], ["60", "30"]),
                  tipo_division="porcentaje")
    assert error(r) == "Los porcentajes deben sumar 100"


@pytest.mark.parametrize("valor", ["0", "-10", "abc", None, True, "NaN"])
def test_porcentaje_invalido(client, grupo, usuarios, valor):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios[:2], [valor, "100"]),
                  tipo_division="porcentaje")
    assert "porcentaje" in error(r)


def test_crear_gasto_montos(client, grupo, usuarios):
    ana, beto, carla = usuarios
    r = registrar(client, grupo, ana.id, todos(usuarios, ["50", "30.50", 19.5]), tipo_division="montos")
    assert r.status_code == 201
    assert partes(r) == {ana.id: "50.00", beto.id: "30.50", carla.id: "19.50"}


def test_montos_que_no_suman_el_total(client, grupo, usuarios):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios[:2], ["50", "40"]), tipo_division="montos")
    assert error(r) == "Los montos deben sumar el total del gasto"


@pytest.mark.parametrize("valor", ["0", "-5", "1.001", "x"])
def test_monto_de_participante_invalido(client, grupo, usuarios, valor):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios[:2], [valor, "100"]), tipo_division="montos")
    assert "monto" in error(r)


@pytest.mark.parametrize("monto", [0, "-10", "abc", "10.555"])
def test_monto_del_gasto_invalido(client, grupo, usuarios, monto):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios), monto=monto)
    assert "monto" in error(r)


@pytest.mark.parametrize("descripcion", ["   ", 123])
def test_descripcion_obligatoria(client, grupo, usuarios, descripcion):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios), descripcion=descripcion)
    assert error(r) == "La descripción del gasto es obligatoria"


def test_faltan_campos_obligatorios(client, grupo):
    r = client.post(f"/api/grupos/{grupo.id}/gastos", json={"descripcion": "Cena"})
    assert "Faltan campos obligatorios" in error(r)


def test_tipo_division_invalido(client, grupo, usuarios):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios), tipo_division="mitad")
    assert "tipo_division" in error(r)


def test_quien_pago_no_es_miembro(client, grupo, usuarios, externo):
    r = registrar(client, grupo, externo.id, todos(usuarios))
    assert "no es miembro" in error(r)


def test_participante_no_es_miembro(client, grupo, usuarios, externo):
    r = registrar(client, grupo, usuarios[0].id, todos([usuarios[0], externo]))
    assert error(r) == f"El participante {externo.id} no es miembro del grupo"


def test_participantes_repetidos(client, grupo, usuarios):
    ana = usuarios[0]
    r = registrar(client, grupo, ana.id, todos([ana, ana]))
    assert "repetido" in error(r)


@pytest.mark.parametrize("participantes", [[], "todos", [5], [{"valor": "10"}]])
def test_participantes_vacios_o_mal_formados(client, grupo, usuarios, participantes):
    r = registrar(client, grupo, usuarios[0].id, participantes)
    assert r.status_code == 400


@pytest.mark.parametrize("campo", ["pagado_por", "usuario_id"])
def test_ids_booleanos_se_rechazan(client, grupo, usuarios, campo):
    if campo == "pagado_por":
        r = registrar(client, grupo, True, todos(usuarios))
    else:
        r = registrar(client, grupo, usuarios[0].id, [{"usuario_id": True}])
    assert f"{campo} debe ser el id" in error(r)


def test_fecha_invalida(client, grupo, usuarios):
    r = registrar(client, grupo, usuarios[0].id, todos(usuarios), fecha="18/11/2026")
    assert "AAAA-MM-DD" in error(r)


def test_gasto_en_grupo_inexistente(client, usuarios):
    r = client.post("/api/grupos/999/gastos", json={"descripcion": "Cena", "monto": 10, "pagado_por": 1,
                                                    "participantes": [{"usuario_id": 1}]})
    assert r.status_code == 404


def test_dividir_gasto_siempre_suma_el_monto(app):
    """Prueba directa del servicio con montos que no se dividen exacto."""
    for monto, n in (("100", 3), ("0.05", 3), ("10", 7), ("99999.99", 6)):
        resultado = servicio.dividir_gasto(monto, "iguales", [(i, None) for i in range(n)])
        assert sum(p for _, p in resultado) == Decimal(monto)
        assert max(p for _, p in resultado) - min(p for _, p in resultado) <= Decimal("0.01")

    resultado = servicio.dividir_gasto("10", "porcentaje", [(1, "33.3333"), (2, "33.3333"), (3, "33.3334")])
    assert sum(p for _, p in resultado) == Decimal("10.00")

    with pytest.raises(DatosInvalidos):
        servicio.dividir_gasto("10", "otro", [(1, None)])


# ---------- listar, obtener, actualizar y eliminar (#13) ----------

def test_listar_ordenado_por_fecha_e_id(client, grupo, usuarios):
    ana = usuarios[0]
    segundo = registrar(client, grupo, ana.id, todos(usuarios), fecha="2026-11-02").get_json()["id"]
    primero = registrar(client, grupo, ana.id, todos(usuarios), fecha="2026-11-01").get_json()["id"]
    tercero = registrar(client, grupo, ana.id, todos(usuarios), fecha="2026-11-02").get_json()["id"]

    r = client.get(f"/api/grupos/{grupo.id}/gastos")
    assert r.status_code == 200
    assert [g["id"] for g in r.get_json()] == [primero, segundo, tercero]


def test_listar_en_grupo_inexistente(client):
    assert client.get("/api/grupos/999/gastos").status_code == 404


def test_obtener_gasto(client, grupo, usuarios):
    creado = registrar(client, grupo, usuarios[0].id, todos(usuarios)).get_json()
    r = client.get(f"/api/gastos/{creado['id']}")
    assert r.status_code == 200
    assert r.get_json() == creado
    assert client.get("/api/gastos/999").status_code == 404


def test_actualizar_vuelve_a_dividir(client, grupo, usuarios):
    ana, beto, carla = usuarios
    gasto_id = registrar(client, grupo, ana.id, todos(usuarios)).get_json()["id"]

    r = client.put(f"/api/gastos/{gasto_id}", json={
        "descripcion": "Cena y postre", "monto": "200", "pagado_por": beto.id, "fecha": "2026-11-10",
        "tipo_division": "montos", "participantes": todos([beto, carla], ["150", "50"])})
    assert r.status_code == 200
    datos = r.get_json()
    campos = ("descripcion", "monto", "pagado_por", "fecha", "tipo_division")
    assert [datos[c] for c in campos] == ["Cena y postre", "200.00", beto.id, "2026-11-10", "montos"]
    assert partes(r) == {beto.id: "150.00", carla.id: "50.00"}  # Ana ya no participa
    assert client.get(f"/api/gastos/{gasto_id}").get_json() == datos


def test_actualizar_solo_el_monto_reusa_participantes_iguales(client, grupo, usuarios):
    ana, beto, carla = usuarios
    gasto_id = registrar(client, grupo, ana.id, todos(usuarios)).get_json()["id"]
    r = client.put(f"/api/gastos/{gasto_id}", json={"monto": "10"})
    assert r.status_code == 200
    assert partes(r) == {ana.id: "3.34", beto.id: "3.33", carla.id: "3.33"}


def test_actualizar_sin_redividir_conserva_divisiones(client, grupo, usuarios):
    ana = usuarios[0]
    creado = registrar(client, grupo, ana.id, todos(usuarios, ["50", "25", "25"]),
                       tipo_division="porcentaje").get_json()
    r = client.put(f"/api/gastos/{creado['id']}", json={"descripcion": "Comida"})
    assert r.status_code == 200
    assert r.get_json()["descripcion"] == "Comida"
    assert r.get_json()["divisiones"] == creado["divisiones"]


def test_actualizar_a_porcentaje_sin_participantes(client, grupo, usuarios):
    gasto_id = registrar(client, grupo, usuarios[0].id, todos(usuarios)).get_json()["id"]
    r = client.put(f"/api/gastos/{gasto_id}", json={"tipo_division": "porcentaje"})
    assert "enviar los participantes" in error(r)


def test_actualizar_con_datos_invalidos_no_cambia_nada(client, grupo, usuarios, externo):
    creado = registrar(client, grupo, usuarios[0].id, todos(usuarios)).get_json()
    assert client.put(f"/api/gastos/{creado['id']}", json={"monto": "-1"}).status_code == 400
    assert client.put(f"/api/gastos/{creado['id']}", json={"pagado_por": externo.id}).status_code == 400
    assert client.get(f"/api/gastos/{creado['id']}").get_json() == creado
    assert client.put("/api/gastos/999", json={"monto": "1"}).status_code == 404


def test_eliminar_gasto(client, grupo, usuarios):
    gasto_id = registrar(client, grupo, usuarios[0].id, todos(usuarios)).get_json()["id"]
    r = client.delete(f"/api/gastos/{gasto_id}")
    assert r.status_code == 204 and r.data == b""
    assert client.get(f"/api/gastos/{gasto_id}").status_code == 404
    assert client.delete(f"/api/gastos/{gasto_id}").status_code == 404


# ---------- integración con saldos ----------

def test_saldos_reflejan_el_gasto_y_suman_cero(client, grupo, usuarios):
    ana, beto, carla = usuarios
    registrar(client, grupo, ana.id, todos(usuarios))  # Ana paga 100 entre 3

    r = client.get(f"/api/grupos/{grupo.id}/saldos")
    saldos = {s["usuario_id"]: Decimal(s["saldo"]) for s in r.get_json()}
    assert saldos == {ana.id: Decimal("66.66"), beto.id: Decimal("-33.33"), carla.id: Decimal("-33.33")}
    assert sum(saldos.values()) == 0

    deudas = client.get(f"/api/grupos/{grupo.id}/deudas-simplificadas").get_json()
    assert sorted((d["de_usuario"], d["a_usuario"], d["monto"]) for d in deudas) == \
        sorted([(beto.id, ana.id, "33.33"), (carla.id, ana.id, "33.33")])


def test_no_se_puede_quitar_a_un_miembro_con_deuda(client, grupo, usuarios):
    ana, beto, _ = usuarios
    registrar(client, grupo, ana.id, todos(usuarios))
    r = client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}")
    assert error(r) == "No se puede quitar a un miembro con saldo pendiente"


def test_eliminar_gasto_libera_los_saldos(client, grupo, usuarios):
    ana, beto, _ = usuarios
    gasto_id = registrar(client, grupo, ana.id, todos(usuarios)).get_json()["id"]
    client.delete(f"/api/gastos/{gasto_id}")
    saldos = client.get(f"/api/grupos/{grupo.id}/saldos").get_json()
    assert all(s["saldo"] == "0.00" for s in saldos)
    assert client.delete(f"/api/grupos/{grupo.id}/miembros/{beto.id}").status_code == 200
