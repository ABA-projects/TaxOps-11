"""db/auth.py — User authentication and session helpers."""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """True if plain matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _build_session(row: dict) -> dict:
    """Convert a DB user row to the st.session_state["auth"] contract."""
    return {
        "user_id": str(row["id"]),
        "org_id":  str(row["org_id"]),
        "role":    str(row["role"]),
        "email":   str(row["email"]),
    }


def authenticate(email: str, password: str) -> dict | None:
    """Look up user by email and verify password. Returns session dict or None."""
    from db.database import db_available, get_db
    if not db_available():
        return None

    from sqlalchemy import text
    try:
        with get_db() as db:
            row = db.execute(
                text("""
                    SELECT id, org_id, role, email, hashed_password
                    FROM users
                    WHERE email = :email AND active = TRUE
                """),
                {"email": email.strip().lower()},
            ).mappings().fetchone()
    except Exception:
        return None

    if row is None:
        return None
    if not verify_password(password, row["hashed_password"]):
        return None

    try:
        with get_db() as db:
            db.execute(
                text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
                {"id": row["id"]},
            )
    except Exception:
        pass

    return _build_session(dict(row))
