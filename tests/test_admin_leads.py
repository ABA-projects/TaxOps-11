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


def _headers(role: str) -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role=role, email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_list_leads_requires_admin(client):
    res = client.get("/admin/leads", headers=_headers("contador"))
    assert res.status_code == 403


def test_list_leads_returns_list_for_admin(client):
    res = client.get("/admin/leads", headers=_headers("owner"))
    assert res.status_code == 200
    assert res.json() == []
