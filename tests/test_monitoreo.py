import sentry_sdk

from app import monitoreo


def test_sin_dsn_no_se_inicia_sentry(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert monitoreo.iniciar_sentry() is False


def test_con_dsn_se_inicia_con_ambiente(monkeypatch):
    llamadas = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: llamadas.update(kw))
    monkeypatch.setenv("SENTRY_DSN", "https://clave@o0.ingest.sentry.io/0")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "dev")

    assert monitoreo.iniciar_sentry() is True
    assert llamadas["environment"] == "dev"
    assert llamadas["traces_sample_rate"] == 1.0
    assert llamadas["send_default_pii"] is False


def test_error_no_controlado_devuelve_500_y_se_registra(app, caplog):
    @app.get("/explota")
    def explota():
        raise RuntimeError("falla inesperada")

    r = app.test_client().get("/explota")
    assert r.status_code == 500
    assert r.get_json() == {"error": "Error interno del servidor"}
    assert "Error no controlado en GET /explota" in caplog.text


def test_regla_rechazada_queda_en_el_log(client, caplog):
    client.get("/api/usuarios/999")
    assert "GET /api/usuarios/999 rechazado (404): El usuario no existe" in caplog.text
