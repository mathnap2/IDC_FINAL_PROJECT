from flask import request

from app.errores import DatosInvalidos


def leer_json(*requeridos):
    """Devuelve el cuerpo JSON como dict y valida que traiga los campos requeridos."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise DatosInvalidos("El cuerpo de la petición debe ser un objeto JSON")
    faltantes = [c for c in requeridos if datos.get(c) in (None, "")]
    if faltantes:
        raise DatosInvalidos(f"Faltan campos obligatorios: {', '.join(faltantes)}")
    return datos
