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

## Convenciones

- Lógica de negocio en `app/services/`; las rutas solo leen la entrada y llaman al servicio.
- Los servicios lanzan errores de `app/errores.py` (`DatosInvalidos` 400, `NoAutorizado` 401,
  `NoEncontrado` 404, `Duplicado` 409) y la app los convierte en `{"error": "..."}`.
- Dinero con `Numeric(10, 2)` y `Decimal`; en JSON se envía como texto (`"33.34"`). Fechas ISO 8601.
- Cada componente registra su blueprint en `_registrar_blueprints` de `app/__init__.py`.
- Gunicorn debe usar `--preload` para que las tablas se creen una sola vez al arrancar.
