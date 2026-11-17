from flask import Blueprint, jsonify

from app.errores import DatosInvalidos
from app.routes.utils import leer_json
from app.services import grupos as servicio

bp = Blueprint("grupos", __name__, url_prefix="/api/grupos")


@bp.post("")
def crear_grupo():
    datos = leer_json("nombre", "creado_por")
    if not isinstance(datos["creado_por"], int):
        raise DatosInvalidos("creado_por debe ser el id numérico de un usuario")
    grupo = servicio.crear(datos["nombre"], datos["creado_por"], datos.get("descripcion", ""))
    return jsonify(grupo.to_dict()), 201


@bp.get("")
def listar_grupos():
    return jsonify([g.to_dict() for g in servicio.listar()])


@bp.get("/<int:grupo_id>")
def obtener_grupo(grupo_id):
    return jsonify(servicio.obtener(grupo_id).to_dict())


@bp.put("/<int:grupo_id>")
def actualizar_grupo(grupo_id):
    datos = leer_json()
    grupo = servicio.actualizar(grupo_id, nombre=datos.get("nombre"), descripcion=datos.get("descripcion"))
    return jsonify(grupo.to_dict())


@bp.delete("/<int:grupo_id>")
def eliminar_grupo(grupo_id):
    servicio.eliminar(grupo_id)
    return "", 204


@bp.post("/<int:grupo_id>/miembros/<int:usuario_id>")
def agregar_miembro(grupo_id, usuario_id):
    return jsonify(servicio.agregar_miembro(grupo_id, usuario_id).to_dict()), 201


@bp.delete("/<int:grupo_id>/miembros/<int:usuario_id>")
def quitar_miembro(grupo_id, usuario_id):
    return jsonify(servicio.quitar_miembro(grupo_id, usuario_id).to_dict())
