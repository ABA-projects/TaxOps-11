"""Pydantic schemas — validación de requests y responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    org_name: str  # Nombre de la firma/empresa

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

    @field_validator("org_name")
    @classmethod
    def org_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre de la organización es obligatorio")
        return v.strip()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Role constants ────────────────────────────────────────────────────────────
ADMIN_ROLES = ("owner", "admin")
BASE_ROLES  = ("contador", "auxiliar_contable")
ALL_ROLES   = ADMIN_ROLES + BASE_ROLES

ROLE_LABELS = {
    "owner":             "Owner",
    "admin":             "Admin",
    "contador":          "Contador",
    "auxiliar_contable": "Auxiliar Contable",
}

# ── Users ─────────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: str
    org_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: str = "contador"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ALL_ROLES:
            raise ValueError(f"Rol inválido. Opciones: {', '.join(ALL_ROLES)}")
        return v


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


class ChangeRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ALL_ROLES:
            raise ValueError(f"Rol inválido. Opciones: {', '.join(ALL_ROLES)}")
        return v


# ── Organizations ─────────────────────────────────────────────────────────────

class OrgResponse(BaseModel):
    id: str
    slug: str
    name: str
    nit: Optional[str] = None
    plan: str
    active: bool
    created_at: datetime


class CreateOrgRequest(BaseModel):
    slug: str
    name: str
    nit: Optional[str] = None
    plan: str = "free"


# ── Clients ───────────────────────────────────────────────────────────────────

class ClientResponse(BaseModel):
    id: str
    org_id: str
    nit: str
    razon_social: str
    active: bool
    created_at: datetime


class CreateClientRequest(BaseModel):
    nit: str
    razon_social: str


# ── Invoices ──────────────────────────────────────────────────────────────────

class IngresosProrateoItem(BaseModel):
    periodo: str  # YYYY-MM
    gravados: float = 0.0
    excluidos: float = 0.0


class ProcessInvoicesResponse(BaseModel):
    total_archivos: int
    procesados: int
    errores: int
    db_nuevas: int = 0
    db_duplicadas: int = 0
    df_base: list[dict[str, Any]]
    df_val: list[dict[str, Any]]
    df_pror: list[dict[str, Any]]


class ExportInvoicesRequest(BaseModel):
    df_base: list[dict[str, Any]]
    df_val: list[dict[str, Any]]
    df_pror: list[dict[str, Any]]


# ── Exogenas ──────────────────────────────────────────────────────────────────

class ProcessExogenasResponse(BaseModel):
    total_archivos: int
    procesados: int
    errores: int
    ica_excluidos: int
    advertencias: list[str]
    df_detalle: list[dict[str, Any]]
    df_1003: list[dict[str, Any]]


class ExportExogenasRequest(BaseModel):
    df_detalle: list[dict[str, Any]]
    df_1003: list[dict[str, Any]]


# ── Chatbot ───────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    history: list[ChatMessage] = []
    df_context: Optional[list[dict[str, Any]]] = None
    df_type: Optional[str] = None  # "facturas" | "exogenas"
    system_prompt: Optional[str] = None  # override para chatbots contextuales


class ChatResponse(BaseModel):
    content: str
    provider: str
    model: str


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    total_invoices: int
    total_exogenas: int
    total_users: int
    total_clients: int
    invoices_this_month: int
    recent_sessions: list[dict[str, Any]]
    # Extended financial + operational metrics
    invoices_by_month: list[dict[str, Any]] = []
    top_providers: list[dict[str, Any]] = []
    active_users_today: int = 0
    modules_usage: list[dict[str, Any]] = []
    error_rate: float = 0.0
    total_nomina: int = 0


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    modules: list[str] = []


class GroupResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: Optional[str] = None
    modules: list[str]
    created_at: datetime
    members_count: int = 0


class AuditLogEntry(BaseModel):
    id: str
    user_email: Optional[str] = None
    action: str
    module: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime


class SuperadminOrgStats(BaseModel):
    id: str
    slug: str
    name: str
    plan: str
    active: bool
    users_count: int
    invoices_count: int


# ── Invitations ───────────────────────────────────────────────────────────────

class InviteCreate(BaseModel):
    email: str
    role: str = "auxiliar_contable"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "contador", "auxiliar_contable"):
            raise ValueError("Rol inválido. Opciones: admin, contador, auxiliar_contable")
        return v


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    invite_url: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime


class AcceptInviteRequest(BaseModel):
    full_name: Optional[str] = None
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class InviteInfoResponse(BaseModel):
    email: str
    role: str
    org_name: str
