"""services/renta/storage.py — GCS upload + signed URL for renta documents."""
from __future__ import annotations

import datetime
import os

_BUCKET_NAME = os.environ.get("GCS_BUCKET", "taxops-docs")


def _client():
    from google.cloud import storage
    return storage.Client()


def upload_to_gcs(
    file_bytes: bytes,
    org_id: str,
    contrib_id: str,
    año: int,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a file to GCS. Returns the gs:// URI (used as s3_key in DB)."""
    client = _client()
    bucket = client.bucket(_BUCKET_NAME)
    blob_name = f"renta/{org_id}/{contrib_id}/{año}/{filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type=content_type)
    return f"gs://{_BUCKET_NAME}/{blob_name}"


def get_signed_url(gcs_key: str, expiry_hours: int = 1) -> str:
    """Generate a signed URL for temporary read access.

    Falls back to an authenticated URL if signing isn't available
    (e.g. when running with a SA that can't self-sign tokens).
    """
    # gcs_key format: gs://bucket/path/to/file
    path = gcs_key.removeprefix(f"gs://{_BUCKET_NAME}/")
    client = _client()
    bucket = client.bucket(_BUCKET_NAME)
    blob = bucket.blob(path)
    try:
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(hours=expiry_hours),
            method="GET",
            version="v4",
        )
        return url
    except Exception:
        # Cloud Run SA can't self-sign — return public URL if bucket is not private
        return f"https://storage.googleapis.com/{_BUCKET_NAME}/{path}"


def delete_from_gcs(gcs_key: str) -> None:
    """Delete a blob. Silently ignores NotFound."""
    path = gcs_key.removeprefix(f"gs://{_BUCKET_NAME}/")
    try:
        client = _client()
        client.bucket(_BUCKET_NAME).blob(path).delete()
    except Exception:
        pass
