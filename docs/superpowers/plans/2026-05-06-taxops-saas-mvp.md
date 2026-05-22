# TaxOps SaaS MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authentication, multi-tenancy, and persistent storage to TaxOps so the pilot accounting firm can log in on Railway with isolated data and pay a monthly subscription.

**Architecture:** Two-mode codebase — when `DATABASE_URL` env var is absent the app works exactly as today (local, no DB, no login). When `DATABASE_URL` is set (Railway) a login gate appears and all processed data is stored per-organization in PostgreSQL. A single `manage.py` CLI bootstraps the DB schema and creates the first org/user.

**Tech Stack:** Streamlit · streamlit-authenticator==0.3.3 · SQLAlchemy 2.x · psycopg2-binary · PostgreSQL 16 (Railway managed)

**Spec:** `docs/superpowers/specs/2026-05-06-taxops-saas-mvp-design.md`

---

## Chunk 1: Dependencies and DB Lazy Init

### Task 1: Add new dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add to `requirements.txt`**

Append these four lines after `groq>=0.11`:

```
sqlalchemy>=2.0
psycopg2-binary>=2.9
streamlit-authenticator==0.3.3
bcrypt>=4.0
```

`bcrypt` is listed explicitly even though it is a transitive dependency of `streamlit-authenticator` — this prevents breakage if `streamlit-authenticator` changes its hashing backend.

- [ ] **Step 2: Add to `pyproject.toml` dependencies list**

In `pyproject.toml` under `[project].dependencies`, add after `"groq>=0.11"`:

```toml
"sqlalchemy>=2.0",
"psycopg2-binary>=2.9",
"streamlit-authenticator==0.3.3",
"bcrypt>=4.0",
```

- [ ] **Step 3: Install locally to verify no conflicts**

```bash
pip install "sqlalchemy>=2.0" psycopg2-binary "streamlit-authenticator==0.3.3" "bcrypt>=4.0"
```

Expected: all three install without errors. Note: psycopg2-binary on Mac may show a warning about binary wheel — that is fine.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt pyproject.toml
git commit -m "feat: add sqlalchemy, psycopg2-binary, streamlit-authenticator deps"
```

---

### Task 2: Refactor `db/database.py` to lazy engine initialization

**Context:** Currently `database.py` calls `create_engine()` at module import time with a hardcoded fallback to `localhost:5432`. This makes every local install attempt a TCP connection on startup. The fix: only build the engine when `DATABASE_URL` is present in the environment.

**Files:**
- Modify: `db/database.py`
- Create: `tests/test_database_lazy.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_database_lazy.py`:

```python
"""Tests for lazy DB engine initialization."""
import importlib
import os
import sys


