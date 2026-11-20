from flask import Blueprint, jsonify

from app.routes.utils import leer_json
from app.services import pagos as servicio
from app.services import saldos as saldos_servicio

bp = Blueprint("pagos", __name__, url_prefix="/api")


@bp.post("/grupos/<int:grupo_id>/pagos")
def crear_pago(grupo_id):
    datos = leer_json("de_usuario", "a_usuario", "monto")
    pago = servicio.crear(grupo_id, datos["de_usuario"], datos["a_usuario"],
                          datos["monto"], datos.get("fecha"))
    return jsonify(pago.to_dict()), 201


@bp.get("/grupos/<int:grupo_id>/pagos")
def listar_pagos(grupo_id):
    return jsonify([p.to_dict() for p in servicio.listar(grupo_id)])


@bp.get("/pagos/<int:pago_id>")
def obtener_pago(pago_id):
    return jsonify(servicio.obtener(pago_id).to_dict())


@bp.put("/pagos/<int:pago_id>")
def actualizar_pago(pago_id):
    datos = leer_json()
    pago = servicio.actualizar(pago_id, de_usuario=datos.get("de_usuario"), a_usuario=datos.get("a_usuario"),
                               monto=datos.get("monto"), fecha=datos.get("fecha"))
    return jsonify(pago.to_dict())


@bp.delete("/pagos/<int:pago_id>")
def eliminar_pago(pago_id):
    servicio.eliminar(pago_id)
    return "", 204


@bp.get("/grupos/<int:grupo_id>/saldos")
def saldos(grupo_id):
    return jsonify([{**s, "saldo": str(s["saldo"])} for s in saldos_servicio.calcular_saldos(grupo_id)])


@bp.get("/grupos/<int:grupo_id>/deudas-simplificadas")
def deudas_simplificadas(grupo_id):
    return jsonify([{**d, "monto": str(d["monto"])} for d in saldos_servicio.simplificar_deudas(grupo_id)])
