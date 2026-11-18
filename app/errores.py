"""Errores de negocio compartidos.

Los servicios lanzan estas excepciones y create_app() las convierte en
{"error": "..."} con el código HTTP correspondiente. Así las rutas no
tienen que armar respuestas de error a mano.
"""


class ErrorAPI(Exception):
    codigo = 400

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


class DatosInvalidos(ErrorAPI):
    """Datos mal formados o una regla de negocio no se cumple."""
    codigo = 400


class NoAutorizado(ErrorAPI):
    codigo = 401


class NoEncontrado(ErrorAPI):
    codigo = 404


class Duplicado(ErrorAPI):
    codigo = 409
