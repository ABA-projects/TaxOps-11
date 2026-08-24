"""Calendario Tributario DIAN — router.

GET    /calendario/eventos          → lista de eventos (usuario autenticado)
PUT    /calendario/eventos          → reemplaza la lista completa (superadmin)
POST   /calendario/eventos          → agrega un evento (superadmin)
DELETE /calendario/eventos/{id}     → elimina un evento (superadmin)

Persistencia: S3 (config/calendario_2026.json, fuera del prefijo "uploads/" — no cae en el
lifecycle de 3 días). Antes usaba un archivo local (api/data/calendario_2026.json) — eso
funcionaba en Cloud Run (proceso continuo) pero no sobrevive en Lambda: cada execution
environment arranca desde la imagen del container, así que un PUT se perdía en el siguiente
cold start.
"""
from __future__ import annotations

import json

import boto3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import get_settings
from dependencies import get_current_user, require_superadmin

router = APIRouter(prefix="/calendario", tags=["Calendario"])

_S3_KEY = "config/calendario_2026.json"


def _load() -> list[dict]:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    try:
        obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=_S3_KEY)
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        return []


def _save(eventos: list[dict]) -> None:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    s3.put_object(
        Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
        Key=_S3_KEY,
        Body=json.dumps(eventos, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


class EventoCalendario(BaseModel):
    id: str
    fecha: str            # YYYY-MM-DD
    titulo: str
    descripcion: str
    tipo: str             # retencion | iva | renta | exogenas | ica | patrimonio | otro
    urgencia: str         # critica | alta | media | baja
    articulo: str | None = None
    link: str | None = None
    alertaDias: int | None = None


@router.get("/eventos", response_model=list[EventoCalendario])
async def get_eventos(current_user=Depends(get_current_user)):
    """Devuelve todos los eventos del calendario tributario activo."""
    return _load()


@router.put("/eventos", response_model=list[EventoCalendario])
async def replace_eventos(
    eventos: list[EventoCalendario],
    current_user=Depends(require_superadmin),
):
    """Reemplaza la lista completa de eventos. Solo superadmin."""
    data = [e.model_dump() for e in eventos]
    data.sort(key=lambda e: e["fecha"])
    _save(data)
    return data


@router.post("/eventos", response_model=EventoCalendario, status_code=201)
async def add_evento(
    evento: EventoCalendario,
    current_user=Depends(require_superadmin),
):
    """Agrega un evento individual. Solo superadmin."""
    eventos = _load()
    if any(e["id"] == evento.id for e in eventos):
        raise HTTPException(status_code=409, detail="Ya existe un evento con ese id")
    eventos.append(evento.model_dump())
    eventos.sort(key=lambda e: e["fecha"])
    _save(eventos)
    return evento


@router.delete("/eventos/{evento_id}", status_code=204)
async def delete_evento(
    evento_id: str,
    current_user=Depends(require_superadmin),
):
    """Elimina un evento por id. Solo superadmin."""
    eventos = _load()
    new = [e for e in eventos if e["id"] != evento_id]
    if len(new) == len(eventos):
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    _save(new)
