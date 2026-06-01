"""Add renta module tables.

Revision ID: 004
Revises: 003
Create Date: 2026-06-01
"""
from __future__ import annotations
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS contribuyentes (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            responsable_id   UUID REFERENCES users(id) ON DELETE SET NULL,
            tipo_doc         VARCHAR(5)   NOT NULL DEFAULT '13',
            numero_doc       VARCHAR(20)  NOT NULL,
            nombre_completo  VARCHAR(200) NOT NULL,
            email            VARCHAR(150),
            telefono         VARCHAR(20),
            direccion        TEXT,
            ciudad           VARCHAR(100),
            año_gravable     INTEGER      NOT NULL,
            estado           VARCHAR(30)  NOT NULL DEFAULT 'pendiente_docs',
            observaciones    TEXT,
            datos_tributarios JSONB       DEFAULT '{}',
            created_at       TIMESTAMPTZ  DEFAULT NOW(),
            updated_at       TIMESTAMPTZ  DEFAULT NOW(),
            CONSTRAINT uq_contribuyente_año UNIQUE (org_id, numero_doc, año_gravable)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_contrib_org ON contribuyentes (org_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contrib_estado ON contribuyentes (org_id, estado);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contrib_responsable ON contribuyentes (responsable_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS renta_documentos (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            contribuyente_id         UUID NOT NULL REFERENCES contribuyentes(id) ON DELETE CASCADE,
            org_id                   UUID NOT NULL,
            s3_key                   TEXT NOT NULL,
            filename                 VARCHAR(255) NOT NULL,
            mime_type                VARCHAR(100),
            size_bytes               BIGINT,
            categoria                VARCHAR(50)  DEFAULT 'otros',
            carpeta_virtual          VARCHAR(50)  DEFAULT '08_Otros',
            confianza_clasificacion  FLOAT        DEFAULT 0,
            datos_extraidos          JSONB        DEFAULT '{}',
            texto_ocr                TEXT,
            estado_ocr               VARCHAR(20)  DEFAULT 'pendiente',
            estado_validacion        VARCHAR(20)  DEFAULT 'pendiente',
            version                  INTEGER      DEFAULT 1,
            created_at               TIMESTAMPTZ  DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rdoc_contrib ON renta_documentos (contribuyente_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rdoc_org_cat ON renta_documentos (org_id, categoria);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rdoc_estado ON renta_documentos (estado_ocr);")

    op.execute("""
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
            pdf_path              TEXT,
            inconsistencias       JSONB DEFAULT '[]',
            detalle_calculo       JSONB DEFAULT '{}',
            updated_at            TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_decl_año UNIQUE (contribuyente_id, año_gravable)
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS reglas_tributarias (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            año_gravable  INTEGER     NOT NULL,
            tipo_regla    VARCHAR(50) NOT NULL,
            concepto      VARCHAR(100) NOT NULL,
            parametros    JSONB       NOT NULL,
            fuente_legal  TEXT,
            CONSTRAINT uq_regla UNIQUE (año_gravable, tipo_regla, concepto)
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS renta_jobs (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            contribuyente_id UUID REFERENCES contribuyentes(id) ON DELETE CASCADE,
            doc_id           UUID REFERENCES renta_documentos(id) ON DELETE CASCADE,
            tipo             VARCHAR(30) NOT NULL,
            estado           VARCHAR(20) DEFAULT 'pendiente',
            progreso         INTEGER     DEFAULT 0,
            resultado        JSONB,
            error            TEXT,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rjob_contrib ON renta_jobs (contribuyente_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rjob_estado ON renta_jobs (estado);")

    # Seed: reglas tributarias 2025
    op.execute("""
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
          "porcentaje": 0.25, "limite_mensual_uvt": 240,
          "concepto": "Renta exenta laboral Art 206 num 10 ET"
        }', 'Art 206 ET'),
        (2025, 'deduccion', 'intereses_vivienda', '{
          "limite_uvt": 1200, "concepto": "Intereses crédito hipotecario Art 119 ET"
        }', 'Art 119 ET'),
        (2025, 'deduccion', 'dependientes', '{
          "porcentaje": 0.10, "limite_mensual_uvt": 32,
          "concepto": "Deducción por dependientes Art 387 ET"
        }', 'Art 387 ET')
        ON CONFLICT (año_gravable, tipo_regla, concepto) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS renta_jobs CASCADE;")
    op.execute("DROP TABLE IF EXISTS renta_declaraciones CASCADE;")
    op.execute("DROP TABLE IF EXISTS renta_documentos CASCADE;")
    op.execute("DROP TABLE IF EXISTS contribuyentes CASCADE;")
    op.execute("DROP TABLE IF EXISTS reglas_tributarias CASCADE;")
