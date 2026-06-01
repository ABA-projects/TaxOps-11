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

-- ============================================================
-- MÓDULO RENTA — Declaración de Renta Personas Naturales
-- ============================================================

-- ─── Contribuyentes (personas naturales declarantes) ─────────────────────────
CREATE TABLE IF NOT EXISTS contribuyentes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    responsable_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    tipo_doc         VARCHAR(5)   NOT NULL DEFAULT '13',
    -- 13=CC, 22=CE, 41=PA
    numero_doc       VARCHAR(20)  NOT NULL,
    nombre_completo  VARCHAR(200) NOT NULL,
    email            VARCHAR(150),
    telefono         VARCHAR(20),
    direccion        TEXT,
    ciudad           VARCHAR(100),
    año_gravable     INTEGER      NOT NULL,
    estado           VARCHAR(30)  NOT NULL DEFAULT 'pendiente_docs',
    -- pendiente_docs | en_proceso | revision | completado | presentado
    observaciones    TEXT,
    datos_tributarios JSONB       DEFAULT '{}',
    created_at       TIMESTAMPTZ  DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  DEFAULT NOW(),
    CONSTRAINT uq_contribuyente_año UNIQUE (org_id, numero_doc, año_gravable)
);

CREATE INDEX IF NOT EXISTS idx_contrib_org ON contribuyentes (org_id);
CREATE INDEX IF NOT EXISTS idx_contrib_estado ON contribuyentes (org_id, estado);
CREATE INDEX IF NOT EXISTS idx_contrib_responsable ON contribuyentes (responsable_id);

