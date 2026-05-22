"""Invoices router — process, list, export."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from dependencies import get_current_user
from schemas import ExportInvoicesRequest, ProcessInvoicesResponse

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/process", response_model=ProcessInvoicesResponse)
async def process_invoices(
    files: list[UploadFile] = File(...),
    ingresos_json: str = Form(default="[]"),
    user: dict = Depends(get_current_user),
) -> ProcessInvoicesResponse:
    try:
        ingresos_list = json.loads(ingresos_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="ingresos_json inválido")

    ingresos_gravados = {i["periodo"]: float(i.get("gravados", 0)) for i in ingresos_list}
    ingresos_excluidos = {i["periodo"]: float(i.get("excluidos", 0)) for i in ingresos_list}

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_paths: list[Path] = []
        for upload in files:
            safe_name = Path(upload.filename or "archivo").name
            dest = Path(tmpdir) / safe_name
            dest.write_bytes(await upload.read())
            tmp_paths.append(dest)

        try:
            from services.processor import procesar

            resultado = procesar(
                archivos=tmp_paths,
                ingresos_gravados=ingresos_gravados or None,
                ingresos_excluidos=ingresos_excluidos or None,
                org_id=user["org_id"],
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error en procesamiento: {exc}")

    return ProcessInvoicesResponse(
        total_archivos=resultado.total_archivos,
        procesados=resultado.total_archivos - resultado.errores,
        errores=resultado.errores,
        db_nuevas=resultado.db_nuevas,
        db_duplicadas=resultado.db_duplicadas,
        df_base=resultado.df_base.fillna("").to_dict(orient="records"),
        df_val=resultado.df_val.fillna("").to_dict(orient="records"),
        df_pror=resultado.df_pror.fillna("").to_dict(orient="records"),
    )


@router.post("/export")
async def export_excel(
    body: ExportInvoicesRequest,
    user: dict = Depends(get_current_user),
) -> Response:
    import pandas as pd

    df_base = pd.DataFrame(body.df_base)
    df_val = pd.DataFrame(body.df_val)
    df_pror = pd.DataFrame(body.df_pror)

    tmp = Path(tempfile.mktemp(suffix=".xlsx"))
    try:
        from pipeline.excel_writer import write_excel

        write_excel(df_base, df_val, df_pror, tmp)
        content = tmp.read_bytes()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar Excel: {exc}")
    finally:
        tmp.unlink(missing_ok=True)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=taxops_facturas.xlsx"},
    )


@router.get("/")
async def list_invoices(
    periodo: str | None = None,
    nit_emisor: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user),
) -> dict:
    from db.database import db_available, get_db

    if not db_available():
        return {"invoices": [], "total": 0, "db_available": False}

    from sqlalchemy import text

    filters = ["org_id = :org_id"]
    params: dict = {"org_id": user["org_id"], "limit": limit, "offset": offset}

    if periodo:
        filters.append("periodo = :periodo")
        params["periodo"] = periodo
    if nit_emisor:
        filters.append("nit_emisor = :nit_emisor")
        params["nit_emisor"] = nit_emisor

    where = " AND ".join(filters)
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    f"SELECT * FROM invoices WHERE {where} "
                    "ORDER BY procesado_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().fetchall()
            total = db.execute(
                text(f"SELECT COUNT(*) FROM invoices WHERE {where}"),
                count_params,
            ).scalar()
    except Exception:
        return {"invoices": [], "total": 0, "db_available": False}

    return {
        "invoices": [dict(r) for r in rows],
        "total": total,
        "db_available": True,
    }
