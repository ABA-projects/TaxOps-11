"""Auth router — login, register, refresh, me, logout, Google OAuth."""
from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError

from core.security import create_access_token, create_refresh_token, decode_token
from dependencies import get_current_user
from schemas import (
    AcceptInviteRequest,
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _slug_from_name(name: str) -> str:
    """Convert org name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:40] + "-" + secrets.token_hex(3)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    from db.auth import authenticate

    user = authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # _build_session returns "user_id" not "id"
    access = create_access_token(
        sub=str(user["user_id"]),
        org_id=str(user["org_id"]),
        role=user["role"],
        email=user["email"],
    )
    refresh = create_refresh_token(sub=str(user["user_id"]))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest) -> TokenResponse:
    """Self-service registration — creates org + owner user."""
    from db.database import get_db
    from db.auth import hash_password
    from sqlalchemy import text

    try:
        with get_db() as db:
            # Check email not taken
            exists = db.execute(
                text("SELECT id FROM users WHERE email = :e"),
                {"e": body.email},
            ).fetchone()
            if exists:
                raise HTTPException(status_code=409, detail="El correo ya está registrado")

            slug = _slug_from_name(body.org_name)
            org = db.execute(
                text("""
                    INSERT INTO organizations (slug, name, plan)
                    VALUES (:s, :n, 'free')
                    RETURNING id
                """),
                {"s": slug, "n": body.org_name},
            ).mappings().fetchone()

            hashed = hash_password(body.password)
            user = db.execute(
                text("""
                    INSERT INTO users (org_id, email, hashed_password, full_name, role)
                    VALUES (:o, :e, :h, :f, 'auxiliar_contable')
                    RETURNING id, org_id, role, email
                """),
                {"o": org["id"], "e": body.email, "h": hashed, "f": body.full_name or ""},
            ).mappings().fetchone()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Error al crear la cuenta") from exc

    access = create_access_token(
        sub=str(user["id"]),
        org_id=str(user["org_id"]),
        role=user["role"],
        email=user["email"],
    )
    refresh = create_refresh_token(sub=str(user["id"]))
    return TokenResponse(access_token=access, refresh_token=refresh)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google/status")
async def google_status() -> dict:
    """Indica si Google OAuth está configurado (sin credenciales)."""
    from core.config import get_settings
    return {"available": bool(get_settings().GOOGLE_CLIENT_ID)}


@router.get("/google")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect to Google OAuth consent screen."""
    from core.config import get_settings
    s = get_settings()
    if not s.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth no configurado")

    import base64 as _b64
    import json as _json
    # Embed frontend URL in state so callback doesn't depend on env vars
    state_payload = _b64.urlsafe_b64encode(
        _json.dumps({"n": secrets.token_urlsafe(8), "f": s.FRONTEND_URL}).encode()
    ).decode().rstrip("=")
    redirect_uri = f"{s.API_BASE_URL}/auth/google/callback"  # Google llama al backend
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={s.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        f"&state={state_payload}"
        "&access_type=offline"
        "&prompt=select_account"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str, state: str | None = None) -> dict:
    """Exchange Google code for tokens, create/find user, return JWT."""
    import httpx
    from core.config import get_settings
    from db.database import get_db
    from sqlalchemy import text

    s = get_settings()
    if not s.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth no configurado")

    # Recover frontend URL from state early (needed for redirects on error/no-account)
    import base64 as _b64
    import json as _json
    try:
        padded = (state or "") + "==" * (4 - len((state or "")) % 4)
        frontend_base = _json.loads(_b64.urlsafe_b64decode(padded)).get("f", s.FRONTEND_URL)
    except Exception:
        frontend_base = s.FRONTEND_URL

    redirect_uri = f"{s.API_BASE_URL}/auth/google/callback"  # debe coincidir con lo enviado a Google

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": s.GOOGLE_CLIENT_ID,
                "client_secret": s.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if not token_res.is_success:
        raise HTTPException(status_code=400, detail="Error al autenticar con Google")

    id_token_str = token_res.json().get("id_token", "")

    # Verify ID token via Google's tokeninfo endpoint (server-side, full signature check)
    async with httpx.AsyncClient() as client:
        info_res = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token_str},
        )
    if not info_res.is_success:
        raise HTTPException(status_code=400, detail="Token de Google inválido")
    google_user = info_res.json()
    if google_user.get("aud") != s.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Token de Google inválido")

    email = google_user.get("email", "").lower()
    full_name = google_user.get("name", "")
    if not email:
        raise HTTPException(status_code=400, detail="Google no proporcionó email")

    try:
        with get_db() as db:
            row = db.execute(
                text("SELECT id, org_id, role, email FROM users WHERE email = :e AND active = TRUE"),
                {"e": email},
            ).mappings().fetchone()

            if row is None:
                import urllib.parse
                signup_url = (
                    f"{frontend_base.rstrip('/')}/signup/google"
                    f"?email={urllib.parse.quote(email)}"
                    f"&name={urllib.parse.quote(full_name)}"
                )
                return RedirectResponse(signup_url)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Error de base de datos") from exc

    access = create_access_token(
        sub=str(row["id"]),
        org_id=str(row["org_id"]),
        role=row["role"],
        email=row["email"],
    )
    refresh = create_refresh_token(sub=str(row["id"]))

    # Recover frontend URL from state (avoids relying on env var at callback time)
    frontend_url = f"{frontend_base.rstrip('/')}/auth/callback?access_token={access}&refresh_token={refresh}"
    return RedirectResponse(frontend_url)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(body: RefreshRequest) -> AccessTokenResponse:
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token de refresco inválido")
        user_id = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Token expirado o inválido")

    from db.database import get_db
    from sqlalchemy import text

    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT id, org_id, role, email FROM users "
                    "WHERE id = :id AND active = TRUE"
                ),
                {"id": user_id},
            ).mappings().fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    if row is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    access = create_access_token(
        sub=str(row["id"]),
        org_id=str(row["org_id"]),
        role=row["role"],
        email=row["email"],
    )
    return AccessTokenResponse(access_token=access)


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)) -> UserResponse:
    from db.database import get_db
    from sqlalchemy import text

    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT id, org_id, email, full_name, role, active, "
                    "last_login_at, created_at FROM users WHERE id = :id"
                ),
                {"id": user["user_id"]},
            ).mappings().fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    if row is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return UserResponse(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        active=row["active"],
        last_login_at=row["last_login_at"],
        created_at=row["created_at"],
    )


