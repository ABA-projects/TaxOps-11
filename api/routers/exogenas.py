"""Exogenas router — async processor (SQS+worker), list, export."""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

import boto3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core import job_store
from core.config import get_settings
from dependencies import get_current_user
from schemas import ExportExogenasRequest, ProcessExogenasRequest

router = APIRouter(prefix="/exogenas", tags=["Exógenas"])

# Extensiones permitidas para certificados de retención.
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp",
}


@router.post("/process")
async def process_exogenas(
    body: ProcessExogenasRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    if not body.s3_keys:
        raise HTTPException(400, "Adjunta al menos un certificado")

    job_id = str(uuid.uuid4())
    job_store.put_job(job_id, "processing", {"progreso": 0, "total": len(body.s3_keys), "completados": 0})

    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    sqs.send_message(
        QueueUrl=settings.SQS_QUEUE_URL,
        MessageBody=json.dumps({
            "tipo": "exogenas",
            "job_id": job_id,
            "org_id": user["org_id"],
            "s3_keys": body.s3_keys,
        }),
    )
    return {"job_id": job_id, "total": len(body.s3_keys)}


@router.get("/jobs/{job_id}")
async def job_status(
    job_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")

    if job.get("status") == "done" and job.get("result_s3_key"):
        settings = get_settings()
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        try:
            obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=job["result_s3_key"])
            job["result"] = json.loads(obj["Body"].read())
        except Exception as exc:
            job["result_error"] = f"Error leyendo resultado de S3: {exc}"

    return job


@router.post("/export")
async def export_excel(
    body: ExportExogenasRequest,
    user: dict = Depends(get_current_user),
) -> Response:
    import pandas as pd

    df_1003 = pd.DataFrame(body.df_1003)
    df_detalle = pd.DataFrame(body.df_detalle)

    tmp = Path(tempfile.mktemp(suffix=".xlsx"))
    try:
        from exogenas.excel_writer import write_1003

        write_1003(df_1003, df_detalle, tmp)
        content = tmp.read_bytes()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar Excel: {exc}")
    finally:
        tmp.unlink(missing_ok=True)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=taxops_exogenas_1003.xlsx"},
    )


@router.get("/")
async def list_exogenas(
    anio: int | None = None,
    concepto: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user),
) -> dict:
    from db.database import db_available, get_db

    if not db_available():
        return {"exogenas": [], "total": 0, "db_available": False}

    from sqlalchemy import text

    filters = ["org_id = :org_id"]
    params: dict = {"org_id": user["org_id"], "limit": limit, "offset": offset}

    if anio:
        filters.append("anio = :anio")
        params["anio"] = anio
    if concepto:
        filters.append("concepto = :concepto")
        params["concepto"] = concepto

    where = " AND ".join(filters)
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    f"SELECT * FROM exogenas_results WHERE {where} "
                    "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().fetchall()
            total = db.execute(
                text(f"SELECT COUNT(*) FROM exogenas_results WHERE {where}"),
                count_params,
            ).scalar()
    except Exception:
        return {"exogenas": [], "total": 0, "db_available": False}

    return {
        "exogenas": [dict(r) for r in rows],
        "total": total,
        "db_available": True,
    }
