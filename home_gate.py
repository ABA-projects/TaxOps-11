"""home_gate.py — Pure helpers for Home.py login gate.

Testable without Streamlit. Home.py imports these functions.
"""
from __future__ import annotations

import os

_REQUIRED_AUTH_KEYS = {"user_id", "org_id", "role", "email"}


def login_required() -> bool:
    """Return True when DATABASE_URL is set — meaning the app runs in SaaS mode.

    When DATABASE_URL is absent (local / demo mode) no authentication is needed.
    """
    return bool(os.environ.get("DATABASE_URL"))


def get_auth_session(session_state: dict) -> dict | None:
    """Extract and validate the auth dict from ``session_state``.

    Args:
        session_state: A dict-like object (e.g. st.session_state or a plain dict).

    Returns:
        The auth dict if all required keys are present, otherwise ``None``.
    """
    auth = session_state.get("auth")
    if not auth:
        return None
    if not _REQUIRED_AUTH_KEYS.issubset(auth.keys()):
        return None
    return auth
