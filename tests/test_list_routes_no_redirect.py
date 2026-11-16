"""Regresión: los listados GET de la raíz de un router no deben redirigir.

En producción la barra final se pierde antes de llegar a la app (la Lambda recibe `/invoices/`
como `/invoices`). Una ruta declarada como `@router.get("/")` solo matchea `/invoices/`, así que
Starlette respondía 307 hacia `/invoices/` — con el host crudo de la Lambda, no api.taxopsapp.com —
y como la barra se vuelve a perder, la redirección se repetía sin fin (bucle). El frontend pide
`GET /novedades` sin barra, por lo que la página Novedades quedaba rota.

Las rutas raíz deben declararse como `""` para que matcheen el path sin barra directamente.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    from core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    get_settings.cache_clear()
    try:
        yield TestClient(load_fastapi_app())
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("path", ["/invoices", "/exogenas", "/novedades"])
def test_listado_sin_barra_final_no_redirige(client, path):
    # follow_redirects=False: si hay 307 queremos verlo, no que el cliente lo siga en silencio.
    resp = client.get(path, follow_redirects=False)

    assert resp.status_code != 307, (
        f"GET {path} redirige a {resp.headers.get('location')!r}: en prod provoca un bucle"
    )
    # Sin token la ruta se encuentra y exige autenticación.
    assert resp.status_code == 401
