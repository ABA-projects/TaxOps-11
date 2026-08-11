"""services/renta/storage.py — S3 upload + signed URL for renta documents."""
from __future__ import annotations

import boto3

from api.core.config import get_settings


def _client():
    settings = get_settings()
    return boto3.client("s3", region_name=settings.AWS_REGION)


def upload_to_s3(
    file_bytes: bytes,
    org_id: str,
    contrib_id: str,
    año: int,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a file to S3. Returns the object key (used as s3_key in DB)."""
    settings = get_settings()
    key = f"renta/{org_id}/{contrib_id}/{año}/{filename}"
    _client().put_object(
        Bucket=settings.S3_BUCKET_RENTA_DOCS,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


def get_signed_url(s3_key: str, expiry_hours: int = 1) -> str:
    """Generate a presigned URL for temporary read access."""
    settings = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_RENTA_DOCS, "Key": s3_key},
        ExpiresIn=expiry_hours * 3600,
    )


def delete_from_s3(s3_key: str) -> None:
    """Delete an object. Silently ignores failures."""
    settings = get_settings()
    try:
        _client().delete_object(Bucket=settings.S3_BUCKET_RENTA_DOCS, Key=s3_key)
    except Exception:
        pass


def download_from_s3(s3_key: str) -> bytes:
    """Download an object's bytes."""
    settings = get_settings()
    response = _client().get_object(Bucket=settings.S3_BUCKET_RENTA_DOCS, Key=s3_key)
    return response["Body"].read()
