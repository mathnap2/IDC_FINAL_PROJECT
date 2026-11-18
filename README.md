# Cuentas Claras — Backend

API REST en Flask para registrar gastos compartidos en grupos, pagos entre miembros y calcular saldos.

## Correr en local

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows (en Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt
flask --app wsgi run          # usa FLASK_CONFIG=prod por defecto; para SQLite local:
FLASK_CONFIG=dev flask --app wsgi run
```

## Correr con Docker

```bash
docker compose up --build              # API en http://localhost:8000 + PostgreSQL 16
curl http://localhost:8000/health
```

La imagen (`Dockerfile`) es multi-stage sobre `python:3.12-slim`: la primera etapa instala las dependencias en
un entorno virtual y la segunda solo copia ese entorno y el código. Corre como usuario sin privilegios con
Gunicorn en el puerto 8000 (`PORT`) y `--preload`. El número de workers se cambia con `GUNICORN_WORKERS`
(por defecto 2, suficiente para el plan F1 de Azure).

## Pruebas y lint

```bash
pytest          # incluye reporte de cobertura (pytest.ini)
flake8
```

## Variables de entorno

| Variable | Uso |
|---|---|
| `FLASK_CONFIG` | `dev`, `test` o `prod` (por defecto `prod` en `wsgi.py`) |
| `DATABASE_URL` | Cadena de conexión, p. ej. `postgresql://usuario:clave@host:5432/db_dev` |
| `SECRET_KEY` | Llave de Flask |
| `CORS_ORIGINS` | Orígenes permitidos del frontend, separados por coma (por defecto `*`) |
| `SENTRY_DSN` | Proyecto `cuentas-claras-server` en Sentry; sin esta variable Sentry no se activa |
| `SENTRY_ENVIRONMENT` | `dev` o `prod` (lo pone Terraform) |
| `SENTRY_RELEASE` | Opcional: versión o sha del commit que se despliega |
| `SENTRY_TRACES_SAMPLE_RATE` | Opcional: porcentaje de trazas (por defecto `1.0`) |

## Convenciones

- Lógica de negocio en `app/services/`; las rutas solo leen la entrada y llaman al servicio.
- Los servicios lanzan errores de `app/errores.py` (`DatosInvalidos` 400, `NoAutorizado` 401,
  `NoEncontrado` 404, `Duplicado` 409) y la app los convierte en `{"error": "..."}`.
- Dinero con `Numeric(10, 2)` y `Decimal`; en JSON se envía como texto (`"33.34"`). Fechas ISO 8601.
- Cada componente registra su blueprint en `_registrar_blueprints` de `app/__init__.py`.
- Gunicorn debe usar `--preload` para que las tablas se creen una sola vez al arrancar.

## Monitoreo (APM con Sentry)

`app/monitoreo.py` inicia Sentry antes de crear la app (solo si existe `SENTRY_DSN`):

- **Errores (Issues):** cualquier excepción no controlada responde 500 y se registra con nivel ERROR,
  lo que crea un Issue con el stack trace.
- **Trazas:** cada request queda como una traza; si viene del frontend, la traza continúa desde el navegador.
- **Mensajes (Logs):** las reglas de negocio rechazadas (400, 404, 409) se registran como WARNING.
