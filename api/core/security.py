"""JWT helpers — create y decode tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt

from .config import get_settings

_s = get_settings()


def create_access_token(sub: str, org_id: str, role: str, email: str) -> str:
    allowed = {e.strip().lower() for e in _s.TAXOPS_SUPERADMIN_EMAILS.split(",") if e.strip()}
    return jwt.encode(
        {
            "sub": sub,
            "org_id": org_id,
            "role": role,
            "email": email,
            "is_superadmin": email.lower() in allowed,
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=_s.ACCESS_TOKEN_EXPIRE_MINUTES),
        },
        _s.SECRET_KEY,
        algorithm=_s.ALGORITHM,
    )


def create_refresh_token(sub: str) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(days=_s.REFRESH_TOKEN_EXPIRE_DAYS),
        },
        _s.SECRET_KEY,
        algorithm=_s.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """Raises JWTError if invalid or expired."""
    return jwt.decode(token, _s.SECRET_KEY, algorithms=[_s.ALGORITHM])
