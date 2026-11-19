# Cuentas Claras — Backend

API REST en Flask para registrar gastos compartidos en grupos, pagos entre miembros y calcular saldos.

> 📋 **Tablero del proyecto:** [Cuentas Claras](https://github.com/users/angelcortes1705/projects/3)
> · Repos: [backend](https://github.com/mathnap2/IDC_FINAL_PROJECT)
> · [frontend](https://github.com/mathnap2/IDC_FINAL_PROJECT_FRONTEND)
> · [infraestructura](https://github.com/mathnap2/IDC_FINAL_PROJECT_TERRAFORM)

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

## Pruebas UAT

`uat/` contiene pruebas de aceptación que hablan con una API desplegada por HTTP y borran lo que crean:

```bash
UAT_BASE_URL=http://localhost:8000 pytest uat -o addopts=""
```

## Pipeline (GitHub Actions)

`.github/workflows/pipeline.yml`:

| Evento | Jobs |
|---|---|
| PR a `develop` o `main` | `ci`: flake8, pytest con cobertura ≥ 80 % y reportes (artefacto + resumen) |
| Push a `develop` | `ci` → `build` (`:dev` y `:sha-<commit>`) → `deploy-dev` → `uat` contra dev |
| Push a `main` | `ci` → `build` (`:latest` y `:sha-<commit>`) → `deploy-prod` (espera aprobación del environment `production`) |

La imagen se publica en Docker Hub como `mathnap2/cuentas-claras` y se despliega la etiqueta `:sha-<commit>`
para saber exactamente qué versión corre en cada ambiente. El login a Azure es por OIDC (sin contraseñas).
Si cambian los nombres de las Web Apps, se actualizan en `env:` al inicio del workflow.

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

## Pagos y saldos

| Operación | Petición | Cuerpo / respuesta |
|---|---|---|
| Registrar pago | `POST /api/grupos/<id>/pagos` | `{de_usuario, a_usuario, monto, fecha?}` (fecha `AAAA-MM-DD`, por defecto hoy) |
| Listar pagos del grupo | `GET /api/grupos/<id>/pagos` | ordenados por fecha |
| Ver / editar / eliminar pago | `GET` / `PUT` / `DELETE /api/pagos/<id>` | `PUT` acepta los mismos campos, todos opcionales |
| Saldos | `GET /api/grupos/<id>/saldos` | `[{usuario_id, nombre, saldo}]` |
| Deudas simplificadas | `GET /api/grupos/<id>/deudas-simplificadas` | `[{de_usuario, a_usuario, monto}]` |

Reglas: el monto es mayor a 0 y con máximo 2 decimales; no se puede pagar a uno mismo; quien paga y
quien recibe son miembros del grupo. El saldo es positivo si al miembro le deben y negativo si debe, y los
saldos de un grupo siempre suman 0. Las deudas simplificadas se calculan con un algoritmo voraz (quien más
debe le paga a quien más le deben), que deja a todos en 0 con a lo más n − 1 transferencias: por ejemplo,
A→B 100 y B→C 100 queda en A→C 100.

## Monitoreo (APM con Sentry)

`app/monitoreo.py` inicia Sentry antes de crear la app (solo si existe `SENTRY_DSN`):

- **Errores (Issues):** cualquier excepción no controlada responde 500 y se registra con nivel ERROR,
  lo que crea un Issue con el stack trace.
- **Trazas:** cada request queda como una traza; si viene del frontend, la traza continúa desde el navegador.
- **Mensajes (Logs):** las reglas de negocio rechazadas (400, 404, 409) se registran como WARNING.
