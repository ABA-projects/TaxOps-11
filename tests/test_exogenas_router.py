"""Tests para POST /exogenas/process y GET /exogenas/jobs/{job_id} — moto-mocked
SQS+DynamoDB+S3. No corre el worker real (mismo criterio que el plan Task 5
Step 8): se verifica el enqueue y el polling del job, no el procesamiento."""
import json
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
    monkeypatch.setenv("JOBS_TABLE_NAME", "taxops-jobs-prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")

        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="taxops-jobs-prod")["QueueUrl"]
        monkeypatch.setenv("SQS_QUEUE_URL", queue_url)

        ddb = boto3.client("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="taxops-jobs-prod",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield TestClient(load_fastapi_app())


def _auth_headers() -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="owner", email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_process_exogenas_enqueues_and_returns_job_id(client):
    res = client.post(
        "/exogenas/process",
        json={"s3_keys": ["uploads/exogenas/org1/x/cert.pdf"]},
        headers=_auth_headers(),
    )
    assert res.status_code == 200
    body = res.json()
    assert "job_id" in body
    assert body["total"] == 1

    from core import job_store
    job = job_store.get_job(body["job_id"])
    assert job["status"] == "processing"


def test_process_exogenas_requires_s3_keys(client):
    res = client.post("/exogenas/process", json={"s3_keys": []}, headers=_auth_headers())
    assert res.status_code == 400


def test_process_exogenas_requires_auth(client):
    res = client.post("/exogenas/process", json={"s3_keys": ["x"]})
    assert res.status_code in (401, 403)


def test_job_status_not_found(client):
    res = client.get("/exogenas/jobs/no-existe", headers=_auth_headers())
    assert res.status_code == 404


def test_job_status_done_embeds_result_from_s3(client):
    s3 = boto3.client("s3", region_name="us-east-1")
    result = {"df_1003": [], "df_detalle": [], "total_archivos": 1, "errores": 0}
    s3.put_object(
        Bucket="taxops-job-artifacts-prod",
        Key="uploads/results/exogenas/job1.json",
        Body=json.dumps(result).encode("utf-8"),
    )

    from core import job_store
    job_store.put_job("job1", "done", {"result_s3_key": "uploads/results/exogenas/job1.json"})

    res = client.get("/exogenas/jobs/job1", headers=_auth_headers())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "done"
    assert body["result"]["total_archivos"] == 1


def test_job_status_processing_no_result_yet(client):
    from core import job_store
    job_store.put_job("job2", "processing", {"progreso": 40})

    res = client.get("/exogenas/jobs/job2", headers=_auth_headers())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "processing"
    assert "result" not in body
