"""Add nomina empleados, periodos and detalle tables.

Revision ID: 006
Revises: 005
Create Date: 2026-06-20
"""
from __future__ import annotations

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS empleados (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            cedula      VARCHAR(20)  NOT NULL DEFAULT '',
            nombre      VARCHAR(200) NOT NULL,
            cargo       VARCHAR(200) NOT NULL DEFAULT '',
            salario     NUMERIC(15,2) NOT NULL DEFAULT 0,
            clase_riesgo_arl INTEGER NOT NULL DEFAULT 1,
            tipo_salario     VARCHAR(20)  NOT NULL DEFAULT 'ordinario',
            fecha_ingreso    DATE,
            email            VARCHAR(255) NOT NULL DEFAULT '',
            activo           BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS nomina_periodos (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            periodo          VARCHAR(7)   NOT NULL,
            tipo             VARCHAR(20)  NOT NULL DEFAULT 'mensual',
            estado           VARCHAR(20)  NOT NULL DEFAULT 'borrador',
            total_devengado  NUMERIC(15,2) NOT NULL DEFAULT 0,
            total_deducciones NUMERIC(15,2) NOT NULL DEFAULT 0,
            total_neto       NUMERIC(15,2) NOT NULL DEFAULT 0,
            carga_patronal   NUMERIC(15,2) NOT NULL DEFAULT 0,
            costo_empresa    NUMERIC(15,2) NOT NULL DEFAULT 0,
            empleados_count  INTEGER NOT NULL DEFAULT 0,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (org_id, periodo, tipo)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS nomina_detalle (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            periodo_id   UUID NOT NULL REFERENCES nomina_periodos(id) ON DELETE CASCADE,
            empleado_id  UUID NOT NULL REFERENCES empleados(id),
            org_id       UUID NOT NULL REFERENCES organizations(id),
            resultado    JSONB NOT NULL DEFAULT '{}',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (periodo_id, empleado_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_empleados_org ON empleados(org_id) WHERE activo = TRUE")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_empleados_org_cedula "
        "ON empleados(org_id, cedula) WHERE cedula != ''"
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_nomina_periodos_org ON nomina_periodos(org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_nomina_detalle_periodo ON nomina_detalle(periodo_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS nomina_detalle")
    op.execute("DROP TABLE IF EXISTS nomina_periodos")
    op.execute("DROP TABLE IF EXISTS empleados")
