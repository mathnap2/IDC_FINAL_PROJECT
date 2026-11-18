from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Division, Gasto, Grupo, Pago


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_ruta_inexistente_devuelve_404_en_json(client):
    r = client.get("/api/no-existe")
    assert r.status_code == 404
    assert "error" in r.get_json()


def test_modelos_y_relaciones(usuarios):
    ana, beto, carla = usuarios
    grupo = Grupo(nombre="Viaje", creado_por=ana.id, miembros=[ana, beto, carla])
    gasto = Gasto(grupo=grupo, pagado_por=ana.id, descripcion="Cena", monto=Decimal("100.00"))
    gasto.divisiones = [
        Division(usuario_id=ana.id, monto=Decimal("33.34")),
        Division(usuario_id=beto.id, monto=Decimal("33.33")),
        Division(usuario_id=carla.id, monto=Decimal("33.33")),
    ]
    pago = Pago(grupo=grupo, de_usuario=beto.id, a_usuario=ana.id, monto=Decimal("33.33"))
    db.session.add_all([grupo, gasto, pago])
    db.session.commit()

    assert grupo.es_miembro(beto.id)
    assert sum(d.monto for d in gasto.divisiones) == Decimal("100.00")
    assert gasto.to_dict()["monto"] == "100.00"
    assert gasto.to_dict()["fecha"] == date.today().isoformat()
    assert pago.to_dict()["a_usuario"] == ana.id
    assert len(grupo.to_dict()["miembros"]) == 3

    # Borrar el grupo borra en cascada sus gastos, divisiones y pagos.
    db.session.delete(grupo)
    db.session.commit()
    assert Gasto.query.count() == 0
    assert Division.query.count() == 0
    assert Pago.query.count() == 0
