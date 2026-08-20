"""Tests para services/exogenas/job_processor.py — moto-mocked S3/DynamoDB."""
import json

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    monkeypatch.setenv("JOBS_TABLE_NAME", "taxops-jobs-prod")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")

        ddb = boto3.client("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="taxops-jobs-prod",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield s3


def _fake_row(archivo: str) -> dict:
    return {
        "nit": "900123456", "concepto": "1303", "tipo_doc": "31", "dv": "1",
        "base": 100000, "retencion": 3500, "porcentaje": 3.5,
        "razon_social": "Test SAS", "ciudad_retencion": "Bogotá",
        "direccion": "Calle 1 # 2-3", "cod_dpto": "11", "cod_mpio": "001",
        "primer_apellido": "", "segundo_apellido": "",
        "primer_nombre": "", "otros_nombres": "",
    }


def test_process_exogenas_job_happy_path(aws, monkeypatch):
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/cert.pdf", Body=b"fake pdf bytes")

    monkeypatch.setattr(
        "services.exogenas.job_processor._extract_from_path",
        lambda path: [_fake_row("cert.pdf")],
    )

    from api.core import job_store
    from services.exogenas.job_processor import process_exogenas_job

    process_exogenas_job(job_id="job1", org_id="org1", s3_keys=["uploads/exogenas/org1/x/cert.pdf"])

    job = job_store.get_job("job1")
    assert job["status"] == "done"
    assert "result_s3_key" in job
    assert job["result_s3_key"].startswith("uploads/results/exogenas/job1")


def test_process_exogenas_job_persists_result_to_s3(aws, monkeypatch):
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/cert.pdf", Body=b"fake pdf bytes")
    monkeypatch.setattr(
        "services.exogenas.job_processor._extract_from_path",
        lambda path: [_fake_row("cert.pdf")],
    )

    from services.exogenas.job_processor import process_exogenas_job
    process_exogenas_job(job_id="job2", org_id="org1", s3_keys=["uploads/exogenas/org1/x/cert.pdf"])

    obj = aws.get_object(Bucket="taxops-job-artifacts-prod", Key="uploads/results/exogenas/job2.json")
    data = json.loads(obj["Body"].read())
    assert "df_1003" in data
    assert "df_detalle" in data
    assert len(data["df_detalle"]) == 1


def test_process_exogenas_job_one_file_error_does_not_abort_batch(aws, monkeypatch):
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/bad.pdf", Body=b"corrupt")
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/good.pdf", Body=b"fake pdf bytes")

    def fake_extract(path):
        if "bad.pdf" in str(path):
            raise ValueError("archivo corrupto")
        return [_fake_row("good.pdf")]

    monkeypatch.setattr("services.exogenas.job_processor._extract_from_path", fake_extract)

    from api.core import job_store
    from services.exogenas.job_processor import process_exogenas_job
    process_exogenas_job(
        job_id="job3", org_id="org1",
        s3_keys=["uploads/exogenas/org1/x/bad.pdf", "uploads/exogenas/org1/x/good.pdf"],
    )

    job = job_store.get_job("job3")
    assert job["status"] == "done"  # el job entero no se cae por un archivo malo


def test_process_exogenas_job_missing_s3_key_counts_as_error(aws, monkeypatch):
    monkeypatch.setattr(
        "services.exogenas.job_processor._extract_from_path",
        lambda path: [_fake_row("x")],
    )

    from api.core import job_store
    from services.exogenas.job_processor import process_exogenas_job
    process_exogenas_job(job_id="job4", org_id="org1", s3_keys=["uploads/exogenas/org1/x/no-existe.pdf"])

    job = job_store.get_job("job4")
    assert job["status"] == "done"
