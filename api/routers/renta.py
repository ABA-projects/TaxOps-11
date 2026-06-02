"""Renta router — CRUD contribuyentes + declaraciones."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from dependencies import get_current_user, require_admin
from schemas_renta import (
    ContribuyenteCreate,
    ContribuyenteOut,
    ContribuyenteUpdate,
    DatosTributariosIn,
    DeclaracionOut,
    DocumentoOut,
    RiesgoOut,
)

router = APIRouter(prefix="/renta", tags=["Renta"])


# ─── Contribuyentes ───────────────────────────────────────────────────────────

@router.get("/contribuyentes", response_model=list[ContribuyenteOut])
async def list_contribuyentes(
    año_gravable: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_contribuyentes
    return get_contribuyentes(user["org_id"], año_gravable=año_gravable, estado=estado)


@router.post("/contribuyentes", response_model=ContribuyenteOut, status_code=201)
async def create_contribuyente(
    body: ContribuyenteCreate,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import insert_contribuyente
    try:
        return insert_contribuyente(body.model_dump(), user["org_id"])
    except Exception as e:
        if "uq_contribuyente_año" in str(e):
            raise HTTPException(409, "Ya existe un contribuyente con ese documento y año gravable")
        raise HTTPException(500, str(e))


@router.get("/contribuyentes/{id}", response_model=ContribuyenteOut)
async def get_contribuyente_endpoint(
    id: UUID,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_contribuyente
    row = get_contribuyente(str(id), user["org_id"])
    if not row:
        raise HTTPException(404, "Contribuyente no encontrado")
    return row


@router.put("/contribuyentes/{id}", response_model=ContribuyenteOut)
async def update_contribuyente_endpoint(
    id: UUID,
    body: ContribuyenteUpdate,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import update_contribuyente, get_contribuyente
    updated = update_contribuyente(str(id), user["org_id"], body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, "Contribuyente no encontrado")
    return get_contribuyente(str(id), user["org_id"])


@router.delete("/contribuyentes/{id}", status_code=204)
async def delete_contribuyente_endpoint(
    id: UUID,
    user: dict = Depends(require_admin),
):
    from db.database_renta import delete_contribuyente
    deleted = delete_contribuyente(str(id), user["org_id"])
    if not deleted:
        raise HTTPException(404, "Contribuyente no encontrado")


# ─── Info / riesgo ────────────────────────────────────────────────────────────

@router.get("/contribuyentes/{id}/info", response_model=RiesgoOut)
async def get_contribuyente_info(
    id: UUID,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_contribuyente_info
    info = get_contribuyente_info(str(id), user["org_id"])
    if not info:
        raise HTTPException(404, "Contribuyente no encontrado")
    return info


# ─── Documentos ───────────────────────────────────────────────────────────────

@router.get("/contribuyentes/{id}/documentos", response_model=list[DocumentoOut])
async def list_documentos(
    id: UUID,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_documentos
    return get_documentos(str(id), user["org_id"])


# ─── Declaraciones ────────────────────────────────────────────────────────────

@router.get("/contribuyentes/{id}/declaracion", response_model=Optional[DeclaracionOut])
async def get_declaracion(
    id: UUID,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_declaracion
    return get_declaracion(str(id), user["org_id"])


# ─── Calcular declaración ────────────────────────────────────────────────────

@router.post("/contribuyentes/{id}/declaracion/calcular", response_model=DeclaracionOut)
async def calcular_declaracion_endpoint(
    id: UUID,
    body: dict = Body(default={}),
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_contribuyente, upsert_declaracion
    from services.renta.tax_engine import calcular_declaracion

    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")
    try:
        ajuste_manual = body.get("ajuste_manual") if body else None
        data = calcular_declaracion(str(id), contrib["año_gravable"], ajuste_manual)
        return upsert_declaracion(str(id), contrib["año_gravable"], data)
    except Exception as e:
        raise HTTPException(500, f"Error calculando declaración: {e}")


# ─── Guardar datos tributarios (PATCH) ───────────────────────────────────────

@router.patch("/contribuyentes/{id}/declaracion/datos", response_model=DeclaracionOut)
async def patch_datos_declaracion_endpoint(
    id: UUID,
    body: DatosTributariosIn,
    user: dict = Depends(get_current_user),
):
    from db.database_renta import get_contribuyente, patch_datos_declaracion
    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")
    data = body.model_dump(exclude_none=True)
    try:
        return patch_datos_declaracion(str(id), contrib["año_gravable"], data)
    except Exception as e:
        raise HTTPException(500, f"Error guardando datos: {e}")


# ─── Descargar Formulario 210 PDF ────────────────────────────────────────────

@router.get("/contribuyentes/{id}/declaracion/pdf")
async def descargar_formulario_210(id: UUID, user: dict = Depends(get_current_user)):
    from db.database_renta import get_contribuyente, get_declaracion
    from services.renta.pdf_formulario210 import generar_pdf
    from fastapi.responses import Response

    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")

    decl = get_declaracion(str(id), user["org_id"])
    if not decl:
        raise HTTPException(404, "No existe declaración calculada para este contribuyente")

    try:
        pdf_bytes = generar_pdf(decl, contrib)
    except Exception as e:
        raise HTTPException(500, f"Error generando PDF: {e}")

    filename = f"Formulario210_{contrib['año_gravable']}_{contrib['numero_doc']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/contribuyentes/{id}/declaracion/excel")
async def descargar_formulario_210_excel(id: UUID, user: dict = Depends(get_current_user)):
    from db.database_renta import get_contribuyente, get_declaracion
    from services.renta.excel_formulario210 import generar_excel
    from fastapi.responses import Response

    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")

    decl = get_declaracion(str(id), user["org_id"])
    if not decl:
        raise HTTPException(404, "No existe declaración calculada para este contribuyente")

    try:
        xls_bytes = generar_excel(decl, contrib)
    except Exception as e:
        raise HTTPException(500, f"Error generando Excel: {e}")

    filename = f"Formulario210_{contrib['año_gravable']}_{contrib['numero_doc']}.xlsx"
    return Response(
        content=xls_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Reglas tributarias ───────────────────────────────────────────────────────

@router.get("/reglas/{año_gravable}")
async def get_reglas(
    año_gravable: int,
    user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    from db.database_renta import get_reglas_tributarias
    return get_reglas_tributarias(año_gravable)