def test_import_without_database_url_does_not_raise(monkeypatch):
    """Importing db.database without DATABASE_URL must never raise."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Remove cached module so it re-imports cleanly
    sys.modules.pop("db.database", None)
    import db.database  # must not raise
    assert db.database.db_available() is False


def test_db_available_returns_false_without_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sys.modules.pop("db.database", None)
    import db.database
    assert db.database.db_available() is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_database_lazy.py -v
```

Expected: `FAILED` — import either raises `OperationalError` or `db_available()` returns `True` (because engine connects to localhost).

- [ ] **Step 3: Rewrite `db/database.py` with lazy init**

Replace the entire file with:

```python
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
    """True if PostgreSQL is reachable. Result is cached for the process lifetime."""
    global _db_status
    if _DATABASE_URL is None:
        return False
    if _db_status is not None:
        return _db_status
    try:
        from sqlalchemy import text
        with get_db() as db:
            db.execute(text("SELECT 1"))
        _db_status = True
    except Exception:
        _db_status = False
    return _db_status


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
    """Insert exogenas detail rows into exogenas_results. One row per df row.

    Uses ON CONFLICT DO NOTHING on (org_id, nit, concepto, anio) to safely
    re-process the same file without creating duplicates.
    """
    if df.empty or not db_available():
        return

    from sqlalchemy import text
    sql = text("""
        INSERT INTO exogenas_results (org_id, session_id, anio, concepto, nit,
            razon_social, base, retencion, porcentaje, raw_row)
        VALUES (:org_id, :session_id, :anio, :concepto, :nit,
            :razon_social, :base, :retencion, :porcentaje, :raw_row::jsonb)
        ON CONFLICT (org_id, nit, concepto, anio) DO NOTHING
    """)

    import json
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_database_lazy.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Verify existing tests still pass**

```bash
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py -v
```

Expected: all pass (no DB dependency in those tests).

- [ ] **Step 6: Commit**

```bash
git add db/database.py tests/test_database_lazy.py
git commit -m "refactor: lazy-init DB engine — only connects when DATABASE_URL is set"
```

---

## Chunk 2: Schema Update and Auth Layer

### Task 3: Add `exogenas_results` table to `db/init.sql`

**Files:**
- Modify: `db/init.sql`

- [ ] **Step 1: Append the new table DDL to `db/init.sql`**

At the end of `db/init.sql`, after the last `CREATE TABLE` block, add:

```sql
-- ────────────────────────────────────────────────────────────
-- EXOGENAS_RESULTS — resultados de procesamiento de exógenas
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exogenas_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES processing_sessions(id),
    anio            INTEGER NOT NULL,
    concepto        TEXT,
    nit             TEXT,
    razon_social    TEXT,
    base            NUMERIC(18,2),
    retencion       NUMERIC(18,2),
    porcentaje      NUMERIC(5,2),
    raw_row         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (org_id, nit, concepto, anio)
);
CREATE INDEX IF NOT EXISTS ix_exogenas_results_org_id ON exogenas_results(org_id);
```

Note: the `UNIQUE (org_id, nit, concepto, anio)` constraint is required for the `ON CONFLICT DO NOTHING` clause in `insert_exogenas_batch`.

- [ ] **Step 2: Verify SQL syntax**

```bash
python -c "
import re, pathlib
sql = pathlib.Path('db/init.sql').read_text()
print('exogenas_results found:', 'exogenas_results' in sql)
print('UNIQUE constraint found:', 'UNIQUE (org_id, nit, concepto, anio)' in sql)
"
```

Expected: both `True`.

- [ ] **Step 3: Commit**

```bash
git add db/init.sql
git commit -m "feat: add exogenas_results table to schema"
```

---

### Task 4: Create `db/auth.py`

**Files:**
- Create: `db/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_auth.py`:

```python
"""Tests for db/auth.py — user lookup and session creation."""
import pytest


def test_verify_password_correct():
    from db.auth import hash_password, verify_password
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_verify_password_wrong():
    from db.auth import hash_password, verify_password
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_hash_password_produces_bcrypt_prefix():
    from db.auth import hash_password
    hashed = hash_password("anypassword")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_build_session_dict():
    from db.auth import _build_session
    row = {"id": "uuid1", "org_id": "org1", "role": "owner", "email": "a@b.com"}
    session = _build_session(row)
    assert session["user_id"] == "uuid1"
    assert session["org_id"] == "org1"
    assert session["role"] == "owner"
    assert session["email"] == "a@b.com"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Create `db/auth.py`**

```python
"""db/auth.py — User authentication and session helpers."""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """True if plain matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _build_session(row: dict) -> dict:
    """Convert a DB user row to the st.session_state["auth"] contract."""
    return {
        "user_id": str(row["id"]),
        "org_id":  str(row["org_id"]),
        "role":    str(row["role"]),
        "email":   str(row["email"]),
    }


def authenticate(email: str, password: str) -> dict | None:
    """Look up user by email, verify password. Returns session dict or None.

    Returns None if DB is unavailable, email not found, password wrong,
    or user is inactive.
    """
    from db.database import db_available, get_db
    if not db_available():
        return None

    from sqlalchemy import text
    try:
        with get_db() as db:
            row = db.execute(
                text("""
                    SELECT id, org_id, role, email, hashed_password
                    FROM users
                    WHERE email = :email AND active = TRUE
                """),
                {"email": email.strip().lower()},
            ).mappings().fetchone()
    except Exception:
        return None

    if row is None:
        return None

    if not verify_password(password, row["hashed_password"]):
        return None

    # Update last_login_at (best-effort, don't fail auth if this errors)
    try:
        with get_db() as db:
            db.execute(
                text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
                {"id": row["id"]},
            )
    except Exception:
        pass

    return _build_session(dict(row))
