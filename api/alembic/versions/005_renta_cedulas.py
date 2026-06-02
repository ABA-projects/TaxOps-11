"""Add new fields to renta_declaraciones for Semana 4.

Revision ID: 005
Revises: 004
Create Date: 2026-06-02
"""
from __future__ import annotations

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [
        ("aportes_pension",    "NUMERIC(18,2)", "0"),
        ("afc_fvp",            "NUMERIC(18,2)", "0"),
        ("intereses_vivienda", "NUMERIC(18,2)", "0"),
        ("medicina_prepagada", "NUMERIC(18,2)", "0"),
        ("dependientes",       "INTEGER",        "0"),
        ("tipo_ganancia",      "TEXT",           "NULL"),
        ("pasivos",            "NUMERIC(18,2)", "0"),
        ("ajuste_manual",      "JSONB",          "NULL"),
    ]
    for col, tipo, default in cols:
        default_sql = f"DEFAULT {default}" if default != "NULL" else ""
        op.execute(
            f"ALTER TABLE renta_declaraciones "
            f"ADD COLUMN IF NOT EXISTS {col} {tipo} {default_sql};"
        )


def downgrade() -> None:
    for col in [
        "aportes_pension", "afc_fvp", "intereses_vivienda",
        "medicina_prepagada", "dependientes", "tipo_ganancia",
        "pasivos", "ajuste_manual",
    ]:
        op.execute(
            f"ALTER TABLE renta_declaraciones DROP COLUMN IF EXISTS {col};"
        )
