"""api/core/job_store.py — Estado de background jobs en DynamoDB.

Reemplaza los dicts en memoria (`_jobs` en `routers/renta_documentos.py`,
`in_memory_jobs` en `services/renta/job_processor.py`) que perdían todo el
estado de los jobs en cada restart/redeploy. Ver
docs/superpowers/plans/2026-08-05-taxops11-aws-migration.md, Chunk 2, Task 2.3.

La tabla (`taxops-jobs-prod`, ya creada vía Terraform en Chunk 2, Task 2.1) tiene
hash_key `job_id` (String) y TTL sobre el atributo `expires_at` — cada escritura
renueva el TTL a ~48h en el futuro.
"""
from __future__ import annotations

import time
from typing import Any

import boto3

from .config import get_settings

_TTL_SECONDS = 48 * 3600


def _table():
    settings = get_settings()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    return dynamodb.Table(settings.JOBS_TABLE_NAME)


def put_job(job_id: str, status: str, data: dict[str, Any] | None = None) -> None:
    """Crea o reemplaza el estado de un job.

    `data` es el resto de campos del job (progreso, total, completados, result,
    error, etc.) — se guarda tal cual junto con `job_id`/`status`/`expires_at`.
    """
    item: dict[str, Any] = {**(data or {}), "job_id": job_id, "status": status}
    item["expires_at"] = int(time.time()) + _TTL_SECONDS
    _table().put_item(Item=item)


def get_job(job_id: str) -> dict[str, Any] | None:
    """Lee el estado de un job. Devuelve None si no existe (o ya expiró por TTL)."""
    response = _table().get_item(Key={"job_id": job_id})
    return response.get("Item")
