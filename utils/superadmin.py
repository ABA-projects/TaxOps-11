"""utils/superadmin.py — Superadmin identity check via env var."""
from __future__ import annotations

import os


def is_superadmin(email: str) -> bool:
    """True when the email is listed in TAXOPS_SUPERADMIN_EMAILS.

    Configure in .env:
        TAXOPS_SUPERADMIN_EMAILS=jaime@email.com,otro@email.com
    """
    raw = os.environ.get("TAXOPS_SUPERADMIN_EMAILS", "")
    allowed = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return email.strip().lower() in allowed
