"""db/database_renta.py — DB helpers for the Renta module."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from db.database import get_db


# ─── Contribuyentes ───────────────────────────────────────────────────────────

def get_contribuyentes(
    org_id: str,
    año_gravable: Optional[int] = None,
    estado: Optional[str] = None,
) -> list[dict]:
    from sqlalchemy import text
    clauses = ["org_id = :org_id"]
    params: dict[str, Any] = {"org_id": org_id}
    if año_gravable is not None:
        clauses.append("año_gravable = :año_gravable")
        params["año_gravable"] = año_gravable
    if estado:
        clauses.append("estado = :estado")
        params["estado"] = estado
    where = " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(
            text(f"SELECT * FROM contribuyentes WHERE {where} ORDER BY nombre_completo"),
            params,
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_contribuyente(id: str, org_id: str) -> dict | None:
    from sqlalchemy import text
    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM contribuyentes WHERE id = :id AND org_id = :org_id"),
            {"id": id, "org_id": org_id},
        ).fetchone()
    return dict(row._mapping) if row else None


def insert_contribuyente(data: dict, org_id: str) -> dict:
    from sqlalchemy import text
    import json
    new_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            text("""
                INSERT INTO contribuyentes (
                    id, org_id, responsable_id, tipo_doc, numero_doc,
                    nombre_completo, email, telefono, direccion, ciudad,
                    año_gravable, observaciones, datos_tributarios
                ) VALUES (
                    :id, :org_id, :responsable_id, :tipo_doc, :numero_doc,
                    :nombre_completo, :email, :telefono, :direccion, :ciudad,
                    :año_gravable, :observaciones, CAST(:datos_tributarios AS jsonb)
                )
            """),
            {
                "id":               new_id,
                "org_id":           org_id,
                "responsable_id":   str(data["responsable_id"]) if data.get("responsable_id") else None,
                "tipo_doc":         data.get("tipo_doc", "13"),
                "numero_doc":       data["numero_doc"],
                "nombre_completo":  data["nombre_completo"],
                "email":            data.get("email"),
                "telefono":         data.get("telefono"),
                "direccion":        data.get("direccion"),
                "ciudad":           data.get("ciudad"),
                "año_gravable":     data["año_gravable"],
                "observaciones":    data.get("observaciones"),
                "datos_tributarios": json.dumps(data.get("datos_tributarios") or {}),
            },
        )
    return get_contribuyente(new_id, org_id)


def update_contribuyente(id: str, org_id: str, fields: dict) -> bool:
    from sqlalchemy import text
    import json
    if not fields:
        return True
    if "datos_tributarios" in fields:
        fields["datos_tributarios"] = json.dumps(fields["datos_tributarios"])
    if "responsable_id" in fields and fields["responsable_id"] is not None:
        fields["responsable_id"] = str(fields["responsable_id"])
    set_clauses = ", ".join(f"{k} = :{k}" for k in fields)
    params = {**fields, "id": id, "org_id": org_id}
    with get_db() as db:
        result = db.execute(
            text(f"""
                UPDATE contribuyentes
                SET {set_clauses}, updated_at = NOW()
                WHERE id = :id AND org_id = :org_id
            """),
            params,
        )
    return result.rowcount > 0


def delete_contribuyente(id: str, org_id: str) -> bool:
    from sqlalchemy import text
    with get_db() as db:
        result = db.execute(
            text("DELETE FROM contribuyentes WHERE id = :id AND org_id = :org_id"),
            {"id": id, "org_id": org_id},
        )
    return result.rowcount > 0


# ─── Info / riesgo ────────────────────────────────────────────────────────────

def get_contribuyente_info(id: str, org_id: str) -> dict | None:
    from sqlalchemy import text
    contrib = get_contribuyente(id, org_id)
    if not contrib:
        return None
    with get_db() as db:
        num_docs = db.execute(
            text("SELECT COUNT(*) FROM renta_documentos WHERE contribuyente_id = :id"),
            {"id": id},
        ).scalar() or 0
        docs_pendientes = db.execute(
            text("SELECT COUNT(*) FROM renta_documentos WHERE contribuyente_id = :id AND estado_ocr = 'pendiente'"),
            {"id": id},
        ).scalar() or 0
        decl = db.execute(
            text("SELECT inconsistencias FROM renta_declaraciones WHERE contribuyente_id = :id LIMIT 1"),
            {"id": id},
        ).fetchone()
    return {
        "contribuyente_id": id,
        "num_docs":         int(num_docs),
        "docs_pendientes":  int(docs_pendientes),
        "tiene_declaracion": decl is not None,
        "estado":           contrib["estado"],
        "inconsistencias":  decl[0] if decl else [],
    }


# ─── Documentos ───────────────────────────────────────────────────────────────

def get_documentos(contribuyente_id: str, org_id: str) -> list[dict]:
    from sqlalchemy import text
    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT * FROM renta_documentos
                WHERE contribuyente_id = :cid AND org_id = :org_id
                ORDER BY created_at DESC
            """),
            {"cid": contribuyente_id, "org_id": org_id},
        ).fetchall()
    return [dict(r._mapping) for r in rows]


# ─── Declaraciones ────────────────────────────────────────────────────────────

def get_declaracion(contribuyente_id: str, org_id: str) -> dict | None:
    from sqlalchemy import text
    with get_db() as db:
        row = db.execute(
            text("""
                SELECT d.* FROM renta_declaraciones d
                JOIN contribuyentes c ON c.id = d.contribuyente_id
                WHERE d.contribuyente_id = :cid AND c.org_id = :org_id
                ORDER BY d.año_gravable DESC
                LIMIT 1
            """),
            {"cid": contribuyente_id, "org_id": org_id},
        ).fetchone()
    return dict(row._mapping) if row else None


# ─── Reglas tributarias ───────────────────────────────────────────────────────

def get_reglas_tributarias(año_gravable: int) -> list[dict]:
    from sqlalchemy import text
    with get_db() as db:
        rows = db.execute(
            text("SELECT * FROM reglas_tributarias WHERE año_gravable = :año ORDER BY tipo_regla, concepto"),
            {"año": año_gravable},
        ).fetchall()
    return [dict(r._mapping) for r in rows]
