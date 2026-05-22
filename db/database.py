"""db/database.py — PostgreSQL access layer. Engine is lazy: only created when DATABASE_URL is set."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import pandas as pd

_DATABASE_URL: str | None = os.environ.get("DATABASE_URL")

# Module-level engine/session — created only when DATABASE_URL is present
_engine = None
_SessionLocal = None

if _DATABASE_URL:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session
    _engine = create_engine(
        _DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=5,
        echo=False,
        connect_args={"connect_timeout": 3},
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

_db_status: bool | None = None


@contextmanager
def get_db() -> Generator:
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL not set — DB unavailable")
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def db_available() -> bool:
    """True if PostgreSQL is reachable. Caches True permanently; retries on False."""
    global _db_status
    if _DATABASE_URL is None:
        return False
    if _db_status is True:
        return True
    # Never cache False — always retry so a transient startup failure doesn't block forever
    try:
        from sqlalchemy import text
        with get_db() as db:
            db.execute(text("SELECT 1"))
        _db_status = True
        return True
    except Exception:
        return False


def get_existing_cufes(org_id: str) -> set[str]:
    """CUFEs already processed for an org. Returns empty set if DB unavailable."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            rows = db.execute(
                text("SELECT cufe FROM invoices WHERE org_id = :org_id"),
                {"org_id": org_id},
            ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def insert_invoices_batch(rows: list[dict], org_id: str, session_id: str | None = None) -> tuple[int, int]:
    """Insert invoices in batch. Skips duplicates via ON CONFLICT DO NOTHING.

    Returns:
        (new_count, duplicate_count)
    """
    if not rows or not db_available():
        return 0, 0

    from sqlalchemy import text
    sql = text("""
        INSERT INTO invoices (
            org_id, cufe, folio, tipo, fecha,
            nit_emisor, nombre_emisor, nit_receptor, nombre_receptor,
            subtotal, base_iva_19, iva_19, base_iva_5, iva_5,
            no_gravado, total, retencion_fuente, fuente, periodo
        ) VALUES (
            :org_id, :cufe, :folio, :tipo, :fecha,
            :nit_emisor, :nombre_emisor, :nit_receptor, :nombre_receptor,
            :subtotal, :base_iva_19, :iva_19, :base_iva_5, :iva_5,
            :no_gravado, :total, :retencion_fuente, :fuente, :periodo
        )
        ON CONFLICT (org_id, cufe) DO NOTHING
    """)

    nuevas = 0
    with get_db() as db:
        for row in rows:
            r = dict(row)
            r["org_id"] = org_id
            fecha = r.get("fecha") or None
            r["fecha"] = fecha
            if fecha and str(fecha) not in ("None", "nan", ""):
                try:
                    r["periodo"] = str(fecha)[:7]
                except Exception:
                    r["periodo"] = None
            else:
                r["periodo"] = None
            result = db.execute(sql, r)
            nuevas += result.rowcount

    return nuevas, len(rows) - nuevas


def insert_exogenas_batch(df: pd.DataFrame, org_id: str, session_id: str | None = None) -> None:
    """Insert exogenas detail rows into exogenas_results. One row per df row."""
    if df.empty or not db_available():
        return

    from sqlalchemy import text
    import json
    sql = text("""
        INSERT INTO exogenas_results (org_id, session_id, anio, concepto, nit,
            razon_social, base, retencion, porcentaje, raw_row)
        VALUES (:org_id, :session_id, :anio, :concepto, :nit,
            :razon_social, :base, :retencion, :porcentaje, :raw_row::jsonb)
        ON CONFLICT (org_id, nit, concepto, anio) DO NOTHING
    """)

    with get_db() as db:
        for _, row in df.iterrows():
            db.execute(sql, {
                "org_id":       org_id,
                "session_id":   session_id,
                "anio":         int(row.get("anio", 0) or 0),
                "concepto":     str(row.get("concepto") or ""),
                "nit":          str(row.get("nit") or ""),
                "razon_social": str(row.get("razon_social") or ""),
                "base":         float(row.get("base") or 0),
                "retencion":    float(row.get("retencion") or 0),
                "porcentaje":   float(row.get("porcentaje") or 0),
                "raw_row":      json.dumps(row.to_dict(), default=str),
            })


