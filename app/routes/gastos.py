from flask import Blueprint, jsonify

from app.routes.utils import leer_json
from app.services import gastos as servicio

bp = Blueprint("gastos", __name__, url_prefix="/api")


@bp.post("/grupos/<int:grupo_id>/gastos")
def crear_gasto(grupo_id):
    datos = leer_json("descripcion", "monto", "pagado_por", "participantes")
    gasto = servicio.crear(grupo_id, datos["descripcion"], datos["monto"], datos["pagado_por"],
                           datos["participantes"], datos.get("tipo_division"), datos.get("fecha"))
    return jsonify(gasto.to_dict()), 201


@bp.get("/grupos/<int:grupo_id>/gastos")
def listar_gastos(grupo_id):
    return jsonify([g.to_dict() for g in servicio.listar(grupo_id)])


@bp.get("/gastos/<int:gasto_id>")
def obtener_gasto(gasto_id):
    return jsonify(servicio.obtener(gasto_id).to_dict())


@bp.put("/gastos/<int:gasto_id>")
def actualizar_gasto(gasto_id):
    datos = leer_json()
    gasto = servicio.actualizar(gasto_id, descripcion=datos.get("descripcion"), monto=datos.get("monto"),
                                pagado_por=datos.get("pagado_por"), participantes=datos.get("participantes"),
                                tipo_division=datos.get("tipo_division"), fecha=datos.get("fecha"))
    return jsonify(gasto.to_dict())


@bp.delete("/gastos/<int:gasto_id>")
def eliminar_gasto(gasto_id):
    servicio.eliminar(gasto_id)
    return "", 204
