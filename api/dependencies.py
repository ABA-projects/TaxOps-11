"""FastAPI dependency injection — auth guards reutilizables."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from core.config import get_settings
from core.security import decode_token

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        return {
            "user_id": payload["sub"],
            "org_id": payload["org_id"],
            "role": payload["role"],
            "email": payload["email"],
            "is_superadmin": bool(payload.get("is_superadmin", False)),
        }
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Requiere rol admin u owner")
    return user


async def require_owner(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Requiere rol owner")
    return user


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    s = get_settings()
    allowed = {e.strip().lower() for e in s.TAXOPS_SUPERADMIN_EMAILS.split(",") if e.strip()}
    if user["email"].lower() not in allowed:
        raise HTTPException(status_code=403, detail="Acceso restringido a superadmin")
    return user
