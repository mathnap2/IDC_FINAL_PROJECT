from flask import Blueprint, jsonify

from app.routes.utils import leer_json
from app.services import usuarios as servicio

bp = Blueprint("usuarios", __name__, url_prefix="/api")


@bp.post("/usuarios")
def crear_usuario():
    datos = leer_json("nombre", "email", "password")
    usuario = servicio.crear(datos["nombre"], datos["email"], datos["password"])
    return jsonify(usuario.to_dict()), 201


@bp.get("/usuarios")
def listar_usuarios():
    return jsonify([u.to_dict() for u in servicio.listar()])


@bp.get("/usuarios/<int:usuario_id>")
def obtener_usuario(usuario_id):
    return jsonify(servicio.obtener(usuario_id).to_dict())


@bp.put("/usuarios/<int:usuario_id>")
def actualizar_usuario(usuario_id):
    datos = leer_json()
    usuario = servicio.actualizar(
        usuario_id,
        nombre=datos.get("nombre"),
        email=datos.get("email"),
        password=datos.get("password"),
    )
    return jsonify(usuario.to_dict())


@bp.delete("/usuarios/<int:usuario_id>")
def eliminar_usuario(usuario_id):
    servicio.eliminar(usuario_id)
    return "", 204


@bp.post("/auth/login")
def login():
    datos = leer_json("email", "password")
    usuario = servicio.autenticar(datos["email"], datos["password"])
    return jsonify(usuario.to_dict())
