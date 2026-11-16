"""Endurecimiento de la API: rutas alcanzables y documentación apagada en producción."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402


def _client(monkeypatch, *, in_lambda: bool) -> TestClient:
    from core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    if in_lambda:
        # El runtime de Lambda siempre define esta variable; fuera de Lambda no existe.
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "taxops-api-prod")
    else:
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    get_settings.cache_clear()
    return TestClient(load_fastapi_app())


@pytest.fixture(autouse=True)
def _clear_settings():
    yield
    from core.config import get_settings

    get_settings.cache_clear()


def test_reglas_renta_es_alcanzable(monkeypatch):
    # El regex de rutas de Starlette solo acepta [a-zA-Z_] en el nombre del parámetro: con
    # {año_gravable} la ruta nunca matcheaba y respondía 404 antes de pasar por la autenticación.
    client = _client(monkeypatch, in_lambda=False)

    resp = client.get("/renta/reglas/2025")

    assert resp.status_code == 401, f"la ruta no matchea: {resp.status_code}"


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_docs_apagados_en_lambda(monkeypatch, path):
    client = _client(monkeypatch, in_lambda=True)

    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_docs_disponibles_fuera_de_lambda(monkeypatch, path):
    client = _client(monkeypatch, in_lambda=False)

    assert client.get(path).status_code == 200
