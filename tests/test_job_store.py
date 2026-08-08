"""Tests for api/core/job_store.py — DynamoDB-backed job status store.

Uses moto to mock DynamoDB (no live AWS calls). Creates a table matching the
real Terraform-managed `taxops-jobs-prod` schema (hash_key job_id, TTL on
expires_at) before each test.
"""
from __future__ import annotations

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


def test_put_and_get_job(dynamodb_table):
    from api.core import job_store

    job_store.put_job("job-1", "processing", {"progreso": 10, "total": 3})
    job = job_store.get_job("job-1")

    assert job is not None
    assert job["job_id"] == "job-1"
    assert job["status"] == "processing"
    assert job["progreso"] == 10
    assert job["total"] == 3
    assert "expires_at" in job


def test_get_job_missing_returns_none(dynamodb_table):
    from api.core import job_store

    assert job_store.get_job("does-not-exist") is None


def test_put_job_overwrites_previous_state(dynamodb_table):
    from api.core import job_store

    job_store.put_job("job-2", "processing", {"progreso": 0, "total": 2})
    job_store.put_job("job-2", "done", {"progreso": 100, "total": 2, "categoria": "renta"})

    job = job_store.get_job("job-2")
    assert job["status"] == "done"
    assert job["progreso"] == 100
    assert job["categoria"] == "renta"


def test_put_job_sets_ttl_around_48h(dynamodb_table):
    import time

    from api.core import job_store

    before = int(time.time())
    job_store.put_job("job-3", "error", {"error": "boom"})
    after = int(time.time())

    job = job_store.get_job("job-3")
    expected_min = before + 48 * 3600 - 5
    expected_max = after + 48 * 3600 + 5
    assert expected_min <= job["expires_at"] <= expected_max
