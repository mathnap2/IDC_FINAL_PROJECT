"""Lógica de negocio de Grupo y sus miembros (sin Flask, para poder probarla directo)."""

from decimal import Decimal

from app.errores import DatosInvalidos, Duplicado, NoEncontrado
from app.extensions import db
from app.models import Division, Gasto, Grupo, Pago, Usuario


def _validar_nombre(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        raise DatosInvalidos("El nombre del grupo es obligatorio")
    return nombre


def _obtener_usuario(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontrado("El usuario no existe")
    return usuario


def crear(nombre, creado_por, descripcion=""):
    nombre = _validar_nombre(nombre)
    creador = db.session.get(Usuario, creado_por)
    if creador is None:
        raise DatosInvalidos("El usuario creador no existe")

    # Regla: el creador queda como miembro automáticamente.
    grupo = Grupo(nombre=nombre, descripcion=(descripcion or "").strip(),
                  creado_por=creador.id, miembros=[creador])
    db.session.add(grupo)
    db.session.commit()
    return grupo


def obtener(grupo_id):
    grupo = db.session.get(Grupo, grupo_id)
    if grupo is None:
        raise NoEncontrado("El grupo no existe")
    return grupo


def listar():
    return Grupo.query.order_by(Grupo.id).all()


def actualizar(grupo_id, nombre=None, descripcion=None):
    grupo = obtener(grupo_id)
    if nombre is not None:
        grupo.nombre = _validar_nombre(nombre)
    if descripcion is not None:
        grupo.descripcion = descripcion.strip()
    db.session.commit()
    return grupo


def eliminar(grupo_id):
    # Los gastos, divisiones y pagos del grupo se borran en cascada (ver models/grupo.py).
    db.session.delete(obtener(grupo_id))
    db.session.commit()


def agregar_miembro(grupo_id, usuario_id):
    grupo = obtener(grupo_id)
    usuario = _obtener_usuario(usuario_id)
    if grupo.es_miembro(usuario.id):
        raise Duplicado("El usuario ya es miembro del grupo")
    grupo.miembros.append(usuario)
    db.session.commit()
    return grupo


def quitar_miembro(grupo_id, usuario_id):
    grupo = obtener(grupo_id)
    usuario = _obtener_usuario(usuario_id)
    if not grupo.es_miembro(usuario.id):
        raise DatosInvalidos("El usuario no es miembro del grupo")
    if usuario.id == grupo.creado_por:
        raise DatosInvalidos("No se puede quitar al creador del grupo")
    # Regla: no se puede quitar a alguien que todavía debe o a quien le deben.
    if saldo_miembro(grupo.id, usuario.id) != 0:
        raise DatosInvalidos("No se puede quitar a un miembro con saldo pendiente")
    grupo.miembros.remove(usuario)
    db.session.commit()
    return grupo


def saldo_miembro(grupo_id, usuario_id):
    """Saldo de un miembro dentro de un grupo (positivo = le deben, negativo = debe).

    saldo = lo que pagó en gastos − su parte de los gastos + pagos que hizo − pagos que recibió
    """

    def suma(consulta):
        return Decimal(consulta.scalar() or 0)

    pagado = suma(db.session.query(db.func.sum(Gasto.monto))
                  .filter(Gasto.grupo_id == grupo_id, Gasto.pagado_por == usuario_id))
    su_parte = suma(db.session.query(db.func.sum(Division.monto)).join(Gasto)
                    .filter(Gasto.grupo_id == grupo_id, Division.usuario_id == usuario_id))
    pagos_hechos = suma(db.session.query(db.func.sum(Pago.monto))
                        .filter(Pago.grupo_id == grupo_id, Pago.de_usuario == usuario_id))
    pagos_recibidos = suma(db.session.query(db.func.sum(Pago.monto))
                           .filter(Pago.grupo_id == grupo_id, Pago.a_usuario == usuario_id))
    return (pagado - su_parte + pagos_hechos - pagos_recibidos).quantize(Decimal("0.01"))
