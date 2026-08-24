import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    return TestClient(load_fastapi_app())


def _auth_headers() -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="contador", email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_list_novedades_requires_auth(client):
    res = client.get("/novedades")
    assert res.status_code in (401, 403)


def test_list_novedades_returns_list(client, monkeypatch):
    # db_available() será False sin una Postgres real — el endpoint debe degradar a lista vacía,
    # no crashear (mismo criterio que list_exogenas/list_invoices existentes)
    res = client.get("/novedades", headers=_auth_headers())
    assert res.status_code == 200
    assert res.json() == []