@router.post("/logout")
async def logout() -> dict:
    # JWT es stateless; el cliente descarta los tokens
    return {"message": "Sesión cerrada"}


@router.get("/invite/{token}")
async def get_invite_info(token: str) -> dict:
    """Retorna info de la invitación (sin autenticación) para mostrar en la página de registro."""
    from db.database import get_db
    from sqlalchemy import text

    with get_db() as db:
        row = db.execute(
            text("""
                SELECT i.email, i.role, o.name AS org_name
                FROM invitations i
                JOIN organizations o ON o.id = i.org_id
                WHERE i.token = :t AND i.used_at IS NULL AND i.expires_at > NOW()
            """),
            {"t": token},
        ).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invitación inválida o expirada")
    return {"email": row["email"], "role": row["role"], "org_name": row["org_name"]}


@router.post("/invite/{token}/accept", response_model=TokenResponse, status_code=201)
async def accept_invite(token: str, body: AcceptInviteRequest) -> TokenResponse:
    """Crea el usuario a partir de una invitación y retorna tokens de acceso."""
    from db.database import get_db
    from db.auth import hash_password
    from sqlalchemy import text

    with get_db() as db:
        invite = db.execute(
            text("""
                SELECT id, org_id, email, role
                FROM invitations
                WHERE token = :t AND used_at IS NULL AND expires_at > NOW()
            """),
            {"t": token},
        ).mappings().fetchone()
        if not invite:
            raise HTTPException(status_code=404, detail="Invitación inválida o expirada")

        exists = db.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": invite["email"]}
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="El correo ya tiene una cuenta")

        hashed = hash_password(body.password)
        user = db.execute(
            text("""
                INSERT INTO users (org_id, email, hashed_password, full_name, role)
                VALUES (:o, :e, :h, :f, :r)
                RETURNING id, org_id, role, email
            """),
            {"o": invite["org_id"], "e": invite["email"], "h": hashed,
             "f": body.full_name or "", "r": invite["role"]},
        ).mappings().fetchone()

        db.execute(
            text("UPDATE invitations SET used_at = NOW() WHERE id = :id"),
            {"id": invite["id"]},
        )

    access = create_access_token(
        sub=str(user["id"]),
        org_id=str(user["org_id"]),
        role=user["role"],
        email=user["email"],
    )
    refresh = create_refresh_token(sub=str(user["id"]))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/request-admin")
async def request_admin(user: dict = Depends(get_current_user)) -> dict:
    """Usuario con rol base solicita cambio de perfil. Marca timestamp en DB."""
    from db.database import get_db
    from sqlalchemy import text
    from schemas import BASE_ROLES

    if user["role"] not in BASE_ROLES:
        raise HTTPException(status_code=403, detail="Solo usuarios con rol base pueden solicitar cambio de perfil")

    try:
        with get_db() as db:
            db.execute(
                text("UPDATE users SET admin_requested_at = NOW() WHERE id = :id"),
                {"id": user["user_id"]},
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Error de base de datos") from exc

    return {"message": "Solicitud enviada. Un administrador revisará tu solicitud."}


@router.patch("/me")
async def update_me(body: dict, user: dict = Depends(get_current_user)) -> dict:
    """Actualiza nombre y/o contraseña del usuario autenticado."""
    from db.database import get_db
    from db.auth import hash_password, verify_password
    from sqlalchemy import text

    full_name = body.get("full_name")
    current_password = body.get("current_password")
    new_password = body.get("new_password")

    if not full_name and not new_password:
        raise HTTPException(status_code=422, detail="Nada que actualizar")

    with get_db() as db:
        if new_password:
            if len(new_password) < 8:
                raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres")
            if not current_password:
                raise HTTPException(status_code=422, detail="Debes ingresar tu contraseña actual")
            row = db.execute(
                text("SELECT hashed_password FROM users WHERE id = :id"),
                {"id": user["user_id"]},
            ).mappings().fetchone()
            if not row or not verify_password(current_password, row["hashed_password"]):
                raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

        updates: dict = {}
        if full_name is not None:
            updates["full_name"] = full_name.strip()
        if new_password:
            updates["hashed_password"] = hash_password(new_password)

        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["_id"] = user["user_id"]
            db.execute(text(f"UPDATE users SET {set_clause} WHERE id = :_id"), updates)

    return {"message": "Perfil actualizado"}


@router.get("/me/groups")
async def my_groups(user: dict = Depends(get_current_user)) -> list[dict]:
    """Grupos a los que pertenece el usuario autenticado."""
    from db.database import get_db
    from sqlalchemy import text

    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT g.id, g.name, g.description, g.modules
                FROM groups g
                JOIN user_groups ug ON ug.group_id = g.id
                WHERE ug.user_id = :uid
                ORDER BY g.name
            """),
            {"uid": user["user_id"]},
        ).mappings().fetchall()
    return [{"id": str(r["id"]),
             "name": r["name"],
             "description": r["description"],
             "modules": r["modules"]} for r in rows]
