"""services/renta/job_processor.py — Orchestrates upload → OCR → classify → DB."""
from __future__ import annotations

import json
import uuid
from datetime import datetime


def process_documento_job(
    job_id: str,
    doc_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    contrib_id: str,
    org_id: str,
    año: int,
    in_memory_jobs: dict,
) -> None:
    """
    Runs in a background thread:
      1. Upload to GCS
      2. OCR → text
      3. Classify → category + fields
      4. UPDATE renta_documentos in DB
      5. UPDATE in-memory job status
    """
    import logging
    log = logging.getLogger("taxops.renta")

    def _update_job(progreso: int, **kwargs):
        if job_id in in_memory_jobs:
            in_memory_jobs[job_id].update({"progreso": progreso, **kwargs})

    try:
        # 1. Upload to GCS — non-fatal: OCR/classify still run if GCS fails
        from services.renta.storage import upload_to_gcs
        gcs_key = f"pending/{doc_id}"
        try:
            _update_job(10, status="uploading")
            gcs_key = upload_to_gcs(
                file_bytes=file_bytes,
                org_id=org_id,
                contrib_id=contrib_id,
                año=año,
                filename=filename,
                content_type=mime_type or "application/octet-stream",
            )
        except Exception as gcs_exc:
            log.warning("GCS upload failed for %s: %s — continuing without storage", filename, gcs_exc)

        _update_job(30, status="ocr")

        # 2. OCR
        from services.renta.ocr_agent import extract_text
        text = extract_text(file_bytes, filename, mime_type)
        log.info("OCR '%s': %d chars extracted", filename, len(text))
        _update_job(60, status="classifying")

        # 3. Classify
        from services.renta.classifier_agent import classify_document
        classification = classify_document(text, filename)
        _update_job(85, status="saving")

        # 4. Update DB
        _update_doc_in_db(
            doc_id=doc_id,
            gcs_key=gcs_key,
            texto_ocr=text,
            classification=classification,
        )

        _update_job(
            100,
            status="done",
            categoria=classification["categoria"],
            confianza=classification["confianza"],
        )

    except Exception as exc:
        log.error("Job %s failed for doc %s: %s", job_id, doc_id, exc, exc_info=True)
        _update_job(0, status="error", error=str(exc))
        _mark_doc_error(doc_id, str(exc))


def _update_doc_in_db(
    doc_id: str,
    gcs_key: str,
    texto_ocr: str,
    classification: dict,
) -> None:
    from sqlalchemy import text
    from db.database import get_db
    with get_db() as db:
        db.execute(
            text("""
                UPDATE renta_documentos SET
                    s3_key                  = :gcs_key,
                    texto_ocr               = :texto_ocr,
                    categoria               = :categoria,
                    carpeta_virtual         = :carpeta_virtual,
                    confianza_clasificacion = :confianza,
                    datos_extraidos         = CAST(:datos_extraidos AS jsonb),
                    estado_ocr              = 'completado',
                    estado_validacion       = 'pendiente'
                WHERE id = :doc_id
            """),
            {
                "gcs_key":        gcs_key,
                "texto_ocr":      texto_ocr[:50_000],  # cap at 50k chars
                "categoria":      classification["categoria"],
                "carpeta_virtual": classification["carpeta_virtual"],
                "confianza":      classification["confianza"],
                "datos_extraidos": json.dumps(classification["datos_extraidos"]),
                "doc_id":         doc_id,
            },
        )


def _mark_doc_error(doc_id: str, error: str) -> None:
    try:
        from sqlalchemy import text
        from db.database import get_db
        with get_db() as db:
            db.execute(
                text("""
                    UPDATE renta_documentos
                    SET estado_ocr = 'error',
                        datos_extraidos = CAST(:err AS jsonb)
                    WHERE id = :id
                """),
                {"id": doc_id, "err": json.dumps({"_error": error[:500]})},
            )
    except Exception:
        pass
