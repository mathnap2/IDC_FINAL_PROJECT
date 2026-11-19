"""Saldos de un grupo y deudas simplificadas (sin Flask, para poder probarlo directo).

Convención (la misma de grupos.saldo_miembro):
    saldo > 0  → al miembro le deben
    saldo < 0  → el miembro debe

    saldo = lo que pagó en gastos − su parte de los gastos + pagos que hizo − pagos que recibió

Como cada gasto se reparte completo entre sus divisiones y cada pago suma a uno lo que resta
a otro, la suma de los saldos de un grupo siempre es 0.
"""

from collections import defaultdict
from decimal import Decimal

from app.extensions import db
from app.models import Division, Gasto, Pago
from app.services import grupos as grupos_servicio

CENTAVO = Decimal("0.01")


def _sumar_por_usuario(saldos, consulta, signo):
    for usuario_id, total in consulta:
        saldos[usuario_id] += signo * Decimal(total or 0)


def _saldos_por_usuario(grupo_id):
    """{usuario_id: saldo} con 4 consultas agregadas (no una por miembro)."""
    saldos = defaultdict(Decimal)
    suma_gastos = db.func.sum(Gasto.monto)
    suma_partes = db.func.sum(Division.monto)
    suma_pagos = db.func.sum(Pago.monto)

    _sumar_por_usuario(saldos, db.session.query(Gasto.pagado_por, suma_gastos)
                       .filter(Gasto.grupo_id == grupo_id).group_by(Gasto.pagado_por), +1)
    _sumar_por_usuario(saldos, db.session.query(Division.usuario_id, suma_partes).join(Gasto)
                       .filter(Gasto.grupo_id == grupo_id).group_by(Division.usuario_id), -1)
    _sumar_por_usuario(saldos, db.session.query(Pago.de_usuario, suma_pagos)
                       .filter(Pago.grupo_id == grupo_id).group_by(Pago.de_usuario), +1)
    _sumar_por_usuario(saldos, db.session.query(Pago.a_usuario, suma_pagos)
                       .filter(Pago.grupo_id == grupo_id).group_by(Pago.a_usuario), -1)
    return saldos


def calcular_saldos(grupo_id):
    """Saldo de cada miembro del grupo: [{usuario_id, nombre, saldo}] ordenado por id."""
    grupo = grupos_servicio.obtener(grupo_id)
    saldos = _saldos_por_usuario(grupo.id)
    return [
        {"usuario_id": m.id, "nombre": m.nombre,
         "saldo": saldos.get(m.id, Decimal(0)).quantize(CENTAVO)}
        for m in sorted(grupo.miembros, key=lambda m: m.id)
    ]


def simplificar_deudas(grupo_id):
    """Transferencias mínimas para dejar a todos en 0: [{de_usuario, a_usuario, monto}].

    Algoritmo voraz: en cada paso, quien más debe le paga a quien más le deben, por el menor
    de los dos montos. Así uno de los dos queda en 0 en cada paso, de modo que con n personas
    con saldo distinto de 0 se generan como máximo n − 1 transferencias, y las deudas en
    cadena desaparecen (A→B 100 y B→C 100 queda en A→C 100).
    """
    saldos = calcular_saldos(grupo_id)
    deudores = [[-s["saldo"], s["usuario_id"]] for s in saldos if s["saldo"] < 0]
    acreedores = [[s["saldo"], s["usuario_id"]] for s in saldos if s["saldo"] > 0]

    transferencias = []
    while deudores and acreedores:
        # Mayor monto primero; a montos iguales, el id menor (resultado determinista).
        deudores.sort(key=lambda d: (-d[0], d[1]))
        acreedores.sort(key=lambda a: (-a[0], a[1]))
        deudor, acreedor = deudores[0], acreedores[0]

        monto = min(deudor[0], acreedor[0])
        transferencias.append({"de_usuario": deudor[1], "a_usuario": acreedor[1], "monto": monto})

        deudor[0] -= monto
        acreedor[0] -= monto
        if deudor[0] == 0:
            deudores.pop(0)
        if acreedor[0] == 0:
            acreedores.pop(0)
    return transferencias
