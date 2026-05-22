# TaxOps SaaS MVP — Design Spec

**Date:** 2026-05-06  
**Status:** Approved  
**Scope:** Convert TaxOps from local app to billable SaaS for accounting firms

---

## Context

TaxOps processes Colombian DIAN invoices (PDF/XML) and generates Exógenas reports. It is currently deployed on Railway (`proyecto-facturas-production.up.railway.app`). One pilot client — an accounting firm that manages multiple end-clients — has agreed to pay once the product is ready.

**Goal:** Add auth + multi-tenancy + persistent storage to Railway deployment so the pilot client can log in, use the app with their data isolated, and pay a monthly subscription.

---

## Architecture

```
[Accounting Firm User]  →  Login  →  [TaxOps on Railway]  →  PostgreSQL
                                              │
                                   org_id filters all data
                                   (each firm sees only their own)
```

**Two-mode codebase:**

| Mode | Condition | Behavior |
|------|-----------|----------|
| Local / offline | `DATABASE_URL` not set | App opens directly, no login, no DB |
| SaaS / Railway | `DATABASE_URL` set | Login screen appears, auth enforced, data persisted |

**Important:** `db/database.py` must lazy-initialize the SQLAlchemy engine — only create the engine when `DATABASE_URL` is present in the environment, not at module import time. This ensures local installs (without PostgreSQL) never throw a connection error on startup.

The `TAXOPS_ORG_ID` env var (used in Docker local dev) is deprecated in SaaS mode — `org_id` comes from the authenticated user session, not from an env var.

---

## Dependencies

Add to `requirements.txt` and `pyproject.toml`:

```
sqlalchemy>=2.0
psycopg2-binary>=2.9
streamlit-authenticator==0.3.3
```

`sqlalchemy` and `psycopg2-binary` were removed in a previous refactor to simplify local usage. They are re-added with the two-mode guard: the engine is only initialized when `DATABASE_URL` is set, so local installs remain lightweight.

`streamlit-authenticator==0.3.3` is pinned to the v0.3.x API (uses `stauth.Authenticate` with a credentials dict from DB, not YAML config).

---

## Data Model

Schema is defined in `db/init.sql` — do not redefine it. The relevant tables already exist:

- `organizations` — one row per accounting firm
- `users` — linked to `organizations.id` via `org_id`
- `invoices` — already has `org_id` column for multi-tenancy
- `processing_sessions` — already has `org_id`

**New table to add to `db/init.sql`:**

```sql
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
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_exogenas_results_org_id ON exogenas_results(org_id);
```

`raw_row` stores the full row as JSON for forward compatibility. Structured columns cover the most-queried fields.

---

## Auth Flow

**Login:**
1. User submits email + password
2. `db/auth.py` queries `users` table: `SELECT id, org_id, role, hashed_password FROM users WHERE email = ? AND active = true`
3. Verify password with bcrypt (same library as `streamlit-authenticator`) against `hashed_password` column
4. On success: store `{user_id, org_id, role, email}` in `st.session_state["auth"]`
5. App renders normally; all DB calls receive `org_id` from session

**Logout:**
- `streamlit-authenticator` logout widget clears `st.session_state["auth"]`
- App re-renders to login screen on next rerun

**Session contract — `st.session_state["auth"]`:**
```python
{
    "user_id": str,   # UUID
    "org_id":  str,   # UUID — used in all DB queries
    "role":    str,   # "owner" | "contador"
    "email":   str,
}
```

---

## Multi-tenancy in Services

**`services/processor.py`:** The `org_id` parameter already exists (currently a no-op). The change is to call `insert_invoices_batch(df, org_id)` when `org_id` is provided and DB is available.

**`services/processor_exogenas.py`:** No `org_id` parameter exists yet. Add `org_id: str | None = None` to `procesar_exogenas()` signature and call `insert_exogenas_batch(df, org_id)` when provided.

**`db/database.py` — new function `insert_exogenas_batch`:**
```python
def insert_exogenas_batch(df: pd.DataFrame, org_id: str, session_id: str | None = None) -> None:
    """Insert exogenas detail rows into exogenas_results. One row per df row."""
```
Maps `df_detalle` columns to `exogenas_results` columns. Uses `ON CONFLICT DO NOTHING` on `(org_id, nit, concepto, anio)` to avoid duplicates on re-processing. `session_id` is optional for MVP — pass `None` until `processing_sessions` is wired for exógenas.

Both services remain fully functional without `org_id` (local mode, no DB).

---

## Operator CLI — `manage.py`

```bash
# Create a new organization and its first owner user
python manage.py create-org --name "Firma Contable ABC" --email admin@firma.com --password secret123

# Initialize DB schema (run once against Railway PostgreSQL)
python manage.py init-db
```

`create-org` hashes the password with bcrypt via `streamlit-authenticator`'s `Hasher` class to guarantee hash compatibility with the login flow.

`init-db` runs `db/init.sql` against `DATABASE_URL`. This is required before first Railway deploy because Railway managed PostgreSQL does not auto-run init scripts.

---

## Railway Deployment

1. Run `python manage.py init-db` against Railway PostgreSQL to create all tables
2. Set env var `DATABASE_URL` in Railway project settings
3. Deploy — app will boot in SaaS mode automatically
4. Run `python manage.py create-org` to create the pilot client's account
5. Share Railway URL + credentials with pilot client

---

## Implementation Order

1. Add `sqlalchemy`, `psycopg2-binary`, `streamlit-authenticator==0.3.3` to `requirements.txt` and `pyproject.toml`
2. Refactor `db/database.py` to lazy-initialize engine (only when `DATABASE_URL` set)
3. Add `exogenas_results` table DDL to `db/init.sql`
4. Create `db/auth.py` — user lookup + bcrypt verification, returns session dict
5. Add login gate to `Home.py` — only when `DATABASE_URL` present; logout widget in sidebar
6. Wire `org_id` in `services/processor.py` — call `insert_invoices_batch()` when `org_id` provided
7. Add `org_id` param to `services/processor_exogenas.py` — call `insert_exogenas_batch()` when provided
8. Create `manage.py` with `init-db` and `create-org` commands
9. Run `manage.py init-db` + `manage.py create-org` against Railway
10. Deploy to Railway and validate pilot client login

---

## Success Criteria

- Pilot client logs in on Railway URL with their credentials
- Their processed invoices and exógenas are saved and visible on next login
- No other org can see their data
- Local installs work without any PostgreSQL (no `DATABASE_URL` set)
- Pilot signs payment agreement for 3-month discounted period
