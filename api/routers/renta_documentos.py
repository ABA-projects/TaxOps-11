"""renta_documentos.py — Upload, list, preview, delete documents for a contribuyente."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from dependencies import get_current_user, require_admin

router = APIRouter(prefix="/renta", tags=["Renta · Documentos"])

# One job at a time to avoid OOM (OCR is memory-intensive)
_executor = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, dict[str, Any]] = {}

_ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/tiff", "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
_MAX_MB = 20


def _get_contribuyente_or_404(contrib_id: str, org_id: str) -> dict:
    from db.database_renta import get_contribuyente
    c = get_contribuyente(contrib_id, org_id)
    if not c:
        raise HTTPException(404, "Contribuyente no encontrado")
    return c


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/contribuyentes/{contrib_id}/documentos/upload")
async def upload_documentos(
    contrib_id: str,
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    contrib = _get_contribuyente_or_404(contrib_id, user["org_id"])
    año = contrib["año_gravable"]

    if not files:
        raise HTTPException(400, "Adjunta al menos un archivo")

    job_id = str(uuid.uuid4())
    doc_records: list[dict] = []

    for f in files:
        content_type = f.content_type or "application/octet-stream"
        if content_type not in _ALLOWED_TYPES:
            raise HTTPException(
                415,
                f"Tipo no soportado: {f.filename} ({content_type}). "
                "Permitidos: PDF, JPG, PNG, TIFF, WEBP, DOCX, XLSX.",
            )
        file_bytes = await f.read()
        if len(file_bytes) > _MAX_MB * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} supera {_MAX_MB} MB")

        doc_id = _create_doc_record(
            contrib_id=contrib_id,
            org_id=user["org_id"],
            filename=f.filename or "archivo",
            mime_type=content_type,
            size_bytes=len(file_bytes),
        )
        doc_records.append({
            "doc_id":    doc_id,
            "file_bytes": file_bytes,
            "filename":   f.filename or "archivo",
            "mime_type":  content_type,
        })

    _jobs[job_id] = {
        "status":   "processing",
        "progreso": 0,
        "total":    len(doc_records),
        "completados": 0,
    }

    _executor.submit(
        _run_upload_job,
        job_id, doc_records, contrib_id, user["org_id"], año,
    )
    return {"job_id": job_id, "total": len(doc_records)}


def _run_upload_job(
    job_id: str,
    doc_records: list[dict],
    contrib_id: str,
    org_id: str,
    año: int,
) -> None:
    from services.renta.job_processor import process_documento_job
    total = len(doc_records)
    for i, rec in enumerate(doc_records, 1):
        sub_job: dict[str, Any] = {}
        process_documento_job(
            job_id=f"{job_id}_{i}",
            doc_id=rec["doc_id"],
            file_bytes=rec["file_bytes"],
            filename=rec["filename"],
            mime_type=rec["mime_type"],
            contrib_id=contrib_id,
            org_id=org_id,
            año=año,
            in_memory_jobs=sub_job,
        )
        _jobs[job_id]["completados"] = i
        _jobs[job_id]["progreso"] = round(i / total * 100)
    _jobs[job_id]["status"] = "done"


def _create_doc_record(
    contrib_id: str,
    org_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
) -> str:
    from sqlalchemy import text
    from db.database import get_db
    doc_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            text("""
                INSERT INTO renta_documentos
                    (id, contribuyente_id, org_id, s3_key, filename, mime_type, size_bytes, estado_ocr)
                VALUES
                    (:id, :contrib_id, :org_id, :s3_key, :filename, :mime_type, :size_bytes, 'procesando')
            """),
            {
                "id":         doc_id,
                "contrib_id": contrib_id,
                "org_id":     org_id,
                "s3_key":     f"pending/{doc_id}",
                "filename":   filename,
                "mime_type":  mime_type,
                "size_bytes": size_bytes,
            },
        )
    return doc_id


# ─── Job status ──────────────────────────────────────────────────────────────

@router.get("/contribuyentes/{contrib_id}/documentos/jobs/{job_id}")
async def job_status(
    contrib_id: str,
    job_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    return job


# ─── List documentos ─────────────────────────────────────────────────────────

@router.get("/contribuyentes/{contrib_id}/documentos")
async def list_documentos(
    contrib_id: str,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    _get_contribuyente_or_404(contrib_id, user["org_id"])
    from db.database_renta import get_documentos
    docs = get_documentos(contrib_id, user["org_id"])
    # Remove texto_ocr from list (too heavy)
    return [{k: v for k, v in d.items() if k != "texto_ocr"} for d in docs]


# ─── Preview (proxy via API — no signed URLs needed) ─────────────────────────

@router.get("/contribuyentes/{contrib_id}/documentos/{doc_id}/preview")
async def preview_documento(
    contrib_id: str,
    doc_id: str,
    user: dict = Depends(get_current_user),
) -> Response:
    _get_contribuyente_or_404(contrib_id, user["org_id"])
    from sqlalchemy import text
    from db.database import get_db

    with get_db() as db:
        row = db.execute(
            text("SELECT s3_key, filename, mime_type FROM renta_documentos WHERE id = :id AND org_id = :org_id"),
            {"id": doc_id, "org_id": user["org_id"]},
        ).fetchone()
    if not row:
        raise HTTPException(404, "Documento no encontrado")

    gcs_key: str = row[0]
    filename: str = row[1]
    mime_type: str = row[2] or "application/octet-stream"

    if gcs_key.startswith("pending/"):
        raise HTTPException(409, "Documento aún en procesamiento")

    try:
        from google.cloud import storage
        path = gcs_key.removeprefix("gs://taxops-docs/")
        client = storage.Client()
        blob = client.bucket("taxops-docs").blob(path)
        content = blob.download_as_bytes()
        return Response(
            content=content,
            media_type=mime_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(502, f"Error descargando de GCS: {exc}")


# ─── Delete ──────────────────────────────────────────────────────────────────

@router.delete("/contribuyentes/{contrib_id}/documentos/{doc_id}", status_code=204)
async def delete_documento(
    contrib_id: str,
    doc_id: str,
    user: dict = Depends(require_admin),
) -> None:
    _get_contribuyente_or_404(contrib_id, user["org_id"])
    from sqlalchemy import text
    from db.database import get_db
    from services.renta.storage import delete_from_gcs

    with get_db() as db:
        row = db.execute(
            text("SELECT s3_key FROM renta_documentos WHERE id = :id AND org_id = :org_id"),
            {"id": doc_id, "org_id": user["org_id"]},
        ).fetchone()
        if not row:
            raise HTTPException(404, "Documento no encontrado")
        gcs_key = row[0]
        db.execute(text("DELETE FROM renta_documentos WHERE id = :id"), {"id": doc_id})

    if gcs_key and not gcs_key.startswith("pending/"):
        delete_from_gcs(gcs_key)
