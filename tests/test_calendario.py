"""Tests para /calendario/eventos — moto-mocked S3 (el storage cambió de archivo local a S3)."""
import json
import sys
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402

_CALENDARIO_KEY = "config/calendario_2026.json"
_BUCKET = "taxops-job-artifacts-prod"


@pytest.fixture
def client(monkeypatch):
    from core.config import get_settings

    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", _BUCKET)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    get_settings.cache_clear()  # get_settings() es @lru_cache a nivel de proceso — sin esto,
    # un test previo de otro archivo que ya lo llamó deja un Settings() viejo cacheado.
    try:
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket=_BUCKET)
            yield TestClient(load_fastapi_app())
    finally:
        get_settings.cache_clear()  # no dejar el cache sucio para los tests que corren después


def _auth_headers(role: str = "owner", is_superadmin: bool = False) -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role=role, email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def _superadmin_headers(monkeypatch) -> dict:
    monkeypatch.setenv("TAXOPS_SUPERADMIN_EMAILS", "super@taxops.com")
    from core.config import get_settings
    get_settings.cache_clear()  # el env recién seteado no se ve hasta limpiar el cache (se
    # llenó al cargar la app en el fixture `client`) — el fixture lo vuelve a limpiar al salir
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="owner", email="super@taxops.com")
    return {"Authorization": f"Bearer {token}"}


def test_get_eventos_empty_when_no_s3_object(client):
    res = client.get("/calendario/eventos", headers=_auth_headers())
    assert res.status_code == 200
    assert res.json() == []


def test_put_eventos_writes_to_s3(client, monkeypatch):
    headers = _superadmin_headers(monkeypatch)
    evento = {
        "id": "1", "fecha": "2026-09-15", "titulo": "IVA bimestral",
        "descripcion": "Vencimiento IVA", "tipo": "iva", "urgencia": "alta",
    }
    put_res = client.put("/calendario/eventos", json=[evento], headers=headers)
    assert put_res.status_code == 200

    s3 = boto3.client("s3", region_name="us-east-1")
    obj = s3.get_object(Bucket=_BUCKET, Key=_CALENDARIO_KEY)
    data = json.loads(obj["Body"].read())
    assert data[0]["titulo"] == "IVA bimestral"


def test_put_eventos_persists_and_get_returns_it(client, monkeypatch):
    headers = _superadmin_headers(monkeypatch)
    evento = {
        "id": "1", "fecha": "2026-09-15", "titulo": "IVA bimestral",
        "descripcion": "Vencimiento IVA", "tipo": "iva", "urgencia": "alta",
    }
    client.put("/calendario/eventos", json=[evento], headers=headers)

    get_res = client.get("/calendario/eventos", headers=_auth_headers())
    assert get_res.status_code == 200
    assert get_res.json() == [evento | {"articulo": None, "link": None, "alertaDias": None}]


def test_put_eventos_requires_superadmin(client):
    res = client.put("/calendario/eventos", json=[], headers=_auth_headers())
    assert res.status_code == 403
