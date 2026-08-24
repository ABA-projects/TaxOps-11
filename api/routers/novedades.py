"""Novedades router — feed de cambios DIAN/NIIF generado por los agentes contables
(agents/contabilidad/dian-monitor, monitor-niif). Ver docs/superpowers/specs/
2026-08-23-agentes-contables-integracion-design.md."""
from __future__ import annotations

from dependencies import get_current_user
from fastapi import APIRouter, Depends
from schemas import NovedadResponse

router = APIRouter(prefix="/novedades", tags=["Novedades"])


@router.get("/", response_model=list[NovedadResponse])
async def list_novedades(
    tipo: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
) -> list[NovedadResponse]:
    from db.database import db_available, get_db

    if not db_available():
        return []

    from sqlalchemy import text

    filters = []
    params: dict = {"limit": limit, "offset": offset}
    if tipo:
        filters.append("tipo = :tipo")
        params["tipo"] = tipo
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    f"SELECT id, tipo, titulo, resumen, fecha_generado FROM novedades {where} "
                    "ORDER BY fecha_generado DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().fetchall()
    except Exception:
        return []

    return [
        NovedadResponse(
            id=str(r["id"]), tipo=r["tipo"], titulo=r["titulo"],
            resumen=r["resumen"], fecha_generado=str(r["fecha_generado"]),
        )
        for r in rows
    ]
