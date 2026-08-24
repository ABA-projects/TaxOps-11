"""Add novedades and leads_comerciales tables.

Revision ID: 007
Revises: 006
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS novedades (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tipo            VARCHAR(20) NOT NULL,
            titulo          TEXT NOT NULL,
            resumen         TEXT NOT NULL,
            fecha_generado  DATE NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_novedades_fecha ON novedades (fecha_generado DESC)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS leads_comerciales (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa         TEXT NOT NULL,
            sector          VARCHAR(100),
            ciudad          VARCHAR(100),
            contacto        TEXT,
            fuente_url      TEXT,
            fecha_generado  DATE NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_lead UNIQUE (empresa, ciudad)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS leads_comerciales")
    op.execute("DROP TABLE IF EXISTS novedades")