def get_autorretenedores_nits() -> set[str]:
    """Load autorretenedor NITs from PostgreSQL. Falls back to empty set."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            rows = db.execute(
                text("SELECT nit FROM autorretenedores WHERE vigente = TRUE")
            ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


# ── User management ───────────────────────────────────────────────────────────

def list_users(org_id: str) -> list[dict]:
    """Return all users for an org, ordered by created_at."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            rows = db.execute(
                text("""
                    SELECT id, email, full_name, role, active, created_at, last_login_at
                    FROM users
                    WHERE org_id = :org_id
                    ORDER BY created_at
                """),
                {"org_id": org_id},
            ).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def create_user(org_id: str, email: str, password: str, role: str = "contador", full_name: str = "") -> dict:
    """Create a new user in the given org. Returns the created user dict."""
    from db.auth import hash_password
    from sqlalchemy import text
    import uuid

    user_id = str(uuid.uuid4())
    hashed = hash_password(password)
    with get_db() as db:
        db.execute(
            text("""
                INSERT INTO users (id, org_id, email, hashed_password, role, full_name)
                VALUES (:id, :org_id, :email, :hashed_password, :role, :full_name)
            """),
            {
                "id": user_id,
                "org_id": org_id,
                "email": email.strip().lower(),
                "hashed_password": hashed,
                "role": role,
                "full_name": full_name.strip(),
            },
        )
    return {"id": user_id, "email": email, "role": role}


def set_user_active(user_id: str, org_id: str, active: bool) -> None:
    """Enable or disable a user. org_id scopes the update to prevent cross-org edits."""
    from sqlalchemy import text
    with get_db() as db:
        db.execute(
            text("UPDATE users SET active = :active WHERE id = :user_id AND org_id = :org_id"),
            {"active": active, "user_id": user_id, "org_id": org_id},
        )


# ── Dashboard stats ───────────────────────────────────────────────────────────

def get_dashboard_stats(org_id: str) -> dict:
    """Return KPI counts for the admin dashboard."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            row = db.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE periodo = TO_CHAR(NOW(), 'YYYY-MM'))      AS facturas_mes_actual,
                    COUNT(*) FILTER (WHERE periodo = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')) AS facturas_mes_anterior,
                    COUNT(*)                                                           AS facturas_total
                FROM invoices WHERE org_id = :org_id
            """), {"org_id": org_id}).fetchone()
            usuarios = db.execute(text(
                "SELECT COUNT(*) FROM users WHERE org_id = :org_id AND active = TRUE"
            ), {"org_id": org_id}).fetchone()
            clientes = db.execute(text(
                "SELECT COUNT(*) FROM clients WHERE org_id = :org_id AND active = TRUE"
            ), {"org_id": org_id}).fetchone()
            ultima = db.execute(text(
                "SELECT MAX(started_at) FROM processing_sessions WHERE org_id = :org_id"
            ), {"org_id": org_id}).fetchone()
        return {
            "facturas_mes_actual":   int(row[0] or 0),
            "facturas_mes_anterior": int(row[1] or 0),
            "facturas_total":        int(row[2] or 0),
            "usuarios_activos":      int(usuarios[0] or 0),
            "clientes_activos":      int(clientes[0] or 0),
            "ultima_actividad":      ultima[0],
        }
    except Exception:
        return {"facturas_mes_actual": 0, "facturas_mes_anterior": 0, "facturas_total": 0,
                "usuarios_activos": 0, "clientes_activos": 0, "ultima_actividad": None}


# ── Client management ──────────────────────────────────────────────────────────

