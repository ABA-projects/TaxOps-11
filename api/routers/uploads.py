"""api/routers/uploads.py — Presigned S3 uploads compartidos entre módulos.

Genera policies de generate_presigned_post (NO generate_presigned_url/PUT — un PUT
presignado no lleva límite de tamaño real, ver docs/superpowers/specs/
2026-08-14-s3-presigned-uploads-exogenas-async-design.md §1). El navegador sube
directo a S3 con estos campos, bypasseando el límite de 6MB de Lambda Function URL.
"""
from __future__ import annotations

import uuid

import boto3
from fastapi import APIRouter, Depends, HTTPException

from core.config import get_settings
from dependencies import get_current_user
from routers.exogenas import ALLOWED_EXTENSIONS as EXOGENAS_ALLOWED
from schemas import PresignedUpload, PresignRejected, PresignRequest, PresignResponse

router = APIRouter(prefix="/uploads", tags=["Uploads"])

# 20MB por archivo — mismo límite que ya usa Renta (_MAX_MB en renta_documentos.py).
_MAX_BYTES = 20 * 1024 * 1024

FACTURAS_ALLOWED = {".pdf", ".xml"}

_CONTEXTOS = {
    "facturas": FACTURAS_ALLOWED,
    "exogenas": EXOGENAS_ALLOWED,
}


@router.post("/presign", response_model=PresignResponse)
async def presign(
    body: PresignRequest,
    user: dict = Depends(get_current_user),
) -> PresignResponse:
    if body.contexto not in _CONTEXTOS:
        raise HTTPException(422, f"Contexto inválido: {body.contexto}. Válidos: {list(_CONTEXTOS)}")

    allowed_ext = _CONTEXTOS[body.contexto]
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    uploads: list[PresignedUpload] = []
    rechazados: list[PresignRejected] = []

    for archivo in body.archivos:
        ext = "." + archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
        if ext not in allowed_ext:
            rechazados.append(PresignRejected(filename=archivo.filename, motivo=f"Extensión no permitida: {ext}"))
            continue

        s3_key = f"uploads/{body.contexto}/{user['org_id']}/{uuid.uuid4()}/{archivo.filename}"

        try:
            presigned = s3.generate_presigned_post(
                Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
                Key=s3_key,
                Fields={"Content-Type": archivo.content_type},
                Conditions=[
                    {"Content-Type": archivo.content_type},
                    ["content-length-range", 0, _MAX_BYTES],
                ],
                ExpiresIn=300,  # 5 minutos
            )
        except Exception as exc:
            rechazados.append(PresignRejected(filename=archivo.filename, motivo=f"Error generando policy: {exc}"))
            continue

        uploads.append(PresignedUpload(
            filename=archivo.filename,
            s3_key=s3_key,
            url=presigned["url"],
            fields=presigned["fields"],
        ))

    return PresignResponse(uploads=uploads, rechazados=rechazados)
