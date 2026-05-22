"""Add invitations table.

Revision ID: 003
Revises: 002
Create Date: 2026-05-12
"""
from __future__ import annotations
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS invitations (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            created_by  UUID        REFERENCES users(id) ON DELETE SET NULL,
            email       TEXT        NOT NULL,
            role        TEXT        NOT NULL DEFAULT 'contador',
            token       TEXT        NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_invitations_org ON invitations(org_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invitations;")
