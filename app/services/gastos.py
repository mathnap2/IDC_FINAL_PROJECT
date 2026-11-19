"""Lógica de negocio de Gasto y su división (sin Flask, para poder probarla directo).

Un gasto lo paga un miembro del grupo y se reparte entre varios participantes. Cada parte se
guarda como una Division y la suma de las divisiones siempre es exactamente el monto del gasto;
así saldos.py puede calcular los saldos sin saber cómo se dividió cada gasto.
"""

from decimal import ROUND_DOWN, Decimal, InvalidOperation

from app.errores import DatosInvalidos, NoEncontrado
from app.extensions import db
from app.models import TIPOS_DIVISION, Division, Gasto
from app.services import grupos as grupos_servicio
from app.services.pagos import _validar_fecha, validar_monto

CENTAVO = Decimal("0.01")
CIEN = Decimal("100")


# ---------- validaciones ----------

def _validar_descripcion(descripcion):
    descripcion = descripcion.strip() if isinstance(descripcion, str) else ""
    if not descripcion:
        raise DatosInvalidos("La descripción del gasto es obligatoria")
    return descripcion


def _validar_tipo(tipo_division):
    if tipo_division not in TIPOS_DIVISION:
        raise DatosInvalidos(f"tipo_division debe ser uno de: {', '.join(TIPOS_DIVISION)}")
    return tipo_division


def _validar_id(valor, campo):
    # bool es subclase de int en Python, por eso se descarta aparte (True no es el usuario 1).
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise DatosInvalidos(f"{campo} debe ser el id numérico de un usuario")
    return valor


def _validar_participantes(grupo, pagado_por, participantes):
    """Revisa la lista de participantes y regresa [(usuario_id, valor)] en el mismo orden."""
    _validar_id(pagado_por, "pagado_por")
    if not grupo.es_miembro(pagado_por):
        raise DatosInvalidos(f"Quien pagó (usuario {pagado_por}) no es miembro del grupo")

    if not isinstance(participantes, list) or not participantes:
        raise DatosInvalidos("El gasto debe tener al menos un participante")

    resultado, vistos = [], set()
    for p in participantes:
        if not isinstance(p, dict):
            raise DatosInvalidos("Cada participante debe ser un objeto con usuario_id")
        usuario_id = _validar_id(p.get("usuario_id"), "usuario_id")
        if usuario_id in vistos:
            raise DatosInvalidos(f"El participante {usuario_id} está repetido")
        if not grupo.es_miembro(usuario_id):
            raise DatosInvalidos(f"El participante {usuario_id} no es miembro del grupo")
        vistos.add(usuario_id)
        resultado.append((usuario_id, p.get("valor")))
    return resultado


def _validar_porcentaje(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str, Decimal)):
        raise DatosInvalidos("Cada porcentaje debe ser un número")
    try:
        porcentaje = Decimal(str(valor).strip())
    except InvalidOperation:
        raise DatosInvalidos("Cada porcentaje debe ser un número")
    if not porcentaje.is_finite():
        raise DatosInvalidos("Cada porcentaje debe ser un número")
    if porcentaje <= 0:
        raise DatosInvalidos("Cada porcentaje debe ser mayor a 0")
    return porcentaje


# ---------- división ----------

def _repartir_sobrante(monto, partes):
    """Reparte los centavos que faltan (por truncar) uno por uno a los primeros participantes."""
    sobrante = int((monto - sum(partes)) / CENTAVO)
    for i in range(sobrante):
        partes[i] += CENTAVO
    return partes


