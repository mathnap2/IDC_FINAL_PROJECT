"""Lógica de negocio de Usuario (sin Flask, para poder probarla directo)."""

from app.errores import DatosInvalidos, Duplicado, NoAutorizado, NoEncontrado
from app.extensions import db
from app.models import Grupo, Usuario


def _normalizar_email(email):
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise DatosInvalidos("El email no es válido")
    return email


def _validar_email_libre(email, excepto_id=None):
    existente = Usuario.query.filter_by(email=email).first()
    if existente and existente.id != excepto_id:
        raise Duplicado("Ya existe un usuario con ese email")


def crear(nombre, email, password):
    nombre = (nombre or "").strip()
    if not nombre:
        raise DatosInvalidos("El nombre es obligatorio")
    if not password or len(password) < 6:
        raise DatosInvalidos("La contraseña debe tener al menos 6 caracteres")
    email = _normalizar_email(email)
    _validar_email_libre(email)

    usuario = Usuario(nombre=nombre, email=email)
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def obtener(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontrado("El usuario no existe")
    return usuario


def listar():
    return Usuario.query.order_by(Usuario.id).all()


def actualizar(usuario_id, nombre=None, email=None, password=None):
    usuario = obtener(usuario_id)
    if nombre is not None:
        if not nombre.strip():
            raise DatosInvalidos("El nombre es obligatorio")
        usuario.nombre = nombre.strip()
    if email is not None:
        email = _normalizar_email(email)
        _validar_email_libre(email, excepto_id=usuario.id)
        usuario.email = email
    if password is not None:
        if len(password) < 6:
            raise DatosInvalidos("La contraseña debe tener al menos 6 caracteres")
        usuario.set_password(password)
    db.session.commit()
    return usuario


def eliminar(usuario_id):
    usuario = obtener(usuario_id)
    # Para no dejar gastos o pagos huérfanos, primero hay que salir de los grupos.
    if Grupo.query.filter(Grupo.miembros.any(id=usuario.id)).first():
        raise DatosInvalidos("No se puede eliminar un usuario que pertenece a un grupo")
    db.session.delete(usuario)
    db.session.commit()


def autenticar(email, password):
    usuario = Usuario.query.filter_by(email=(email or "").strip().lower()).first()
    if usuario is None or not usuario.check_password(password or ""):
        raise NoAutorizado("Email o contraseña incorrectos")
    return usuario
