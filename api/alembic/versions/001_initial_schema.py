"""Initial schema baseline.

Schema created via db/init.sql (docker-entrypoint-initdb.d).
This migration is a marker only — no DDL runs here.

For fresh deployments:
  1. Apply db/init.sql (done automatically by Docker on first start)
  2. cd api/ && alembic stamp head  (tells Alembic DB is already at this revision)

For future schema changes:
  alembic revision --autogenerate -m "description"
  alembic upgrade head

Revision ID: 001
Revises:
Create Date: 2026-05-11
"""
from __future__ import annotations
from alembic import op  # noqa: F401

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
