-- ============================================================
-- TaxOps SaaS — Esquema PostgreSQL inicial
-- Ejecutado automáticamente por docker-entrypoint-initdb.d
-- ============================================================

-- Extensiones útiles
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- búsqueda fuzzy en texto

-- ────────────────────────────────────────────────────────────
-- 1. ORGANIZATIONS (multi-tenant root)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT        NOT NULL UNIQUE,          -- ej. "aba-contable"
    name          TEXT        NOT NULL,
    nit           TEXT,                                  -- NIT empresa contratante
    plan          TEXT        NOT NULL DEFAULT 'free',  -- free | starter | pro
    active        BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- 2. USERS
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           TEXT        NOT NULL UNIQUE,
    hashed_password TEXT        NOT NULL,
    full_name       TEXT,
    role            TEXT        NOT NULL DEFAULT 'contador',  -- owner | admin | contador
    active          BOOLEAN     NOT NULL DEFAULT TRUE,
    admin_requested_at TIMESTAMPTZ,                          -- solicitud de promoción a admin
    last_login_at   TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ,                             -- borrado permanente (soft-hard)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);

-- ────────────────────────────────────────────────────────────
-- 3. CLIENTES (empresas que el contador gestiona)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID    NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    nit         TEXT    NOT NULL,
    razon_social TEXT   NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, nit)
);

CREATE INDEX IF NOT EXISTS idx_clients_org ON clients(org_id);

-- ────────────────────────────────────────────────────────────
-- 4. INVOICES — tabla central de facturas procesadas
--    CUFE es el identificador único DIAN (96 hex chars)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    client_id           UUID        REFERENCES clients(id),
    -- Campos DIAN
    cufe                TEXT        NOT NULL,
    folio               TEXT,
    tipo                TEXT,        -- FE | NC | ND | DS | PE | DE
    fecha               DATE,
    -- Emisor
    nit_emisor          TEXT,
    nombre_emisor       TEXT,
    -- Receptor
    nit_receptor        TEXT,
    nombre_receptor     TEXT,
    -- Montos (en COP, 2 decimales)
    subtotal            NUMERIC(18,2),
    base_iva_19         NUMERIC(18,2),
    iva_19              NUMERIC(18,2),
    base_iva_5          NUMERIC(18,2),
    iva_5               NUMERIC(18,2),
    no_gravado          NUMERIC(18,2),
    total               NUMERIC(18,2),
    retencion_fuente    NUMERIC(18,2),
    -- Metadata procesamiento
    fuente              TEXT,        -- nombre del archivo origen
    procesado_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    periodo             TEXT,        -- YYYY-MM calculado de fecha
    -- Constraint anti-duplicados por organización
    UNIQUE(org_id, cufe)
);

CREATE INDEX IF NOT EXISTS idx_invoices_org       ON invoices(org_id);
CREATE INDEX IF NOT EXISTS idx_invoices_client    ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_periodo   ON invoices(org_id, periodo);
CREATE INDEX IF NOT EXISTS idx_invoices_nit_em    ON invoices(org_id, nit_emisor);
CREATE INDEX IF NOT EXISTS idx_invoices_cufe_trgm ON invoices USING gin(cufe gin_trgm_ops);

-- ────────────────────────────────────────────────────────────
-- 5. PROCESSING_SESSIONS — historial de cargas
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS processing_sessions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID        REFERENCES users(id),
    total_archivos  INTEGER     NOT NULL DEFAULT 0,
    procesados      INTEGER     NOT NULL DEFAULT 0,
    errores         INTEGER     NOT NULL DEFAULT 0,
    nuevas          INTEGER     NOT NULL DEFAULT 0,   -- facturas nuevas (no duplicadas)
    duplicadas      INTEGER     NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running'  -- running | done | failed
);

CREATE INDEX IF NOT EXISTS idx_sessions_org ON processing_sessions(org_id);

-- ────────────────────────────────────────────────────────────
-- 6. AUTORRETENEDORES — tabla en lugar de archivo plano
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS autorretenedores (
    id          SERIAL  PRIMARY KEY,
    nit         TEXT    NOT NULL UNIQUE,
    razon_social TEXT,
    vigente     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- 7. INGRESOS_PRORATEO — reemplaza el text_area de Streamlit
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingresos_prorateo (
    id                  SERIAL  PRIMARY KEY,
    org_id              UUID    NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    periodo             TEXT    NOT NULL,   -- YYYY-MM
    ingresos_gravados   NUMERIC(18,2) NOT NULL DEFAULT 0,
    ingresos_excluidos  NUMERIC(18,2) NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, periodo)
);

-- ────────────────────────────────────────────────────────────
-- 8. Trigger: updated_at automático
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_organizations_updated BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_autorretenedores_updated BEFORE UPDATE ON autorretenedores
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_ingresos_updated BEFORE UPDATE ON ingresos_prorateo
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ────────────────────────────────────────────────────────────
-- 9. Organización demo para desarrollo local
-- ────────────────────────────────────────────────────────────
INSERT INTO organizations (slug, name, plan)
VALUES ('demo', 'TaxOps Demo', 'pro')
ON CONFLICT (slug) DO NOTHING;

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

-- ────────────────────────────────────────────────────────────
-- GROUPS — grupos de usuarios con permisos por módulo
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS groups (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    description TEXT,
    modules     TEXT[]      NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, name)
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id    UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

-- ────────────────────────────────────────────────────────────
-- AUDIT_LOGS — trazabilidad completa de acciones
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID        REFERENCES users(id) ON DELETE SET NULL,
    user_email      TEXT,
    action          TEXT        NOT NULL,
    module          TEXT        NOT NULL DEFAULT 'admin',
    resource_type   TEXT,
    resource_id     TEXT,
    details         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_org_created ON audit_logs (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id);
