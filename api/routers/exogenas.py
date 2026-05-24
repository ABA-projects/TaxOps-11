"""Exogenas router — process, list, export."""
from __future__ import annotations

import shutil
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from dependencies import get_current_user
from schemas import ExportExogenasRequest, ProcessExogenasResponse

router = APIRouter(prefix="/exogenas", tags=["Exógenas"])

# In-memory job store — keyed by job_id, lives for the server instance lifetime
_jobs: dict[str, dict[str, Any]] = {}
# Limit concurrent OCR jobs to avoid OOM on free tier (extras queue automatically)
_executor = ThreadPoolExecutor(max_workers=2)


def _run_job(job_id: str, paths: list[Path], org_id: str, tmpdir: str) -> None:
    """Runs in thread pool. Writes final state to _jobs[job_id]."""
    try:
        from services.processor_exogenas import procesar_exogenas

        total = len(paths)

        def on_progress(i: int, _total: int, name: str) -> None:
            _jobs[job_id]["progress"] = round(i / _total * 100) if _total else 0
            _jobs[job_id]["current_file"] = name

        resultado = procesar_exogenas(paths=paths, on_progress=on_progress, org_id=org_id)

        _jobs[job_id] = {
            "status": "done",
            "progress": 100,
            "current_file": "",
            "result": {
                "total_archivos": resultado.total_archivos,
                "procesados": resultado.total_archivos - resultado.errores,
                "errores": resultado.errores,
                "ica_excluidos": resultado.ica_excluidos,
                "advertencias": resultado.advertencias,
                "df_detalle": resultado.df_detalle.fillna("").to_dict(orient="records"),
                "df_1003": resultado.df_1003.fillna("").to_dict(orient="records"),
            },
        }
    except Exception as exc:
        _jobs[job_id] = {"status": "error", "error": str(exc), "progress": 0}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/process")
async def process_exogenas(
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    _ALLOWED = {
        ".pdf", ".docx", ".doc",
        ".xlsx", ".xls",
        ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp",
    }

    # Persist files in a temp dir that outlives this request (background task needs them)
    tmpdir = tempfile.mkdtemp()
    tmp_paths: list[Path] = []

    try:
        for upload in files:
            safe_name = Path(upload.filename or "archivo").name
            if Path(safe_name).suffix.lower() not in _ALLOWED:
                raise HTTPException(
                    status_code=415,
                    detail=f"Formato no soportado: {safe_name}. "
                           "Soportados: PDF, DOCX, XLSX, JPG, PNG.",
                )
            dest = Path(tmpdir) / safe_name
            with dest.open("wb") as fout:
                while chunk := await upload.read(256 * 1024):
                    fout.write(chunk)
            tmp_paths.append(dest)
    except HTTPException:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Error leyendo archivos: {exc}")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "progress": 0, "current_file": ""}

    _executor.submit(_run_job, job_id, tmp_paths, user["org_id"], tmpdir)

    return {"job_id": job_id, "status": "processing", "total": len(tmp_paths)}


@router.get("/status/{job_id}")
async def job_status(
    job_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado o servidor reiniciado")
    return _jobs[job_id]


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