-- ─── Documentos de cada contribuyente ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS renta_documentos (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contribuyente_id         UUID NOT NULL REFERENCES contribuyentes(id) ON DELETE CASCADE,
    org_id                   UUID NOT NULL,
    s3_key                   TEXT NOT NULL,
    filename                 VARCHAR(255) NOT NULL,
    mime_type                VARCHAR(100),
    size_bytes               BIGINT,
    categoria                VARCHAR(50)  DEFAULT 'otros',
    -- identificacion | ingresos | bancos | patrimonio | bienes | salud | pensiones | tributario | otros
    carpeta_virtual          VARCHAR(50)  DEFAULT '08_Otros',
    confianza_clasificacion  FLOAT        DEFAULT 0,
    datos_extraidos          JSONB        DEFAULT '{}',
    texto_ocr                TEXT,
    estado_ocr               VARCHAR(20)  DEFAULT 'pendiente',
    -- pendiente | procesando | completado | error
    estado_validacion        VARCHAR(20)  DEFAULT 'pendiente',
    version                  INTEGER      DEFAULT 1,
    created_at               TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rdoc_contrib ON renta_documentos (contribuyente_id);
CREATE INDEX IF NOT EXISTS idx_rdoc_org_cat ON renta_documentos (org_id, categoria);
CREATE INDEX IF NOT EXISTS idx_rdoc_estado ON renta_documentos (estado_ocr);

-- ─── Declaración (datos tributarios consolidados) ─────────────────────────────
CREATE TABLE IF NOT EXISTS renta_declaraciones (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contribuyente_id      UUID NOT NULL REFERENCES contribuyentes(id) ON DELETE CASCADE,
    año_gravable          INTEGER NOT NULL,
    patrimonio_bruto      NUMERIC(18,2) DEFAULT 0,
    patrimonio_liquido    NUMERIC(18,2) DEFAULT 0,
    ingresos_laborales    NUMERIC(18,2) DEFAULT 0,
    rentas_capital        NUMERIC(18,2) DEFAULT 0,
    rentas_no_laborales   NUMERIC(18,2) DEFAULT 0,
    dividendos            NUMERIC(18,2) DEFAULT 0,
    ganancias_ocasionales NUMERIC(18,2) DEFAULT 0,
    rentas_exentas        NUMERIC(18,2) DEFAULT 0,
    deducciones           NUMERIC(18,2) DEFAULT 0,
    retenciones           NUMERIC(18,2) DEFAULT 0,
    impuesto_cargo        NUMERIC(18,2) DEFAULT 0,
    saldo_pagar           NUMERIC(18,2) DEFAULT 0,
    saldo_favor           NUMERIC(18,2) DEFAULT 0,
    estado                VARCHAR(20) DEFAULT 'borrador',
    -- borrador | revision | aprobado | presentado
    pdf_path              TEXT,
    inconsistencias       JSONB DEFAULT '[]',
    detalle_calculo       JSONB DEFAULT '{}',
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_decl_año UNIQUE (contribuyente_id, año_gravable)
);

-- ─── Reglas tributarias parametrizables por año ───────────────────────────────
CREATE TABLE IF NOT EXISTS reglas_tributarias (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    año_gravable  INTEGER     NOT NULL,
    tipo_regla    VARCHAR(50) NOT NULL,
    -- uvt | tarifa_renta | renta_exenta | deduccion | patrimonio
    concepto      VARCHAR(100) NOT NULL,
    parametros    JSONB       NOT NULL,
    fuente_legal  TEXT,
    CONSTRAINT uq_regla UNIQUE (año_gravable, tipo_regla, concepto)
);

-- ─── Jobs de procesamiento asíncrono ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS renta_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contribuyente_id UUID REFERENCES contribuyentes(id) ON DELETE CASCADE,
    doc_id           UUID REFERENCES renta_documentos(id) ON DELETE CASCADE,
    tipo             VARCHAR(30) NOT NULL,
    -- ocr | clasificacion | declaracion | form210 | export
    estado           VARCHAR(20) DEFAULT 'pendiente',
    progreso         INTEGER     DEFAULT 0,
    resultado        JSONB,
    error            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rjob_contrib ON renta_jobs (contribuyente_id);
CREATE INDEX IF NOT EXISTS idx_rjob_estado ON renta_jobs (estado);

-- ─── Datos semilla: reglas tributarias 2025 ──────────────────────────────────
INSERT INTO reglas_tributarias (año_gravable, tipo_regla, concepto, parametros, fuente_legal)
VALUES
(2025, 'uvt', 'valor_uvt', '{"uvt": 49799}', 'Resolución DIAN 187/2024'),
(2025, 'tarifa_renta', 'tabla_art241', '{
  "tramos": [
    {"desde_uvt": 0,     "hasta_uvt": 1090,  "tarifa_marginal": 0,    "impuesto_base_uvt": 0},
    {"desde_uvt": 1090,  "hasta_uvt": 1700,  "tarifa_marginal": 0.19, "impuesto_base_uvt": 0},
    {"desde_uvt": 1700,  "hasta_uvt": 4100,  "tarifa_marginal": 0.28, "impuesto_base_uvt": 116},
    {"desde_uvt": 4100,  "hasta_uvt": 8670,  "tarifa_marginal": 0.33, "impuesto_base_uvt": 788},
    {"desde_uvt": 8670,  "hasta_uvt": 18970, "tarifa_marginal": 0.35, "impuesto_base_uvt": 2296},
    {"desde_uvt": 18970, "hasta_uvt": 31000, "tarifa_marginal": 0.37, "impuesto_base_uvt": 5901},
    {"desde_uvt": 31000, "hasta_uvt": null,  "tarifa_marginal": 0.39, "impuesto_base_uvt": 10352}
  ]
}', 'Art 241 ET mod. Ley 2277/2022'),
(2025, 'renta_exenta', 'laboral_25pct', '{
  "porcentaje": 0.25,
  "limite_mensual_uvt": 240,
  "concepto": "Renta exenta laboral Art 206 num 10 ET"
}', 'Art 206 ET'),
(2025, 'deduccion', 'intereses_vivienda', '{
  "limite_uvt": 1200,
  "concepto": "Intereses crédito hipotecario Art 119 ET"
}', 'Art 119 ET'),
(2025, 'deduccion', 'dependientes', '{
  "porcentaje": 0.10,
  "limite_mensual_uvt": 32,
  "concepto": "Deducción por dependientes Art 387 ET"
}', 'Art 387 ET')
ON CONFLICT (año_gravable, tipo_regla, concepto) DO NOTHING;