def list_clients(org_id: str) -> list[dict]:
    try:
        from sqlalchemy import text
        with get_db() as db:
            rows = db.execute(text("""
                SELECT id, nit, razon_social, active, created_at
                FROM clients WHERE org_id = :org_id ORDER BY razon_social
            """), {"org_id": org_id}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def create_client(org_id: str, nit: str, razon_social: str) -> None:
    from sqlalchemy import text
    import uuid
    with get_db() as db:
        db.execute(text("""
            INSERT INTO clients (id, org_id, nit, razon_social)
            VALUES (:id, :org_id, :nit, :razon_social)
        """), {"id": str(uuid.uuid4()), "org_id": org_id,
               "nit": nit.strip(), "razon_social": razon_social.strip()})


def set_client_active(client_id: str, org_id: str, active: bool) -> None:
    from sqlalchemy import text
    with get_db() as db:
        db.execute(text(
            "UPDATE clients SET active = :active WHERE id = :id AND org_id = :org_id"
        ), {"active": active, "id": client_id, "org_id": org_id})


# ── Activity log ───────────────────────────────────────────────────────────────

def list_processing_sessions(org_id: str, limit: int = 50) -> list[dict]:
    try:
        from sqlalchemy import text
        with get_db() as db:
            rows = db.execute(text("""
                SELECT ps.id, ps.started_at, ps.finished_at, ps.status,
                       ps.total_archivos, ps.procesados, ps.errores, ps.nuevas, ps.duplicadas,
                       u.email AS usuario
                FROM processing_sessions ps
                LEFT JOIN users u ON ps.user_id = u.id
                WHERE ps.org_id = :org_id
                ORDER BY ps.started_at DESC
                LIMIT :limit
            """), {"org_id": org_id, "limit": limit}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


# ── Organization ───────────────────────────────────────────────────────────────

def get_org(org_id: str) -> dict | None:
    try:
        from sqlalchemy import text
        with get_db() as db:
            row = db.execute(text(
                "SELECT id, name, slug, nit, plan, active, created_at FROM organizations WHERE id = :org_id"
            ), {"org_id": org_id}).fetchone()
        return dict(row._mapping) if row else None
    except Exception:
        return None


def update_org(org_id: str, name: str, nit: str) -> None:
    from sqlalchemy import text
    with get_db() as db:
        db.execute(text(
            "UPDATE organizations SET name = :name, nit = :nit WHERE id = :org_id"
        ), {"name": name.strip(), "nit": nit.strip(), "org_id": org_id})


# ── Password change ────────────────────────────────────────────────────────────

def update_user_password(user_id: str, org_id: str, new_password: str) -> None:
    from db.auth import hash_password
    from sqlalchemy import text
    hashed = hash_password(new_password)
    with get_db() as db:
        db.execute(text("""
            UPDATE users SET hashed_password = :hashed WHERE id = :user_id AND org_id = :org_id
        """), {"hashed": hashed, "user_id": user_id, "org_id": org_id})


# ── Cleanup helpers (used by future admin UI) ─────────────────────────────────

def preview_cleanup(org_id: str, meses_a_conservar: int = 3) -> dict:
    """Preview what would be deleted. Does NOT delete anything."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            corte_result = db.execute(
                text(f"SELECT TO_CHAR(NOW() - INTERVAL '{meses_a_conservar} months', 'YYYY-MM') AS corte")
            ).fetchone()
            corte = corte_result[0] if corte_result else None
            if not corte:
                return {"total": 0, "periodos": [], "desde_periodo": ""}
            rows = db.execute(
                text("""
                    SELECT periodo, COUNT(*) as cnt
                    FROM invoices
                    WHERE org_id = :org_id AND periodo IS NOT NULL AND periodo < :corte
                    GROUP BY periodo ORDER BY periodo
                """),
                {"org_id": org_id, "corte": corte},
            ).fetchall()
        periodos = [{"periodo": r[0], "count": r[1]} for r in rows]
        return {"total": sum(p["count"] for p in periodos), "periodos": periodos, "desde_periodo": corte}
    except Exception as e:
        return {"total": 0, "periodos": [], "desde_periodo": "", "error": str(e)}


def execute_cleanup(org_id: str, meses_a_conservar: int = 3) -> int:
    """Delete invoices older than N months. Returns number of deleted rows."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            corte_result = db.execute(
                text(f"SELECT TO_CHAR(NOW() - INTERVAL '{meses_a_conservar} months', 'YYYY-MM') AS corte")
            ).fetchone()
            corte = corte_result[0] if corte_result else None
            if not corte:
                return 0
            result = db.execute(
                text("DELETE FROM invoices WHERE org_id = :org_id AND periodo IS NOT NULL AND periodo < :corte"),
                {"org_id": org_id, "corte": corte},
            )
            return result.rowcount
    except Exception:
        return 0


# ── Public registration ────────────────────────────────────────────────────────

def register_org(firm_name: str, email: str, password: str) -> dict:
    """Create a new org + owner user from the public signup form.

    Returns:
        dict with org_id, user_id, email — ready to store in session_state["auth"]
    """
    from db.auth import hash_password
    from sqlalchemy import text
    import uuid, re

    slug_base = re.sub(r"[^a-z0-9]+", "-", firm_name.lower().strip())[:40]
    org_id  = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    hashed  = hash_password(password)

    with get_db() as db:
        # Ensure unique slug
        existing = db.execute(
            text("SELECT COUNT(*) FROM organizations WHERE slug LIKE :pattern"),
            {"pattern": f"{slug_base}%"},
        ).scalar()
        slug = slug_base if existing == 0 else f"{slug_base}-{existing}"

        db.execute(text("""
            INSERT INTO organizations (id, slug, name, plan)
            VALUES (:id, :slug, :name, 'free')
        """), {"id": org_id, "slug": slug, "name": firm_name.strip()})

        db.execute(text("""
            INSERT INTO users (id, org_id, email, hashed_password, role)
            VALUES (:id, :org_id, :email, :hashed_password, 'owner')
        """), {
            "id": user_id, "org_id": org_id,
            "email": email.strip().lower(),
            "hashed_password": hashed,
        })

    return {"user_id": user_id, "org_id": org_id, "role": "owner", "email": email.strip().lower()}


# ── Super-admin (cross-tenant, no org_id scope) ────────────────────────────────

def superadmin_global_stats() -> dict:
    """Platform-wide KPIs. No org scoping — only for the platform operator."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            orgs = db.execute(text(
                "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE active) AS activas FROM organizations"
            )).fetchone()
            users = db.execute(text("SELECT COUNT(*) FROM users")).fetchone()
            invoices = db.execute(text(
                "SELECT COUNT(*) AS total, "
                "COUNT(*) FILTER (WHERE periodo = TO_CHAR(NOW(),'YYYY-MM')) AS este_mes "
                "FROM invoices"
            )).fetchone()
        return {
            "orgs_total":    int(orgs[0] or 0),
            "orgs_activas":  int(orgs[1] or 0),
            "usuarios_total": int(users[0] or 0),
            "facturas_total": int(invoices[0] or 0),
            "facturas_mes":   int(invoices[1] or 0),
        }
    except Exception:
        return {"orgs_total": 0, "orgs_activas": 0, "usuarios_total": 0,
                "facturas_total": 0, "facturas_mes": 0}


def superadmin_list_orgs() -> list[dict]:
    """All organizations with usage metrics."""
    try:
        from sqlalchemy import text
        with get_db() as db:
            rows = db.execute(text("""
                SELECT
                    o.id, o.name, o.slug, o.nit, o.plan, o.active, o.created_at,
                    COUNT(DISTINCT u.id)  AS usuarios,
                    COUNT(DISTINCT i.id)  AS facturas,
                    COUNT(DISTINCT c.id)  AS clientes,
                    MAX(ps.started_at)    AS ultima_actividad
                FROM organizations o
                LEFT JOIN users              u  ON u.org_id = o.id
                LEFT JOIN invoices           i  ON i.org_id = o.id
                LEFT JOIN clients            c  ON c.org_id = o.id
                LEFT JOIN processing_sessions ps ON ps.org_id = o.id
                GROUP BY o.id, o.name, o.slug, o.nit, o.plan, o.active, o.created_at
                ORDER BY o.created_at DESC
            """)).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def superadmin_set_org_active(org_id: str, active: bool) -> None:
    from sqlalchemy import text
    with get_db() as db:
        db.execute(text(
            "UPDATE organizations SET active = :active WHERE id = :org_id"
        ), {"active": active, "org_id": org_id})


def superadmin_set_org_plan(org_id: str, plan: str) -> None:
    from sqlalchemy import text
    with get_db() as db:
        db.execute(text(
            "UPDATE organizations SET plan = :plan WHERE id = :org_id"
        ), {"plan": plan, "org_id": org_id})


def superadmin_org_detail(org_id: str) -> dict:
    """Users + last 20 sessions for any org (cross-tenant drill-down)."""
    users    = list_users(org_id)
    sessions = list_processing_sessions(org_id, limit=20)
    org      = get_org(org_id)
    return {"org": org, "users": users, "sessions": sessions}