```

Note: `bcrypt` is a dependency of `streamlit-authenticator==0.3.3` — it will already be installed.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add db/auth.py tests/test_auth.py
git commit -m "feat: add db/auth.py — bcrypt user authentication"
```

---

## Chunk 3: Login Gate in Home.py

### Task 5: Add conditional login gate to `Home.py`

**Context:** When `DATABASE_URL` is set, `Home.py` must show a login form before rendering navigation. When not set, it renders exactly as today. The gate lives entirely in `Home.py` — pages do not need their own auth checks (Streamlit re-runs `Home.py` on every navigation).

**Files:**
- Modify: `Home.py`
- Create: `tests/test_home_auth_gate.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_home_auth_gate.py`:

```python
"""Tests for the auth gate logic (not Streamlit rendering — pure logic)."""
import os


def test_saas_mode_when_database_url_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost/z")
    import importlib, sys
    sys.modules.pop("db.database", None)
    import db.database as dbmod
    # DATABASE_URL is set → _DATABASE_URL is not None
    assert dbmod._DATABASE_URL is not None


def test_local_mode_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import sys
    sys.modules.pop("db.database", None)
    import db.database as dbmod
    assert dbmod._DATABASE_URL is None
    assert dbmod.db_available() is False
```

- [ ] **Step 2: Run to verify (these should already pass after Task 2)**

```bash
python -m pytest tests/test_home_auth_gate.py -v
```

Expected: both PASS (verifies the lazy init is working before we touch Home.py).

- [ ] **Step 3: Rewrite `Home.py` with auth gate**

```python
"""Home.py — Entry point and main router for TaxOps."""

from __future__ import annotations
import os
import streamlit as st

st.set_page_config(
    page_title="TaxOps · Automatización Contable Colombia",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth gate — only active when DATABASE_URL is set ─────────────────────────
_SAAS_MODE = bool(os.environ.get("DATABASE_URL"))

if _SAAS_MODE:
    from db.auth import authenticate

    if "auth" not in st.session_state:
        st.session_state["auth"] = None

    if st.session_state["auth"] is None:
        st.title("🧾 TaxOps")
        st.markdown("#### Iniciar sesión")

        with st.form("login_form"):
            email    = st.text_input("Correo electrónico")
            password = st.text_input("Contraseña", type="password")
            submit   = st.form_submit_button("Entrar", use_container_width=True)

        if submit:
            session = authenticate(email, password)
            if session:
                st.session_state["auth"] = session
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")
        st.stop()

    # Logout button in sidebar
    with st.sidebar:
        auth = st.session_state["auth"]
        st.caption(f"👤 {auth['email']}")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state["auth"] = None
            st.rerun()

# ── Navigation ────────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "": [
            st.Page("pages/0_Inicio.py", title="Inicio", icon="🏠", default=True),
        ],
        "Facturas DIAN": [
            st.Page("pages/1_Procesar.py",      title="Procesar",      icon="⚙️"),
            st.Page("pages/3_Validacion.py",    title="Validación",    icon="✅"),
            st.Page("pages/4_Prorrateo_IVA.py", title="Prorrateo IVA", icon="📈"),
            st.Page("pages/5_Chatbot.py",       title="Chatbot",       icon="🤖"),
        ],
        "Exógenas": [
            st.Page("pages/6_Exogenas.py",           title="Procesar",  icon="📋"),
            st.Page("pages/7_Exogenas_Analitica.py",  title="Analítica", icon="📊"),
            st.Page("pages/8_Exogenas_Chatbot.py",    title="Chatbot",   icon="🤖"),
        ],
    }
)
pg.run()
```

- [ ] **Step 4: Verify app still starts locally (no DATABASE_URL)**

```bash
python -m streamlit run Home.py &
sleep 4
curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
kill %1
```

Expected: `200` — app loads without login screen.

- [ ] **Step 5: Commit**

```bash
git add Home.py tests/test_home_auth_gate.py
git commit -m "feat: add conditional login gate to Home.py (SaaS mode)"
```

---

## Chunk 4: Service Layer — Wire org_id

### Task 6: Wire `org_id` in `services/processor.py`

**Context:** `processor.py` already accepts `org_id` as a parameter (currently a no-op). The change: when `org_id` is provided and the DB is available, call `insert_invoices_batch()` after building `df_base`.

