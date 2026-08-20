"""Tests para POST /uploads/presign — moto-mocked S3."""
import sys
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")
        yield TestClient(load_fastapi_app())


def _auth_headers(client) -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="owner", email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_presign_facturas_valid_pdf(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={"contexto": "facturas", "archivos": [{"filename": "factura.pdf", "content_type": "application/pdf"}]},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["uploads"]) == 1
    upload = body["uploads"][0]
    assert upload["filename"] == "factura.pdf"
    assert upload["s3_key"].startswith("uploads/facturas/org1/")
    assert upload["s3_key"].endswith("factura.pdf")
    assert "url" in upload
    assert "fields" in upload
    assert "key" in upload["fields"]


def test_presign_exogenas_valid_types(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={
            "contexto": "exogenas",
            "archivos": [
                {"filename": "cert1.pdf", "content_type": "application/pdf"},
                {"filename": "cert2.jpg", "content_type": "image/jpeg"},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert len(res.json()["uploads"]) == 2


def test_presign_rejects_disallowed_extension(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={
            "contexto": "exogenas",
            "archivos": [{"filename": "virus.exe", "content_type": "application/x-msdownload"}],
        },
        headers=headers,
    )
    assert res.status_code == 200  # no falla el request completo — rechaza esa entrada específica
    body = res.json()
    assert len(body["uploads"]) == 0
    assert len(body["rechazados"]) == 1
    assert body["rechazados"][0]["filename"] == "virus.exe"


def test_presign_invalid_contexto(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={"contexto": "no_existe", "archivos": [{"filename": "a.pdf", "content_type": "application/pdf"}]},
        headers=headers,
    )
    assert res.status_code == 422


def test_presign_requires_auth(client):
    res = client.post(
        "/uploads/presign",
        json={"contexto": "facturas", "archivos": [{"filename": "a.pdf", "content_type": "application/pdf"}]},
    )
    assert res.status_code in (401, 403)