def dividir_gasto(monto, tipo_division, participantes):
    """Divide `monto` entre `participantes` ([(usuario_id, valor)]) según `tipo_division`.

    Regresa [(usuario_id, parte)] y la suma de las partes es exactamente `monto`.
      - iguales:    monto / n truncado a centavos; los centavos sobrantes van a los primeros.
      - porcentaje: monto × valor / 100 truncado; los porcentajes deben sumar 100.
      - montos:     cada valor es la parte; los montos deben sumar el total.
    """
    monto = validar_monto(monto)
    _validar_tipo(tipo_division)
    ids = [u for u, _ in participantes]

    if tipo_division == "iguales":
        base = (monto / len(ids)).quantize(CENTAVO, rounding=ROUND_DOWN)
        partes = _repartir_sobrante(monto, [base] * len(ids))

    elif tipo_division == "porcentaje":
        porcentajes = [_validar_porcentaje(v) for _, v in participantes]
        if sum(porcentajes) != CIEN:
            raise DatosInvalidos("Los porcentajes deben sumar 100")
        partes = [(monto * p / CIEN).quantize(CENTAVO, rounding=ROUND_DOWN) for p in porcentajes]
        partes = _repartir_sobrante(monto, partes)

    else:  # montos
        partes = [validar_monto(v) for _, v in participantes]
        if sum(partes) != monto:
            raise DatosInvalidos("Los montos deben sumar el total del gasto")

    return list(zip(ids, partes))


def _asignar_divisiones(gasto, partes):
    gasto.divisiones = [Division(usuario_id=u, monto=m) for u, m in partes]


# ---------- CRUD ----------

def crear(grupo_id, descripcion, monto, pagado_por, participantes, tipo_division=None, fecha=None):
    grupo = grupos_servicio.obtener(grupo_id)
    descripcion = _validar_descripcion(descripcion)
    monto = validar_monto(monto)
    tipo_division = _validar_tipo(tipo_division or "iguales")
    participantes = _validar_participantes(grupo, pagado_por, participantes)
    partes = dividir_gasto(monto, tipo_division, participantes)

    gasto = Gasto(grupo_id=grupo.id, pagado_por=pagado_por, descripcion=descripcion, monto=monto,
                  fecha=_validar_fecha(fecha), tipo_division=tipo_division)
    _asignar_divisiones(gasto, partes)
    db.session.add(gasto)
    db.session.commit()
    return gasto


def listar(grupo_id):
    grupos_servicio.obtener(grupo_id)  # 404 si el grupo no existe
    return (Gasto.query.filter_by(grupo_id=grupo_id)
            .order_by(Gasto.fecha, Gasto.id).all())


def obtener(gasto_id):
    gasto = db.session.get(Gasto, gasto_id)
    if gasto is None:
        raise NoEncontrado("El gasto no existe")
    return gasto


def actualizar(gasto_id, descripcion=None, monto=None, pagado_por=None, participantes=None,
               tipo_division=None, fecha=None):
    """Actualiza solo los campos que llegan; si cambia el monto, el tipo o los participantes, re-divide."""
    gasto = obtener(gasto_id)
    nuevo_pagador = gasto.pagado_por if pagado_por is None else pagado_por
    nuevo_monto = gasto.monto if monto is None else validar_monto(monto)
    nuevo_tipo = gasto.tipo_division if tipo_division is None else _validar_tipo(tipo_division)
    redividir = monto is not None or tipo_division is not None or participantes is not None

    if participantes is None:
        # Sin participantes nuevos se reusan los actuales. Solo alcanza para "iguales":
        # de las divisiones guardadas no se pueden recuperar los porcentajes ni los montos nuevos.
        if redividir and nuevo_tipo != "iguales":
            raise DatosInvalidos("Para dividir por porcentaje o montos hay que enviar los participantes")
        participantes = [{"usuario_id": d.usuario_id} for d in gasto.divisiones]
    participantes = _validar_participantes(gasto.grupo, nuevo_pagador, participantes)

    if descripcion is not None:
        gasto.descripcion = _validar_descripcion(descripcion)
    if fecha is not None:
        gasto.fecha = _validar_fecha(fecha)
    gasto.pagado_por = nuevo_pagador

    if redividir:
        partes = dividir_gasto(nuevo_monto, nuevo_tipo, participantes)
        gasto.monto, gasto.tipo_division = nuevo_monto, nuevo_tipo
        # Primero se borran las divisiones anteriores (flush) porque su llave primaria es
        # (gasto_id, usuario_id) y las nuevas pueden repetir al mismo usuario.
        gasto.divisiones = []
        db.session.flush()
        _asignar_divisiones(gasto, partes)
    db.session.commit()
    return gasto


def eliminar(gasto_id):
    # Las divisiones se borran en cascada (ver models/gasto.py).
    db.session.delete(obtener(gasto_id))
    db.session.commit()