**Files:**
- Modify: `services/processor.py`
- Create: `tests/test_processor_org_id.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_processor_org_id.py`:

```python
"""Test that processor.py calls insert_invoices_batch when org_id is provided."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd


def _fake_extract(path):
    return {
        "tipo": "Factura Electrónica", "cufe": "a" * 96, "folio": "FE-001",
        "fecha": "2026-01-15", "nit_emisor": "900123456", "nombre_emisor": "Test SA",
        "nit_receptor": "800000001", "nombre_receptor": "Cliente",
        "subtotal": 100000, "base_iva_19": 100000, "iva_19": 19000,
        "base_iva_5": 0, "iva_5": 0, "no_gravado": 0, "total": 119000,
        "retencion_fuente": 0, "fuente": "pdf",
    }


def test_insert_called_when_org_id_provided(tmp_path):
    fake_file = tmp_path / "FE-001.pdf"
    fake_file.write_bytes(b"")

    with patch("services.processor.extract_one", side_effect=_fake_extract), \
         patch("services.processor.db_available", return_value=True), \
         patch("services.processor.insert_invoices_batch") as mock_insert:
        from services.processor import procesar
        result = procesar([fake_file], org_id="org-uuid-123")

    mock_insert.assert_called_once()
    call_args = mock_insert.call_args
    assert call_args[0][1] == "org-uuid-123"  # second positional arg is org_id


def test_insert_not_called_without_org_id(tmp_path):
    fake_file = tmp_path / "FE-001.pdf"
    fake_file.write_bytes(b"")

    with patch("services.processor.extract_one", side_effect=_fake_extract), \
         patch("services.processor.insert_invoices_batch") as mock_insert:
        from services.processor import procesar
        result = procesar([fake_file])  # no org_id

    mock_insert.assert_not_called()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_processor_org_id.py -v
```

Expected: `FAILED` — `insert_invoices_batch` is never called.

- [ ] **Step 3: Modify `services/processor.py`**

Add these imports at the top (after existing imports):

```python
from db.database import db_available, insert_invoices_batch
```

In the `procesar()` function, after `df_base = df[[c for c in BASE_COLS if c in df.columns]]`, add:

```python
    if org_id and db_available():
        insert_invoices_batch(df_base.to_dict("records"), org_id)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_processor_org_id.py -v
```

Expected: both PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py tests/test_processor_org_id.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/processor.py tests/test_processor_org_id.py
git commit -m "feat: wire insert_invoices_batch in processor when org_id provided"
```

---

### Task 7: Wire `org_id` in `services/processor_exogenas.py`

**Files:**
- Modify: `services/processor_exogenas.py`
- Create: `tests/test_processor_exogenas_org_id.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_processor_exogenas_org_id.py`:

```python
"""Test that processor_exogenas calls insert_exogenas_batch when org_id is given."""
from unittest.mock import patch
import pandas as pd


def _fake_extract(path):
    return {
        "concepto": "01", "tipo_doc": "31", "nit": "900123456", "dv": "1",
        "primer_apellido": "", "segundo_apellido": "", "primer_nombre": "",
        "otros_nombres": "", "razon_social": "PROVEEDOR SA", "direccion": "CL 1",
        "ciudad_retencion": "Medellín", "cod_dpto": "05", "cod_mpio": "001",
        "base": 1000000.0, "retencion": 35000.0, "porcentaje": 3.5,
    }


def test_insert_exogenas_called_when_org_id_provided(tmp_path):
    fake_file = tmp_path / "cert.pdf"
    fake_file.write_bytes(b"")

    with patch("services.processor_exogenas.extract_one", return_value=_fake_extract(fake_file)), \
         patch("services.processor_exogenas.db_available", return_value=True), \
         patch("services.processor_exogenas.insert_exogenas_batch") as mock_insert:
        from services.processor_exogenas import procesar_exogenas
        result = procesar_exogenas([fake_file], anio=2025, org_id="org-uuid-999")

    mock_insert.assert_called_once()


def test_insert_exogenas_not_called_without_org_id(tmp_path):
    fake_file = tmp_path / "cert.pdf"
    fake_file.write_bytes(b"")

    with patch("services.processor_exogenas.extract_one", return_value=_fake_extract(fake_file)), \
         patch("services.processor_exogenas.insert_exogenas_batch") as mock_insert:
        from services.processor_exogenas import procesar_exogenas
        result = procesar_exogenas([fake_file], anio=2025)  # no org_id

    mock_insert.assert_not_called()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_processor_exogenas_org_id.py -v
