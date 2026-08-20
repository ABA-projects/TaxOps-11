"""Tests for api/worker_handler.py — SQS-triggered Lambda handler for renta jobs.

Uses moto to mock DynamoDB (job_store) and mocks `process_documento_job` directly
rather than S3/OCR/DB, since the handler's own responsibility is just: fan out over
`documentos`, call `process_documento_job` per doc, and update the parent job.
"""
from __future__ import annotations

import json
import os

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
        os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
        os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="taxops-jobs-prod",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


def _sqs_event(body: dict) -> dict:
    return {"Records": [{"body": json.dumps(body)}]}


def test_handler_processes_all_documentos_and_marks_job_done(dynamodb_table, monkeypatch):
    from api.core import job_store
    import api.worker_handler as worker_handler

    calls: list[dict] = []

    def _fake_process(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "services.renta.job_processor.process_documento_job", _fake_process
    )

    body = {
        "job_id": "parent-job-1",
        "contrib_id": "contrib-1",
        "org_id": "org-1",
        "año": 2026,
        "documentos": [
            {
                "doc_id": "doc-1",
                "s3_key": "renta/org-1/contrib-1/2026/a.pdf",
                "filename": "a.pdf",
                "mime_type": "application/pdf",
            },
            {
                "doc_id": "doc-2",
                "s3_key": "renta/org-1/contrib-1/2026/b.pdf",
                "filename": "b.pdf",
                "mime_type": "application/pdf",
            },
        ],
    }

    worker_handler.handler(_sqs_event(body), context=None)

    assert len(calls) == 2
    assert calls[0] == {
        "job_id": "parent-job-1_1",
        "doc_id": "doc-1",
        "s3_key": "renta/org-1/contrib-1/2026/a.pdf",
        "filename": "a.pdf",
        "mime_type": "application/pdf",
        "contrib_id": "contrib-1",
        "org_id": "org-1",
        "año": 2026,
    }
    assert calls[1]["doc_id"] == "doc-2"
    assert calls[1]["job_id"] == "parent-job-1_2"

    job = job_store.get_job("parent-job-1")
    assert job["status"] == "done"
    assert job["completados"] == 2
    assert job["progreso"] == 100


def test_handler_continues_batch_when_one_doc_raises(dynamodb_table, monkeypatch):
    """A single process_documento_job failure must not abort the rest of the
    batch or crash the handler — the parent job still reaches status=done."""
    from api.core import job_store
    import api.worker_handler as worker_handler

    calls: list[str] = []

    def _fake_process(**kwargs):
        calls.append(kwargs["doc_id"])
        if kwargs["doc_id"] == "doc-1":
            raise RuntimeError("simulated OCR crash")

    monkeypatch.setattr(
        "services.renta.job_processor.process_documento_job", _fake_process
    )

    body = {
        "job_id": "parent-job-2",
        "contrib_id": "contrib-1",
        "org_id": "org-1",
        "año": 2026,
        "documentos": [
            {
                "doc_id": "doc-1",
                "s3_key": "renta/org-1/contrib-1/2026/a.pdf",
                "filename": "a.pdf",
                "mime_type": "application/pdf",
            },
            {
                "doc_id": "doc-2",
                "s3_key": "renta/org-1/contrib-1/2026/b.pdf",
                "filename": "b.pdf",
                "mime_type": "application/pdf",
            },
        ],
    }

    # Must not raise.
    worker_handler.handler(_sqs_event(body), context=None)

    # Both docs were attempted despite doc-1 raising.
    assert calls == ["doc-1", "doc-2"]

    job = job_store.get_job("parent-job-2")
    assert job["status"] == "done"
    assert job["completados"] == 2


def test_handler_processes_multiple_sqs_records(dynamodb_table, monkeypatch):
    from api.core import job_store
    import api.worker_handler as worker_handler

    calls: list[str] = []
    monkeypatch.setattr(
        "services.renta.job_processor.process_documento_job",
        lambda **kwargs: calls.append(kwargs["doc_id"]),
    )

    body_a = {
        "job_id": "job-a",
        "contrib_id": "contrib-1",
        "org_id": "org-1",
        "año": 2026,
        "documentos": [
            {"doc_id": "doc-a1", "s3_key": "k1", "filename": "a1.pdf", "mime_type": "application/pdf"},
        ],
    }
    body_b = {
        "job_id": "job-b",
        "contrib_id": "contrib-1",
        "org_id": "org-1",
        "año": 2026,
        "documentos": [
            {"doc_id": "doc-b1", "s3_key": "k2", "filename": "b1.pdf", "mime_type": "application/pdf"},
        ],
    }

    event = {"Records": [
        {"body": json.dumps(body_a)},
        {"body": json.dumps(body_b)},
    ]}

    worker_handler.handler(event, context=None)

    assert calls == ["doc-a1", "doc-b1"]
    assert job_store.get_job("job-a")["status"] == "done"
    assert job_store.get_job("job-b")["status"] == "done"


def test_handler_dispatches_renta_by_default(dynamodb_table, monkeypatch):
    """Un mensaje sin 'tipo' (formato viejo, ya en vuelo) sigue yendo a Renta."""
    import api.worker_handler as worker_handler

    called = {}
    monkeypatch.setattr(
        worker_handler, "_process_renta_batch", lambda body: called.update(renta=body)
    )

    body = {"job_id": "j1", "contrib_id": "c1", "org_id": "o1", "año": 2026, "documentos": []}
    worker_handler.handler(_sqs_event(body), context=None)

    assert called["renta"]["job_id"] == "j1"


def test_handler_dispatches_exogenas(dynamodb_table, monkeypatch):
    import api.worker_handler as worker_handler

    called = {}
    monkeypatch.setattr(
        worker_handler, "_process_exogenas_batch", lambda body: called.update(exogenas=body)
    )

    body = {"tipo": "exogenas", "job_id": "j2", "org_id": "o1", "s3_keys": []}
    worker_handler.handler(_sqs_event(body), context=None)

    assert called["exogenas"]["job_id"] == "j2"
