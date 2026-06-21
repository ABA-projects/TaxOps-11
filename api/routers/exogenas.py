"""Exogenas router — SSE streaming processor, list, export."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from dependencies import get_current_user
from schemas import ExportExogenasRequest

router = APIRouter(prefix="/exogenas", tags=["Exógenas"])

# Temporary store: job_id → (paths, org_id, tmpdir)
# Holds files only for the brief gap between POST and GET stream.
_pending: dict[str, tuple[list[Path], str, str]] = {}


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
    _pending[job_id] = (tmp_paths, user["org_id"], tmpdir)

    return {"job_id": job_id, "total": len(tmp_paths)}


def _sse(data: Any) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


@router.get("/stream/{job_id}")
async def stream_job(job_id: str) -> StreamingResponse:
    """SSE endpoint: keeps Cloud Run request alive while OCR runs file by file."""
    if job_id not in _pending:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    paths, org_id, tmpdir = _pending.pop(job_id)

    async def generate():
        try:
            import gc
            import time

            from exogenas.extractor import extract_many
            from exogenas.municipios import buscar_municipio
            from services.processor_exogenas import _agregar
        except Exception as exc:
            yield _sse({"type": "error", "error": f"Error de inicialización: {exc}"})
            return

        total = len(paths)
        all_rows: list[dict] = []
        errors = 0
        warnings: list[str] = []
        loop = asyncio.get_running_loop()

        try:
            for i, p in enumerate(paths):
                yield _sse({"type": "progress", "progress": round(i / total * 100), "current": p.name})

                t0 = time.time()
                fut = loop.run_in_executor(None, extract_many, p)
                rows: list[dict] = []
                try:
                    # Keepalive SSE comment cada 5 s mientras OCR corre;
                    # límite global 90 s por archivo.
                    deadline = time.monotonic() + 90
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            fut.cancel()
                            raise asyncio.TimeoutError()
                        try:
                            rows = await asyncio.wait_for(
                                asyncio.shield(fut), timeout=min(5.0, remaining)
                            )
                            break
                        except asyncio.TimeoutError:
                            if time.monotonic() >= deadline:
                                fut.cancel()
                                raise
                            yield ":\n\n"  # SSE comment — keepalive, ignorado por el cliente
                    elapsed = time.time() - t0
                    for row in rows:
                        row["_archivo"] = p.name
                        if row.get("error"):
                            errors += 1
                            warnings.append(f"⚠️ {p.name}: {row['error']}")
                        all_rows.append(row)
                    if elapsed > 3:
                        fuente = rows[0].get("fuente", "?") if rows else "?"
                        escaneado = rows[0].get("es_escaneado", False) if rows else False
                        warnings.append(
                            f"⏱️ {p.name}: {elapsed:.1f}s "
                            f"[{'OCR' if escaneado or fuente == 'IMAGEN' else fuente}]"
                        )
                except asyncio.TimeoutError:
                    errors += 1
                    warnings.append(f"⏱️ {p.name}: timeout >90s — archivo omitido")
                except Exception as e:
                    errors += 1
                    warnings.append(f"❌ {p.name}: {e}")

                gc.collect()

            # ── Post-processing ────────────────────────────────────────────
            import pandas as pd

            if not all_rows:
                yield _sse({
                    "type": "done",
                    "result": {
                        "total_archivos": total,
                        "procesados": total - errors,
                        "errores": errors,
                        "ica_excluidos": 0,
                        "advertencias": warnings,
                        "df_detalle": [],
                        "df_1003": [],
                    },
                })
                return

            df = pd.DataFrame(all_rows)

            def _resolve_mpio(ciudad: str) -> pd.Series:
                dpto, mpio = buscar_municipio(str(ciudad))
                return pd.Series({"cod_dpto": dpto, "cod_mpio": mpio})

            mpio_df = df["ciudad_retencion"].apply(_resolve_mpio)
            df["cod_dpto"] = mpio_df["cod_dpto"]
            df["cod_mpio"] = mpio_df["cod_mpio"]

            ica_count = int((df["concepto"] == "ICA").sum())

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
                            f"retenedor: '{fila.get('razon_social','') or fila.get('nit','') or '?'}'"
                        )

            df_1003 = _agregar(df)

            sin_mpio = df_1003[df_1003["cod_dpto"] == ""]
            for _, row in sin_mpio.iterrows():
                warnings.append(
                    f"ℹ️ No se encontró código DIAN para ciudad '{row.get('ciudad_retencion','')}' "
                    f"({row.get('razon_social','')}). Completa manualmente."
                )

            if org_id and not df_1003.empty:
                try:
                    from db.database import db_available, insert_exogenas_batch
                    if db_available():
                        insert_exogenas_batch(df_1003, org_id)
                except Exception:
                    pass

            yield _sse({
                "type": "done",
                "result": {
                    "total_archivos": total,
                    "procesados": total - errors,
                    "errores": errors,
                    "ica_excluidos": ica_count,
                    "advertencias": warnings,
                    "df_detalle": df.fillna("").to_dict(orient="records"),
                    "df_1003": df_1003.fillna("").to_dict(orient="records"),
                },
            })

        except Exception as exc:
            yield _sse({"type": "error", "error": str(exc)})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
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