```

Expected: `FAILED` or `ImportError`.

- [ ] **Step 3: Modify `services/processor_exogenas.py`**

Add import at the top:

```python
from db.database import db_available, insert_exogenas_batch
```

Find the `procesar_exogenas()` function signature. The current signature is:
```python
def procesar_exogenas(paths, on_progress=None) -> ResultadoExogenas:
```

Change it to:
```python
def procesar_exogenas(paths, anio: int = 0, on_progress=None, org_id: str | None = None) -> ResultadoExogenas:
```

Note: `anio` is already used internally in the function body — confirm the parameter name matches. If the existing code already has `anio` as a parameter, only add `org_id`.

After building `resultado` (before the `return` statement), add:

```python
    if org_id and db_available():
        insert_exogenas_batch(resultado.df_detalle, org_id)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_processor_exogenas_org_id.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add services/processor_exogenas.py tests/test_processor_exogenas_org_id.py
git commit -m "feat: add org_id param to procesar_exogenas and wire insert_exogenas_batch"
```

---

### Task 8: Pass `org_id` from session to pages

**Context:** The Streamlit pages call `procesar()` and `procesar_exogenas()`. In SaaS mode, they must pass `org_id` from `st.session_state["auth"]`.

**Files:**
- Modify: `pages/1_Procesar.py`
- Modify: `pages/6_Exogenas.py`

- [ ] **Step 1: Modify `pages/1_Procesar.py`**

After the imports, add a helper:

```python
def _get_org_id() -> str | None:
    auth = st.session_state.get("auth")
    return auth["org_id"] if auth else None
```

In the call to `procesar(archivos, grav, excl, on_progress=on_progress)`, change to:

```python
resultado = procesar(archivos, grav, excl, on_progress=on_progress, org_id=_get_org_id())
```

Both the upload-mode and folder-mode calls need this change.

- [ ] **Step 2: Modify `pages/6_Exogenas.py`**

Add the same helper:

```python
def _get_org_id() -> str | None:
    auth = st.session_state.get("auth")
    return auth["org_id"] if auth else None
```

In the call to `procesar_exogenas(...)`, add `org_id=_get_org_id()`.

- [ ] **Step 3: Verify app starts without errors locally**

```bash
python -m streamlit run Home.py &
sleep 4
curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
kill %1
```

Expected: `200` — no import errors.

- [ ] **Step 4: Commit**

```bash
git add pages/1_Procesar.py pages/6_Exogenas.py
git commit -m "feat: pass org_id from session to processor calls in pages"
```

---

## Chunk 5: Operator CLI and Railway Deployment

### Task 9: Create `manage.py`

**Files:**
- Create: `manage.py`
- Create: `tests/test_manage.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_manage.py`:

```python
"""Tests for manage.py CLI — does not require a live DB."""
import subprocess, sys


def test_manage_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "manage.py", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "init-db" in result.stdout
    assert "create-org" in result.stdout


def test_manage_unknown_command_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "manage.py", "unknown-command"],
        capture_output=True, text=True
    )
    assert result.returncode != 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_manage.py -v
```

Expected: `FAILED` — file does not exist yet.

- [ ] **Step 3: Create `manage.py`**

```python
"""manage.py — Operator CLI for TaxOps SaaS.

Usage:
    python manage.py init-db
    python manage.py create-org --name "Firma ABC" --email admin@firma.com --password secret123
"""

from __future__ import annotations

import argparse
import os
import sys


