"""manage.py — Operator CLI for TaxOps SaaS.

Usage:
    python manage.py init-db
    python manage.py create-org --name "Firma ABC" --email admin@firma.com --password secret123
"""

from __future__ import annotations

import argparse
import os
import sys


def cmd_init_db(args) -> None:
    """Run db/init.sql against DATABASE_URL to create all tables."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL env var is not set.", file=sys.stderr)
        sys.exit(1)

    from pathlib import Path
    from sqlalchemy import create_engine

    sql_path = Path(__file__).parent / "db" / "init.sql"
    if not sql_path.exists():
        print(f"ERROR: {sql_path} not found.", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(url, connect_args={"connect_timeout": 10})
    # Use raw psycopg2 connection — handles multi-statement SQL correctly.
    # SQLAlchemy text() stops at the first semicolon.
    raw = engine.raw_connection()
    try:
        raw.cursor().execute(sql_path.read_text())
        raw.commit()
    finally:
        raw.close()
    print("✅ Database schema initialized.")


def cmd_create_org(args) -> None:
    """Create a new organization and its first owner user."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL env var is not set.", file=sys.stderr)
        sys.exit(1)

    from db.auth import hash_password
    from sqlalchemy import create_engine, text
    import uuid

    engine = create_engine(url, connect_args={"connect_timeout": 10})
    org_id  = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    slug    = args.name.lower().replace(" ", "-")[:50]
    hashed  = hash_password(args.password)

    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO organizations (id, slug, name, plan)
            VALUES (:id, :slug, :name, 'starter')
        """), {"id": org_id, "slug": slug, "name": args.name})

        conn.execute(text("""
            INSERT INTO users (id, org_id, email, hashed_password, role)
            VALUES (:id, :org_id, :email, :hashed_password, 'owner')
        """), {
            "id": user_id, "org_id": org_id,
            "email": args.email.strip().lower(),
            "hashed_password": hashed,
        })
        conn.commit()

    print("✅ Organization created.")
    print(f"   Name:   {args.name}")
    print(f"   Email:  {args.email}")
    print(f"   org_id: {org_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="TaxOps operator CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Initialize DB schema from db/init.sql")

    p_org = sub.add_parser("create-org", help="Create organization and owner user")
    p_org.add_argument("--name",     required=True, help="Organization display name")
    p_org.add_argument("--email",    required=True, help="Owner user email")
    p_org.add_argument("--password", required=True, help="Owner user password")

    args = parser.parse_args()
    if args.command == "init-db":
        cmd_init_db(args)
    elif args.command == "create-org":
        cmd_create_org(args)


if __name__ == "__main__":
    main()
