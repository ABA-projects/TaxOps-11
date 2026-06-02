from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Contribuyentes ───────────────────────────────────────────────────────────

class ContribuyenteCreate(BaseModel):
    tipo_doc: str = Field("13", pattern=r"^(13|22|41|31)$")
    numero_doc: str = Field(..., min_length=5, max_length=20)
    nombre_completo: str = Field(..., min_length=2, max_length=200)
    email: Optional[str] = None
    telefono: Optional[str] = Field(None, max_length=20)
    direccion: Optional[str] = None
    ciudad: Optional[str] = Field(None, max_length=100)
    año_gravable: int = Field(..., ge=2020, le=2030)
    observaciones: Optional[str] = None
    datos_tributarios: dict[str, Any] = Field(default_factory=dict)
    responsable_id: Optional[UUID] = None


class ContribuyenteUpdate(BaseModel):
    nombre_completo: Optional[str] = Field(None, min_length=2, max_length=200)
    email: Optional[str] = None
    telefono: Optional[str] = Field(None, max_length=20)
    direccion: Optional[str] = None
    ciudad: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = Field(
        None,
        pattern=r"^(pendiente_docs|en_proceso|revision|completado|presentado)$",
    )
    observaciones: Optional[str] = None
    datos_tributarios: Optional[dict[str, Any]] = None
    responsable_id: Optional[UUID] = None


class ContribuyenteOut(BaseModel):
    id: UUID
    org_id: UUID
    responsable_id: Optional[UUID]
    tipo_doc: str
    numero_doc: str
    nombre_completo: str
    email: Optional[str]
    telefono: Optional[str]
    direccion: Optional[str]
    ciudad: Optional[str]
    año_gravable: int
    estado: str
    observaciones: Optional[str]
    datos_tributarios: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Documentos ───────────────────────────────────────────────────────────────

class DocumentoOut(BaseModel):
    id: UUID
    contribuyente_id: UUID
    org_id: UUID
    s3_key: str
    filename: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    categoria: str
    carpeta_virtual: str
    confianza_clasificacion: float
    datos_extraidos: dict[str, Any]
    estado_ocr: str
    estado_validacion: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Declaraciones ────────────────────────────────────────────────────────────

class DeclaracionOut(BaseModel):
    id: UUID
    contribuyente_id: UUID
    año_gravable: int
    patrimonio_bruto: float
    patrimonio_liquido: float
    ingresos_laborales: float
    rentas_capital: float
    rentas_no_laborales: float
    dividendos: float
    ganancias_ocasionales: float
    rentas_exentas: float
    deducciones: float
    retenciones: float
    impuesto_cargo: float
    saldo_pagar: float
    saldo_favor: float
    # Campos Semana 4:
    aportes_pension: float = 0.0
    afc_fvp: float = 0.0
    intereses_vivienda: float = 0.0
    medicina_prepagada: float = 0.0
    dependientes: int = 0
    tipo_ganancia: Optional[str] = None
    pasivos: float = 0.0
    ajuste_manual: Optional[dict[str, Any]] = None
    estado: str
    pdf_path: Optional[str]
    inconsistencias: list[Any]
    detalle_calculo: dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Datos tributarios (PATCH /datos) ─────────────────────────────────────────

class DatosTributariosIn(BaseModel):
    ingresos_laborales: Optional[float] = None
    rentas_capital: Optional[float] = None
    rentas_no_laborales: Optional[float] = None
    aportes_pension: Optional[float] = None
    afc_fvp: Optional[float] = None
    retenciones: Optional[float] = None
    intereses_vivienda: Optional[float] = None
    medicina_prepagada: Optional[float] = None
    dependientes: Optional[int] = None
    dividendos: Optional[float] = None
    ganancias_ocasionales: Optional[float] = None
    tipo_ganancia: Optional[str] = Field(None, pattern=r"^(venta_activo|herencia|loteria)$")
    pasivos: Optional[float] = None
    patrimonio_bruto: Optional[float] = None
    ajuste_manual: Optional[dict[str, Any]] = None
    estado: Optional[str] = Field(None, pattern=r"^(borrador|revision|presentado)$")


# ─── Riesgo / info contribuyente ─────────────────────────────────────────────

class RiesgoOut(BaseModel):
    contribuyente_id: UUID
    num_docs: int
    docs_pendientes: int
    tiene_declaracion: bool
    estado: str
    inconsistencias: list[Any]