def cmd_init_db(args) -> None:
    """Run db/init.sql against DATABASE_URL to create all tables."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL env var is not set.", file=sys.stderr)
        sys.exit(1)

    from pathlib import Path
    from sqlalchemy import create_engine

    sql = Path(__file__).parent / "db" / "init.sql"
    if not sql.exists():
        print(f"ERROR: {sql} not found.", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(url, connect_args={"connect_timeout": 10})
    # Use raw psycopg2 connection — it handles multi-statement SQL correctly.
    # SQLAlchemy's conn.execute(text(...)) stops at the first semicolon.
    raw = engine.raw_connection()
    try:
        raw.cursor().execute(sql.read_text())
        raw.commit()
    finally:
        raw.close()
    print("✅ Database schema initialized.")


def cmd_create_org(args) -> None:
    """Create a new organization and its first owner user."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL env var is not set.", file=sys.stderr)
        sys.exit(1)

    from db.auth import hash_password
    from sqlalchemy import create_engine, text
    import uuid

    engine = create_engine(url, connect_args={"connect_timeout": 10})

    org_id  = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    slug    = args.name.lower().replace(" ", "-")[:50]
    hashed  = hash_password(args.password)

    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO organizations (id, slug, name, plan)
            VALUES (:id, :slug, :name, 'starter')
        """), {"id": org_id, "slug": slug, "name": args.name})

        conn.execute(text("""
            INSERT INTO users (id, org_id, email, hashed_password, role)
            VALUES (:id, :org_id, :email, :hashed_password, 'owner')
        """), {
            "id": user_id, "org_id": org_id,
            "email": args.email.strip().lower(),
            "hashed_password": hashed,
        })
        conn.commit()

    print(f"✅ Organization created.")
    print(f"   Name:  {args.name}")
    print(f"   Email: {args.email}")
    print(f"   org_id: {org_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="TaxOps operator CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize DB schema from db/init.sql")

    p_org = sub.add_parser("create-org", help="Create organization and owner user")
    p_org.add_argument("--name",     required=True, help="Organization display name")
    p_org.add_argument("--email",    required=True, help="Owner user email")
    p_org.add_argument("--password", required=True, help="Owner user password")

    args = parser.parse_args()

    if args.command == "init-db":
        cmd_init_db(args)
    elif args.command == "create-org":
        cmd_create_org(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_manage.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add manage.py tests/test_manage.py
git commit -m "feat: add manage.py operator CLI (init-db, create-org)"
```

---

### Task 10: Railway Deployment

**This task has no code changes — it is an operational checklist.**

- [ ] **Step 1: Push all changes to the main branch**

```bash
git push origin main
```

- [ ] **Step 2: Open Railway dashboard and confirm PostgreSQL service is attached**

Go to Railway project → verify a PostgreSQL service is present and its `DATABASE_URL` is available.

- [ ] **Step 3: Initialize the DB schema**

In a local terminal with Railway's DATABASE_URL exported:

```bash
export DATABASE_URL="<Railway PostgreSQL connection string>"
python manage.py init-db
```

Expected: `✅ Database schema initialized.`

Verify `exogenas_results` table was created:

```bash
python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    r = c.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\")).fetchall()
    print([row[0] for row in r])
"
```

Expected: `exogenas_results` in the list.

- [ ] **Step 4: Create the pilot client org**

```bash
python manage.py create-org \
  --name "Nombre de la Firma Contable" \
  --email correo@firma.com \
  --password "contraseña_segura_aqui"
```

Expected: `✅ Organization created.` with the org_id printed.

- [ ] **Step 5: Confirm Railway deployment uses `DATABASE_URL`**

In Railway project settings → verify `DATABASE_URL` env var is set (Railway injects this automatically when a PostgreSQL service is attached — confirm it is present).

- [ ] **Step 6: Trigger a new Railway deploy**

```bash
git commit --allow-empty -m "chore: trigger Railway redeploy"
git push origin main
```

Or use Railway dashboard "Redeploy" button.

- [ ] **Step 7: Validate pilot client login**

Open the Railway URL in an incognito window. You should see the TaxOps login form. Log in with the credentials from Step 4.

Expected: login succeeds, navigation renders, user email appears in sidebar.

- [ ] **Step 8: Validate data isolation**

Process a test invoice after logging in. Log out. Create a second test org with `manage.py create-org`. Log in as the second org. Verify the first org's invoices are not visible.

---

## Final Checklist

- [ ] `python -m pytest tests/ -v` — all tests pass locally
- [ ] Local mode (no `DATABASE_URL`): app starts with no login, no DB errors
- [ ] SaaS mode (with `DATABASE_URL`): login gate appears, auth works, data saves
- [ ] Pilot client can log in on Railway URL
- [ ] Pilot client's processed data persists across sessions
- [ ] No other org can see the pilot's data
