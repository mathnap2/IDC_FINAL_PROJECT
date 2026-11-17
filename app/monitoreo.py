"""APM con Sentry: errores, trazas de cada request y logs.

Solo se activa si existe la variable SENTRY_DSN (en Azure la pone Terraform).
En pruebas y en local sin DSN no se envía nada.
"""

import logging
import os

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration


def iniciar_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "local"),
        release=os.getenv("SENTRY_RELEASE"),  # el pipeline puede poner el sha del commit
        # Trazas: 100 % porque el tráfico del proyecto es muy bajo. En una app real
        # se bajaría en producción (p. ej. 0.1) con SENTRY_TRACES_SAMPLE_RATE.
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
        enable_logs=True,
        integrations=[
            # logs INFO o mayores → Sentry Logs; ERROR o mayores → además crean un Issue.
            LoggingIntegration(level=logging.INFO, sentry_logs_level=logging.INFO, event_level=logging.ERROR),
        ],
        # No mandar IPs ni cuerpos con contraseñas.
        send_default_pii=False,
    )
    return True
