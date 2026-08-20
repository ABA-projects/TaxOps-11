"""Tests para POST /invoices/process — moto-mocked S3.

No existía ningún test previo para invoices.py en el repo (verificado antes de escribir
este archivo) — este es un archivo nuevo, no una actualización de uno existente.
"""
import sys
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402

# PDF real mínimo — suficiente para que pdfplumber/lxml no revienten al abrirlo,
# aunque no tenga texto útil (el pipeline de extracción real ya maneja "no encontró
# datos" como resultado válido de negocio, no como excepción).
_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")
        yield TestClient(load_fastapi_app()), s3


def _auth_headers() -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="owner", email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_process_invoices_from_s3_keys(client):
    test_client, s3 = client
    s3.put_object(
        Bucket="taxops-job-artifacts-prod",
        Key="uploads/facturas/org1/x/factura.pdf",
        Body=_MINIMAL_PDF,
    )

    res = test_client.post(
        "/invoices/process",
        json={"s3_keys": ["uploads/facturas/org1/x/factura.pdf"], "ingresos": []},
        headers=_auth_headers(),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_archivos"] == 1
    assert "df_base" in body
    assert "df_val" in body
    assert "df_pror" in body


def test_process_invoices_missing_s3_key_returns_502(client):
    test_client, _s3 = client
    res = test_client.post(
        "/invoices/process",
        json={"s3_keys": ["uploads/facturas/org1/x/no-existe.pdf"], "ingresos": []},
        headers=_auth_headers(),
    )
    assert res.status_code == 502


def test_process_invoices_requires_auth(client):
    test_client, _s3 = client
    res = test_client.post(
        "/invoices/process",
        json={"s3_keys": [], "ingresos": []},
    )
    assert res.status_code in (401, 403)


def test_process_invoices_empty_s3_keys(client):
    test_client, _s3 = client
    res = test_client.post(
        "/invoices/process",
        json={"s3_keys": [], "ingresos": []},
        headers=_auth_headers(),
    )
    assert res.status_code == 200
    assert res.json()["total_archivos"] == 0
