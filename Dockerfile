# syntax=docker/dockerfile:1

# ---------- Etapa 1: compilar las dependencias ----------
# Se instalan en un entorno virtual aparte para copiar solo el resultado a la imagen final
# (sin pip cache, compiladores ni archivos temporales).
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt


# ---------- Etapa 2: imagen de ejecución ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_CONFIG=prod \
    PORT=8000 \
    GUNICORN_WORKERS=2

# Usuario sin privilegios: el proceso no corre como root.
RUN useradd --create-home --uid 1000 app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app app/ app/
COPY --chown=app:app wsgi.py .

USER app
EXPOSE 8000

# Azure también revisa /health (ver health_check_path en Terraform).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# --preload: la app (y db.create_all) se carga una sola vez antes de crear los workers.
CMD ["sh", "-c", "exec gunicorn --preload --workers ${GUNICORN_WORKERS} --bind 0.0.0.0:${PORT} --access-logfile - wsgi:app"]
