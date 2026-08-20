"""services/exogenas/job_processor.py — Orquesta descarga S3 → OCR/extracción →
agregación → resultado en S3, para el worker SQS.

Espejo de services/renta/job_processor.py, pero con dos diferencias por la
naturaleza de Exógenas:
  1. Es un job por LOTE (varios s3_keys en una sola invocación), no un job por
     documento — Exógenas siempre se procesó así (ver services/processor_exogenas.py).
  2. exogenas.extractor.extract_many() requiere una ruta de archivo real, no
     bytes — cada archivo descargado de S3 se escribe primero a /tmp.

El resultado combinado (df_1003 + df_detalle) se sube como JSON a
uploads/results/exogenas/{job_id}.json en vez de guardarse en el item de
DynamoDB, porque puede exceder el límite de 400KB por item de DynamoDB
(ver spec §4.1).
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import boto3

from api.core import job_store
from api.core.config import get_settings

log = logging.getLogger("taxops.exogenas")


def _extract_from_path(path: Path) -> list[dict]:
    """Wrapper alrededor de exogenas.extractor.extract_many — punto único de
    monkeypatch en tests, evita acoplar los tests a pdfplumber/tesseract real."""
    from exogenas.extractor import extract_many
    return extract_many(path)


def process_exogenas_job(job_id: str, org_id: str, s3_keys: list[str]) -> None:
    """
    Runs in the SQS worker:
      1. Descarga cada s3_key a un archivo temporal
      2. Extrae filas por archivo (un archivo con error no aborta el lote)
      3. Agrega filas → df_1003 (services.processor_exogenas._agregar)
      4. Sube el resultado combinado (df_1003 + df_detalle) a S3 como JSON
      5. Marca el job como "done" con result_s3_key (sin embeber el resultado
         en DynamoDB — puede superar 400KB)
    """
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    def _update_job(progreso: int, **kwargs):
        job_store.put_job(job_id, kwargs.get("status", "processing"), {"progreso": progreso, **kwargs})

    filas: list[dict] = []
    errores = 0
    total = len(s3_keys)

    _update_job(0, status="processing", total=total, completados=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, s3_key in enumerate(s3_keys, 1):
            filename = Path(s3_key).name
            dest = Path(tmpdir) / filename
            try:
                obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=s3_key)
                dest.write_bytes(obj["Body"].read())
                rows = _extract_from_path(dest)
            except Exception as exc:
                log.error(
                    "process_exogenas_job: fallo procesando %s (job %s): %s",
                    s3_key, job_id, exc, exc_info=True,
                )
                errores += 1
                _update_job(round(i / total * 100), status="processing", total=total, completados=i)
                continue

            for row in rows:
                row["_archivo"] = filename
                if row.get("error"):
                    errores += 1
            filas.extend(rows)
            _update_job(round(i / total * 100), status="processing", total=total, completados=i)

    import pandas as pd

    from services.processor_exogenas import _agregar

    df_detalle = pd.DataFrame(filas)
    df_1003 = _agregar(df_detalle) if not df_detalle.empty else pd.DataFrame()

    result = {
        "df_detalle": df_detalle.fillna("").to_dict(orient="records"),
        "df_1003": df_1003.fillna("").to_dict(orient="records"),
        "total_archivos": total,
        "errores": errores,
    }

    result_s3_key = f"uploads/results/exogenas/{job_id}.json"
    s3.put_object(
        Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
        Key=result_s3_key,
        Body=json.dumps(result, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    _update_job(
        100,
        status="done",
        total=total,
        completados=total,
        errores=errores,
        result_s3_key=result_s3_key,
    )
