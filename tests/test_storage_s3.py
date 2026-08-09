"""Tests for services/renta/storage.py — S3-backed document storage.

Uses moto to mock S3 (no live AWS calls). Creates a bucket matching the
default `S3_BUCKET_RENTA_DOCS` setting before each test.
"""
from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def s3_bucket():
    with mock_aws():
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
        os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
        os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

        from api.core.config import get_settings
        settings = get_settings()

        client = boto3.client("s3", region_name=settings.AWS_REGION)
        client.create_bucket(Bucket=settings.S3_BUCKET_RENTA_DOCS)
        yield


def test_upload_to_s3_returns_key(s3_bucket):
    from services.renta.storage import upload_to_s3

    key = upload_to_s3(
        file_bytes=b"contenido-pdf",
        org_id="org-1",
        contrib_id="contrib-1",
        año=2026,
        filename="factura.pdf",
        content_type="application/pdf",
    )

    assert key == "renta/org-1/contrib-1/2026/factura.pdf"


def test_get_signed_url_returns_url(s3_bucket):
    from services.renta.storage import get_signed_url, upload_to_s3

    key = upload_to_s3(
        file_bytes=b"contenido-pdf",
        org_id="org-1",
        contrib_id="contrib-1",
        año=2026,
        filename="factura.pdf",
    )

    url = get_signed_url(key, expiry_hours=2)

    assert url.startswith("https://")
    assert key in url


def test_delete_from_s3_removes_object(s3_bucket):
    from api.core.config import get_settings
    from services.renta.storage import delete_from_s3, upload_to_s3

    key = upload_to_s3(
        file_bytes=b"contenido-pdf",
        org_id="org-1",
        contrib_id="contrib-1",
        año=2026,
        filename="factura.pdf",
    )

    delete_from_s3(key)

    settings = get_settings()
    client = boto3.client("s3", region_name=settings.AWS_REGION)
    with pytest.raises(Exception):
        client.get_object(Bucket=settings.S3_BUCKET_RENTA_DOCS, Key=key)


def test_delete_from_s3_silently_ignores_missing_key(s3_bucket):
    from services.renta.storage import delete_from_s3

    # Should not raise even though the key doesn't exist.
    delete_from_s3("renta/org-1/contrib-1/2026/no-existe.pdf")


def test_download_from_s3_returns_bytes(s3_bucket):
    from services.renta.storage import download_from_s3, upload_to_s3

    key = upload_to_s3(
        file_bytes=b"contenido-pdf",
        org_id="org-1",
        contrib_id="contrib-1",
        año=2026,
        filename="factura.pdf",
    )

    content = download_from_s3(key)

    assert content == b"contenido-pdf"


def test_upload_failure_is_non_fatal_for_job_processor(monkeypatch):
    """job_processor.process_documento_job must keep running OCR/classify
    even if the S3 upload raises (non-fatal try/except around the upload)."""
    import services.renta.job_processor as job_processor

    def _boom(**kwargs):
        raise RuntimeError("simulated S3 outage")

    monkeypatch.setattr("services.renta.storage.upload_to_s3", _boom)
    monkeypatch.setattr(
        "services.renta.ocr_agent.extract_text", lambda *a, **k: "texto ocr"
    )
    monkeypatch.setattr(
        "services.renta.classifier_agent.classify_document",
        lambda *a, **k: {
            "categoria": "otros",
            "confianza": 0.5,
            "carpeta_virtual": "otros",
            "datos_extraidos": {},
        },
    )
    monkeypatch.setattr(job_processor, "_update_doc_in_db", lambda **k: None)
    monkeypatch.setattr(job_processor, "_mark_doc_error", lambda *a, **k: None)

    calls: list[tuple] = []
    monkeypatch.setattr(
        "api.core.job_store.put_job",
        lambda job_id, status, data=None: calls.append((job_id, status, data)),
    )

    job_processor.process_documento_job(
        job_id="job-1",
        doc_id="doc-1",
        file_bytes=b"contenido-pdf",
        filename="factura.pdf",
        mime_type="application/pdf",
        contrib_id="contrib-1",
        org_id="org-1",
        año=2026,
    )

    # Final job update should reflect success ("done"), proving the upload
    # failure did not abort the pipeline.
    statuses = [status for _, status, _ in calls]
    assert "done" in statuses
    assert "error" not in statuses
