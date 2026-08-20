"""services/exogenas/job_processor.py — Orquesta descarga S3 → extracción →
agregación → resultado en S3.

Corre en el worker Lambda (disparado por SQS, ver api/worker_handler.py). A
diferencia de services/renta/job_processor.py (que trabaja directo sobre bytes
vía ocr_agent.extract_text), exogenas.extractor.extract_many() necesita un path
de filesystem — se escribe cada descarga a un tmp file antes de extraer (mismo
patrón que usaba el endpoint SSE que este código reemplaza,
api/routers/exogenas.py::stream_job).

El resultado combinado (df_1003 + df_detalle) se sube como JSON a
uploads/results/exogenas/{job_id}.json en vez de guardarse en el item de
DynamoDB, porque puede exceder el límite de 400KB por item (spec §4.1).
"""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

import boto3

from api.core import job_store
from api.core.config import get_settings

log = logging.getLogger("taxops.exogenas")


def _extract_from_path(path: Path) -> list[dict]:
    """Wrapper delgado sobre extract_many — separado para poder mockearlo en
    tests sin depender de pdfplumber/pytesseract reales."""
    from exogenas.extractor import extract_many
    return extract_many(path)


def process_exogenas_job(job_id: str, org_id: str, s3_keys: list[str]) -> None:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    job_store.put_job(job_id, "processing", {"progreso": 0, "total": len(s3_keys), "completados": 0})

    tmpdir = tempfile.mkdtemp()
    all_rows: list[dict] = []
    errors = 0
    warnings: list[str] = []

    try:
        for i, s3_key in enumerate(s3_keys, 1):
            filename = Path(s3_key).name
            local_path = Path(tmpdir) / filename

            try:
                obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=s3_key)
                local_path.write_bytes(obj["Body"].read())
                rows = _extract_from_path(local_path)
            except Exception as exc:
                errors += 1
                warnings.append(f"❌ {filename}: {exc}")
                rows = []

            for row in rows:
                row["_archivo"] = filename
                if row.get("error"):
                    errors += 1
                    warnings.append(f"⚠️ {filename}: {row['error']}")
                all_rows.append(row)

            job_store.put_job(job_id, "processing", {
                "progreso": round(i / len(s3_keys) * 100),
                "total": len(s3_keys),
                "completados": i,
            })

        result = _build_result(all_rows, errors, warnings, org_id)
        result_s3_key = f"uploads/results/exogenas/{job_id}.json"
        s3.put_object(
            Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
            Key=result_s3_key,
            Body=json.dumps(result, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

        job_store.put_job(job_id, "done", {
            "progreso": 100,
            "total": len(s3_keys),
            "completados": len(s3_keys),
            "result_s3_key": result_s3_key,
        })

    except Exception as exc:
        log.error("process_exogenas_job failed for %s: %s", job_id, exc, exc_info=True)
        job_store.put_job(job_id, "error", {"error": str(exc)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_result(all_rows: list[dict], errors: int, warnings: list[str], org_id: str) -> dict:
    """Agrega las filas crudas al Formato 1003 — misma lógica que vivía inline
    en el endpoint SSE que este código reemplaza (api/routers/exogenas.py, el
    `stream_job` viejo)."""
    import pandas as pd

    total = len({r["_archivo"] for r in all_rows}) if all_rows else 0

    if not all_rows:
        return {
            "total_archivos": total, "procesados": total - errors, "errores": errors,
            "ica_excluidos": 0, "advertencias": warnings, "df_detalle": [], "df_1003": [],
        }

    from exogenas.municipios import buscar_municipio
    from services.processor_exogenas import _agregar

    df = pd.DataFrame(all_rows)

    def _resolve_mpio(ciudad: str) -> pd.Series:
        dpto, mpio = buscar_municipio(str(ciudad))
        return pd.Series({"cod_dpto": dpto, "cod_mpio": mpio})

    mpio_df = df["ciudad_retencion"].apply(_resolve_mpio)
    df["cod_dpto"] = mpio_df["cod_dpto"]
    df["cod_mpio"] = mpio_df["cod_mpio"]

    ica_count = int((df["concepto"] == "ICA").sum())

    # Filas incompletas (sin NIT/concepto/base, salvo ICA que se excluye del
    # 1003 aparte) no entran en df_1003 pero sí se advierten — preservado tal
    # cual del endpoint SSE viejo, ver plan Task 5 "Nota de alcance".
    mask_incompletas = (
        (df["concepto"].fillna("").astype(str).str.strip() == "") |
        (df["nit"].fillna("").astype(str).str.strip() == "") |
        (df["base"].fillna(0) <= 0)
    ) & (df["concepto"].fillna("") != "ICA")
    df_incompletas = df[mask_incompletas]
    if not df_incompletas.empty:
        for archivo, grupo in df_incompletas.groupby("_archivo"):
            for _, fila in grupo.iterrows():
                motivos = []
                if not str(fila.get("nit", "")).strip():
                    motivos.append("NIT vacío")
                if not str(fila.get("concepto", "")).strip():
                    motivos.append("concepto vacío")
                if not (fila.get("base") or 0) > 0:
                    motivos.append("base=0")
                warnings.append(
                    f"⚠️ {archivo}: fila excluida del Formato 1003 "
                    f"({', '.join(motivos)}) — "
                    f"retenedor: '{fila.get('razon_social', '') or fila.get('nit', '') or '?'}'"
                )

    df_1003 = _agregar(df)

    sin_mpio = df_1003[df_1003["cod_dpto"] == ""]
    for _, row in sin_mpio.iterrows():
        warnings.append(
            f"ℹ️ No se encontró código DIAN para ciudad '{row.get('ciudad_retencion', '')}' "
            f"({row.get('razon_social', '')}). Completa manualmente."
        )

    if org_id and not df_1003.empty:
        try:
            from db.database import db_available, insert_exogenas_batch
            if db_available():
                insert_exogenas_batch(df_1003, org_id)
        except Exception:
            pass

    return {
        "total_archivos": total,
        "procesados": total - errors,
        "errores": errors,
        "ica_excluidos": ica_count,
        "advertencias": warnings,
        "df_detalle": df.fillna("").to_dict(orient="records"),
        "df_1003": df_1003.fillna("").to_dict(orient="records"),
    }
