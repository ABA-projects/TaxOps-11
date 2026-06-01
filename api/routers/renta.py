"""Renta router — CRUD contribuyentes + declaraciones."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_current_user, require_admin
from schemas_renta import (
    ContribuyenteCreate,
    ContribuyenteOut,
    ContribuyenteUpdate,
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


# ─── Reglas tributarias ───────────────────────────────────────────────────────

@router.get("/reglas/{año_gravable}")
async def get_reglas(
    año_gravable: int,
    user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    from db.database_renta import get_reglas_tributarias
    return get_reglas_tributarias(año_gravable)
