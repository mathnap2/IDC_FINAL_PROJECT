"""Lógica de negocio de Pago (sin Flask, para poder probarla directo).

Un pago es una transferencia de un miembro a otro dentro de un grupo para saldar deudas.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from app.errores import DatosInvalidos, NoEncontrado
from app.extensions import db
from app.models import Pago
from app.services import grupos as grupos_servicio

CENTAVO = Decimal("0.01")
MONTO_MAXIMO = Decimal("99999999.99")  # Numeric(10, 2)


def validar_monto(valor):
    """Convierte el monto a Decimal con 2 decimales. Acepta número o texto ("150.50")."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str, Decimal)):
        raise DatosInvalidos("El monto debe ser un número")
    try:
        monto = Decimal(str(valor).strip())
    except InvalidOperation:
        raise DatosInvalidos("El monto debe ser un número")
    if not monto.is_finite():
        raise DatosInvalidos("El monto debe ser un número")
    # Regla: monto > 0.
    if monto <= 0:
        raise DatosInvalidos("El monto debe ser mayor a 0")
    if monto != monto.quantize(CENTAVO):
        raise DatosInvalidos("El monto no puede tener más de 2 decimales")
    if monto > MONTO_MAXIMO:
        raise DatosInvalidos("El monto es demasiado grande")
    return monto.quantize(CENTAVO)


def _validar_fecha(valor):
    if valor in (None, ""):
        return date.today()
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise DatosInvalidos("La fecha debe tener el formato AAAA-MM-DD")


def _validar_participantes(grupo, de_usuario, a_usuario):
    for campo, valor in (("de_usuario", de_usuario), ("a_usuario", a_usuario)):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise DatosInvalidos(f"{campo} debe ser el id numérico de un usuario")
    # Regla: no se puede pagar a uno mismo.
    if de_usuario == a_usuario:
        raise DatosInvalidos("No se puede registrar un pago a uno mismo")
    # Regla: quien paga y quien recibe son miembros del grupo.
    for usuario_id in (de_usuario, a_usuario):
        if not grupo.es_miembro(usuario_id):
            raise DatosInvalidos(f"El usuario {usuario_id} no es miembro del grupo")


def crear(grupo_id, de_usuario, a_usuario, monto, fecha=None):
    grupo = grupos_servicio.obtener(grupo_id)
    _validar_participantes(grupo, de_usuario, a_usuario)
    pago = Pago(grupo_id=grupo.id, de_usuario=de_usuario, a_usuario=a_usuario,
                monto=validar_monto(monto), fecha=_validar_fecha(fecha))
    db.session.add(pago)
    db.session.commit()
    return pago


def listar(grupo_id):
    grupos_servicio.obtener(grupo_id)  # 404 si el grupo no existe
    return (Pago.query.filter_by(grupo_id=grupo_id)
            .order_by(Pago.fecha, Pago.id).all())


def obtener(pago_id):
    pago = db.session.get(Pago, pago_id)
    if pago is None:
        raise NoEncontrado("El pago no existe")
    return pago


def actualizar(pago_id, de_usuario=None, a_usuario=None, monto=None, fecha=None):
    pago = obtener(pago_id)
    nuevo_de = pago.de_usuario if de_usuario is None else de_usuario
    nuevo_a = pago.a_usuario if a_usuario is None else a_usuario
    _validar_participantes(pago.grupo, nuevo_de, nuevo_a)
    pago.de_usuario, pago.a_usuario = nuevo_de, nuevo_a
    if monto is not None:
        pago.monto = validar_monto(monto)
    if fecha is not None:
        pago.fecha = _validar_fecha(fecha)
    db.session.commit()
    return pago


def eliminar(pago_id):
    db.session.delete(obtener(pago_id))
    db.session.commit()
