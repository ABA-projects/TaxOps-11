"""Add audit_logs, groups, user_groups; add deleted_at to users.

Revision ID: 002
Revises: 001
Create Date: 2026-05-12
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name        TEXT        NOT NULL,
            description TEXT,
            modules     TEXT[]      NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (org_id, name)
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_id    UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, group_id)
        );
    """)

    op.execute("""
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
        CREATE INDEX IF NOT EXISTS idx_audit_logs_org_created
            ON audit_logs (org_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_user
            ON audit_logs (user_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs;")
    op.execute("DROP TABLE IF EXISTS user_groups;")
    op.execute("DROP TABLE IF EXISTS groups;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at;")
