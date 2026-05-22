"""Exogenas router — process, list, export."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from dependencies import get_current_user
from schemas import ExportExogenasRequest, ProcessExogenasResponse

router = APIRouter(prefix="/exogenas", tags=["Exógenas"])


@router.post("/process", response_model=ProcessExogenasResponse)
async def process_exogenas(
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
) -> ProcessExogenasResponse:
    _ALLOWED = {
        ".pdf", ".docx", ".doc",
        ".xlsx", ".xls",
        ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_paths: list[Path] = []
        for upload in files:
            safe_name = Path(upload.filename or "archivo").name
            if Path(safe_name).suffix.lower() not in _ALLOWED:
                raise HTTPException(
                    status_code=415,
                    detail=f"Formato no soportado: {safe_name}. "
                           "Soportados: PDF, DOCX, XLSX, JPG, PNG.",
                )
            dest = Path(tmpdir) / safe_name
            # Escribir en chunks de 256 KB — no carga el archivo completo en RAM
            with dest.open("wb") as fout:
                while chunk := await upload.read(256 * 1024):
                    fout.write(chunk)
            tmp_paths.append(dest)

        try:
            from services.processor_exogenas import procesar_exogenas

            resultado = procesar_exogenas(paths=tmp_paths, org_id=user["org_id"])
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error en procesamiento: {exc}")

    return ProcessExogenasResponse(
        total_archivos=resultado.total_archivos,
        procesados=resultado.total_archivos - resultado.errores,
        errores=resultado.errores,
        ica_excluidos=resultado.ica_excluidos,
        advertencias=resultado.advertencias,
        df_detalle=resultado.df_detalle.fillna("").to_dict(orient="records"),
        df_1003=resultado.df_1003.fillna("").to_dict(orient="records"),
    )


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
