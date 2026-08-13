"""Admin router — stats, users CRUD, groups, audit log, clients, superadmin."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from dependencies import get_current_user, require_admin, require_owner, require_superadmin
from schemas import (
    ADMIN_ROLES,
    AdminStats,
    AuditLogEntry,
    ChangeRoleRequest,
    ClientResponse,
    CreateClientRequest,
    CreateOrgRequest,
    CreateUserRequest,
    GroupCreate,
    GroupResponse,
    OrgResponse,
    SuperadminOrgStats,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _get_db():
    from db.database import db_available, get_db

    if not db_available():
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    return get_db


def _log(db, *, org_id: str, user: dict, action: str, module: str = "admin",
         resource_type: Optional[str] = None, resource_id: Optional[str] = None,
         details: Optional[dict] = None) -> None:
    """Insert an audit log entry. Never raises — failures are silent."""
    try:
        db.execute(
            text("""
                INSERT INTO audit_logs
                    (org_id, user_id, user_email, action, module, resource_type, resource_id, details)
                VALUES (:org_id, :user_id, :email, :action, :module, :rtype, :rid, :details)
            """),
            {
                "org_id": org_id,
                "user_id": user.get("user_id"),
                "email": user.get("email"),
                "action": action,
                "module": module,
                "rtype": resource_type,
                "rid": resource_id,
                "details": json.dumps(details) if details else None,
            },
        )
    except Exception:
        pass


# ── Dashboard stats ───────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_stats(user: dict = Depends(require_admin)) -> AdminStats:
    get_db = _get_db()
    org = user["org_id"]

    try:
        with get_db() as db:
            total_inv = db.execute(
                text("SELECT COUNT(*) FROM invoices WHERE org_id = :o"), {"o": org}
            ).scalar() or 0
            total_exo = db.execute(
                text("SELECT COUNT(*) FROM exogenas_results WHERE org_id = :o"), {"o": org}
            ).scalar() or 0
            total_usr = db.execute(
                text("SELECT COUNT(*) FROM users WHERE org_id = :o AND deleted_at IS NULL"), {"o": org}
            ).scalar() or 0
            total_cli = db.execute(
                text("SELECT COUNT(*) FROM clients WHERE org_id = :o"), {"o": org}
            ).scalar() or 0
            this_month = db.execute(
                text(
                    "SELECT COUNT(*) FROM invoices WHERE org_id = :o "
                    "AND periodo = TO_CHAR(NOW(), 'YYYY-MM')"
                ),
                {"o": org},
            ).scalar() or 0
            sessions = db.execute(
                text(
                    "SELECT id, total_archivos, nuevas, errores, status, started_at "
                    "FROM processing_sessions WHERE org_id = :o "
                    "ORDER BY started_at DESC LIMIT 10"
                ),
                {"o": org},
            ).mappings().fetchall()

            # Financial: invoices by month (last 6 months)
            inv_by_month = db.execute(
                text("""
                    SELECT periodo AS month, COUNT(*) AS count,
                           COALESCE(SUM(total), 0) AS total_amount
                    FROM invoices
                    WHERE org_id = :o
                      AND periodo >= TO_CHAR(NOW() - INTERVAL '5 months', 'YYYY-MM')
                    GROUP BY periodo ORDER BY periodo
                """),
                {"o": org},
            ).mappings().fetchall()

            # Financial: top 5 providers by invoice count
            top_prov = db.execute(
                text("""
                    SELECT nombre_emisor AS name,
                           COUNT(*) AS count,
                           COALESCE(SUM(total), 0) AS total_amount
                    FROM invoices
                    WHERE org_id = :o AND nombre_emisor IS NOT NULL
                    GROUP BY nombre_emisor
                    ORDER BY count DESC LIMIT 5
                """),
                {"o": org},
            ).mappings().fetchall()

            # Operational: users active today (last_login_at today)
            active_today = db.execute(
                text(
                    "SELECT COUNT(*) FROM users WHERE org_id = :o "
                    "AND DATE(last_login_at) = CURRENT_DATE AND deleted_at IS NULL"
                ),
                {"o": org},
            ).scalar() or 0

            # Operational: modules usage from audit_logs (last 30 days)
            modules_usage = db.execute(
                text("""
                    SELECT module, COUNT(*) AS actions
                    FROM audit_logs
                    WHERE org_id = :o
                      AND created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY module ORDER BY actions DESC
                """),
                {"o": org},
            ).mappings().fetchall()

            # Operational: error rate from processing sessions
            total_sessions = db.execute(
                text("SELECT COUNT(*) FROM processing_sessions WHERE org_id = :o"), {"o": org}
            ).scalar() or 0
            error_sessions = db.execute(
                text("SELECT COUNT(*) FROM processing_sessions WHERE org_id = :o AND status = 'failed'"),
                {"o": org},
            ).scalar() or 0

            # Operational: total nomina calculations
            total_nomina = db.execute(
                text("SELECT COUNT(*) FROM audit_logs WHERE org_id = :o AND module = 'nomina'"),
                {"o": org},
            ).scalar() or 0

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    error_rate = round((error_sessions / total_sessions * 100) if total_sessions else 0.0, 1)

    return AdminStats(
        total_invoices=total_inv,
        total_exogenas=total_exo,
        total_users=total_usr,
        total_clients=total_cli,
        invoices_this_month=this_month,
        recent_sessions=[dict(s) for s in sessions],
        invoices_by_month=[dict(r) for r in inv_by_month],
        top_providers=[dict(r) for r in top_prov],
        active_users_today=active_today,
        modules_usage=[dict(r) for r in modules_usage],
        error_rate=error_rate,
        total_nomina=total_nomina,
    )


# ── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
async def list_users(user: dict = Depends(require_admin)) -> list[UserResponse]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text(
                "SELECT id, org_id, email, full_name, role, active, last_login_at, created_at "
                "FROM users WHERE org_id = :o AND deleted_at IS NULL ORDER BY created_at DESC"
            ),
            {"o": user["org_id"]},
        ).mappings().fetchall()
    return [
        UserResponse(
            id=str(r["id"]),
            org_id=str(r["org_id"]),
            email=r["email"],
            full_name=r["full_name"],
            role=r["role"],
            active=r["active"],
            last_login_at=r["last_login_at"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    admin: dict = Depends(require_admin),
) -> UserResponse:
    from db.auth import hash_password

    get_db = _get_db()
    hashed = hash_password(body.password)

    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "INSERT INTO users (org_id, email, hashed_password, full_name, role) "
                    "VALUES (:org_id, :email, :hp, :fn, :role) "
                    "RETURNING id, org_id, email, full_name, role, active, last_login_at, created_at"
                ),
                {
                    "org_id": admin["org_id"],
                    "email": body.email,
                    "hp": hashed,
                    "fn": body.full_name,
                    "role": body.role,
                },
            ).mappings().fetchone()
            _log(db, org_id=admin["org_id"], user=admin, action="create_user",
                 resource_type="user", resource_id=str(row["id"]),
                 details={"email": body.email, "role": body.role})
    except HTTPException:
        raise
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Email ya registrado")
        raise HTTPException(status_code=500, detail=str(exc))

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


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    admin: dict = Depends(require_admin),
) -> dict:
    get_db = _get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="Sin cambios que aplicar")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_user_id"] = user_id
    updates["_org_id"] = admin["org_id"]

    with get_db() as db:
        db.execute(
            text(f"UPDATE users SET {set_clause} WHERE id = :_user_id AND org_id = :_org_id AND deleted_at IS NULL"),
            updates,
        )
        _log(db, org_id=admin["org_id"], user=admin, action="update_user",
             resource_type="user", resource_id=user_id, details=updates)
    return {"message": "Usuario actualizado"}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    admin: dict = Depends(require_admin),
) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("UPDATE users SET active = FALSE WHERE id = :id AND org_id = :o AND deleted_at IS NULL"),
            {"id": user_id, "o": admin["org_id"]},
        )
        _log(db, org_id=admin["org_id"], user=admin, action="deactivate_user",
             resource_type="user", resource_id=user_id)
    return {"message": "Usuario desactivado"}


@router.delete("/users/{user_id}/permanent")
async def hard_delete_user(
    user_id: str,
    owner: dict = Depends(require_owner),
) -> dict:
    """Borrado permanente (owner only). Anonymiza email antes de eliminar."""
    get_db = _get_db()
    with get_db() as db:
        # Check the user exists and is not the owner themselves
        target = db.execute(
            text("SELECT id, email, role FROM users WHERE id = :id AND org_id = :o AND deleted_at IS NULL"),
            {"id": user_id, "o": owner["org_id"]},
        ).mappings().fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target["role"] == "owner":
            raise HTTPException(status_code=403, detail="No se puede eliminar al owner")
        if str(target["id"]) == owner["user_id"]:
            raise HTTPException(status_code=403, detail="No puedes eliminarte a ti mismo")

        _log(db, org_id=owner["org_id"], user=owner, action="hard_delete_user",
             resource_type="user", resource_id=user_id,
             details={"email": target["email"], "role": target["role"]})

        # Mark as deleted (keeps referential integrity for audit logs)
        db.execute(
            text("""
                UPDATE users
                SET deleted_at = NOW(), active = FALSE,
                    email = CONCAT('deleted_', :uid, '@deleted.local'),
                    hashed_password = 'DELETED'
                WHERE id = :id AND org_id = :o
            """),
            {"id": user_id, "o": owner["org_id"], "uid": user_id},
        )
    return {"message": "Usuario eliminado permanentemente"}


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    admin: dict = Depends(require_admin),
) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("UPDATE users SET active = TRUE WHERE id = :id AND org_id = :o AND deleted_at IS NULL"),
            {"id": user_id, "o": admin["org_id"]},
        )
        _log(db, org_id=admin["org_id"], user=admin, action="reactivate_user",
             resource_type="user", resource_id=user_id)
    return {"message": "Usuario reactivado"}


@router.get("/users/admin-requests")
async def list_admin_requests(admin: dict = Depends(require_admin)) -> list[dict]:
    from schemas import BASE_ROLES
    get_db = _get_db()
    placeholders = ", ".join(f"'{r}'" for r in BASE_ROLES)
    with get_db() as db:
        rows = db.execute(
            text(f"""
                SELECT id, email, full_name, role, admin_requested_at, created_at
                FROM users
                WHERE org_id = :o AND role IN ({placeholders})
                  AND admin_requested_at IS NOT NULL
                  AND active = TRUE AND deleted_at IS NULL
                ORDER BY admin_requested_at ASC
            """),
            {"o": admin["org_id"]},
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@router.patch("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    body: ChangeRoleRequest,
    admin: dict = Depends(require_admin),
) -> dict:
    """Cambia el rol de un usuario. Owner puede asignar cualquier rol; admin solo roles base."""
    caller_role = admin["role"]

    if body.role in ADMIN_ROLES and caller_role != "owner":
        raise HTTPException(status_code=403, detail="Solo el owner puede asignar roles admin u owner")

    get_db = _get_db()
    with get_db() as db:
        target = db.execute(
            text("SELECT id, role FROM users WHERE id = :id AND org_id = :o AND deleted_at IS NULL"),
            {"id": user_id, "o": admin["org_id"]},
        ).mappings().fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target["role"] == "owner" and caller_role != "owner":
            raise HTTPException(status_code=403, detail="No se puede modificar el rol de un owner")
        if str(target["id"]) == admin["user_id"]:
            raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol")

        db.execute(
            text("UPDATE users SET role = :r, admin_requested_at = NULL WHERE id = :id AND org_id = :o"),
            {"r": body.role, "id": user_id, "o": admin["org_id"]},
        )
        _log(db, org_id=admin["org_id"], user=admin, action="change_role",
             resource_type="user", resource_id=user_id,
             details={"from": target["role"], "to": body.role})
    return {"message": f"Rol actualizado a {body.role}"}


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(owner: dict = Depends(require_owner)) -> list[GroupResponse]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT g.id, g.org_id, g.name, g.description, g.modules, g.created_at,
                       COUNT(ug.user_id) AS members_count
                FROM groups g
                LEFT JOIN user_groups ug ON ug.group_id = g.id
                WHERE g.org_id = :o
                GROUP BY g.id ORDER BY g.created_at DESC
            """),
            {"o": owner["org_id"]},
        ).mappings().fetchall()
    return [
        GroupResponse(
            id=str(r["id"]),
            org_id=str(r["org_id"]),
            name=r["name"],
            description=r["description"],
            modules=list(r["modules"] or []),
            created_at=r["created_at"],
            members_count=r["members_count"],
        )
        for r in rows
    ]


@router.post("/groups", response_model=GroupResponse, status_code=201)
async def create_group(
    body: GroupCreate,
    owner: dict = Depends(require_owner),
) -> GroupResponse:
    get_db = _get_db()
    try:
        with get_db() as db:
            row = db.execute(
                text("""
                    INSERT INTO groups (org_id, name, description, modules)
                    VALUES (:o, :name, :desc, :modules)
                    RETURNING id, org_id, name, description, modules, created_at
                """),
                {
                    "o": owner["org_id"],
                    "name": body.name,
                    "desc": body.description,
                    "modules": body.modules,
                },
            ).mappings().fetchone()
            _log(db, org_id=owner["org_id"], user=owner, action="create_group",
                 resource_type="group", resource_id=str(row["id"]),
                 details={"name": body.name})
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Nombre de grupo ya existe")
        raise HTTPException(status_code=500, detail=str(exc))

    return GroupResponse(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        name=row["name"],
        description=row["description"],
        modules=list(row["modules"] or []),
        created_at=row["created_at"],
        members_count=0,
    )


@router.patch("/groups/{group_id}")
async def update_group(
    group_id: str,
    body: GroupCreate,
    owner: dict = Depends(require_owner),
) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("""
                UPDATE groups SET name = :name, description = :desc, modules = :modules
                WHERE id = :id AND org_id = :o
            """),
            {"id": group_id, "o": owner["org_id"], "name": body.name,
             "desc": body.description, "modules": body.modules},
        )
        _log(db, org_id=owner["org_id"], user=owner, action="update_group",
             resource_type="group", resource_id=group_id)
    return {"message": "Grupo actualizado"}


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    owner: dict = Depends(require_owner),
) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("DELETE FROM groups WHERE id = :id AND org_id = :o"),
            {"id": group_id, "o": owner["org_id"]},
        )
        _log(db, org_id=owner["org_id"], user=owner, action="delete_group",
             resource_type="group", resource_id=group_id)
    return {"message": "Grupo eliminado"}


@router.post("/groups/{group_id}/members/{user_id}")
async def add_user_to_group(
    group_id: str,
    user_id: str,
    owner: dict = Depends(require_owner),
) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("INSERT INTO user_groups (user_id, group_id) VALUES (:u, :g) ON CONFLICT DO NOTHING"),
            {"u": user_id, "g": group_id},
        )
        _log(db, org_id=owner["org_id"], user=owner, action="add_to_group",
             resource_type="user", resource_id=user_id,
             details={"group_id": group_id})
    return {"message": "Usuario agregado al grupo"}


@router.delete("/groups/{group_id}/members/{user_id}")
async def remove_user_from_group(
    group_id: str,
    user_id: str,
    owner: dict = Depends(require_owner),
) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("DELETE FROM user_groups WHERE user_id = :u AND group_id = :g"),
            {"u": user_id, "g": group_id},
        )
        _log(db, org_id=owner["org_id"], user=owner, action="remove_from_group",
             resource_type="user", resource_id=user_id,
             details={"group_id": group_id})
    return {"message": "Usuario removido del grupo"}


@router.get("/groups/{group_id}/members")
async def list_group_members(
    group_id: str,
    owner: dict = Depends(require_owner),
) -> list[dict]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT u.id, u.email, u.full_name, u.role, u.active
                FROM users u
                JOIN user_groups ug ON ug.user_id = u.id
                WHERE ug.group_id = :g AND u.org_id = :o AND u.deleted_at IS NULL
            """),
            {"g": group_id, "o": owner["org_id"]},
        ).mappings().fetchall()
    return [dict(r) for r in rows]


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=list[AuditLogEntry])
async def list_audit_logs(
    admin: dict = Depends(require_admin),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
) -> list[AuditLogEntry]:
    get_db = _get_db()
    filters = ["org_id = :o"]
    params: dict = {"o": admin["org_id"], "limit": limit}

    if module:
        filters.append("module = :module")
        params["module"] = module
    if action:
        filters.append("action ILIKE :action")
        params["action"] = f"%{action}%"
    if user_email:
        filters.append("user_email ILIKE :uemail")
        params["uemail"] = f"%{user_email}%"

    where = " AND ".join(filters)
    with get_db() as db:
        rows = db.execute(
            text(f"""
                SELECT id, user_email, action, module, resource_type, resource_id, details, created_at
                FROM audit_logs
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            params,
        ).mappings().fetchall()

    return [
        AuditLogEntry(
            id=str(r["id"]),
            user_email=r["user_email"],
            action=r["action"],
            module=r["module"],
            resource_type=r["resource_type"],
            resource_id=r["resource_id"],
            details=r["details"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ── Clients ──────────────────────────────────────────────────────────────────

@router.get("/clients", response_model=list[ClientResponse])
async def list_clients(user: dict = Depends(require_admin)) -> list[ClientResponse]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text(
                "SELECT id, org_id, nit, razon_social, active, created_at "
                "FROM clients WHERE org_id = :o ORDER BY razon_social"
            ),
            {"o": user["org_id"]},
        ).mappings().fetchall()
    return [
        ClientResponse(
            id=str(r["id"]),
            org_id=str(r["org_id"]),
            nit=r["nit"],
            razon_social=r["razon_social"],
            active=r["active"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/clients", response_model=ClientResponse, status_code=201)
async def create_client(
    body: CreateClientRequest,
    admin: dict = Depends(require_admin),
) -> ClientResponse:
    get_db = _get_db()
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "INSERT INTO clients (org_id, nit, razon_social) "
                    "VALUES (:o, :nit, :rs) "
                    "RETURNING id, org_id, nit, razon_social, active, created_at"
                ),
                {"o": admin["org_id"], "nit": body.nit, "rs": body.razon_social},
            ).mappings().fetchone()
            _log(db, org_id=admin["org_id"], user=admin, action="create_client",
                 resource_type="client", resource_id=str(row["id"]))
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="NIT ya registrado en esta organización")
        raise HTTPException(status_code=500, detail=str(exc))

    return ClientResponse(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        nit=row["nit"],
        razon_social=row["razon_social"],
        active=row["active"],
        created_at=row["created_at"],
    )


# ── Superadmin ────────────────────────────────────────────────────────────────

@router.get("/superadmin/check")
async def superadmin_check(user: dict = Depends(get_current_user)) -> dict:
    """Retorna is_superadmin para cualquier usuario autenticado (nunca 403)."""
    from core.config import get_settings  # noqa: E402 (mismo patrón local que el resto del archivo)
    s = get_settings()
    allowed = {e.strip().lower() for e in s.TAXOPS_SUPERADMIN_EMAILS.split(",") if e.strip()}
    return {"is_superadmin": user["email"].lower() in allowed}


@router.get("/superadmin/orgs", response_model=list[SuperadminOrgStats])
async def list_orgs(_: dict = Depends(require_superadmin)) -> list[SuperadminOrgStats]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text(
                "SELECT o.id, o.slug, o.name, o.plan, o.active, "
                "COUNT(DISTINCT u.id) AS users_count, "
                "COUNT(DISTINCT i.id) AS invoices_count "
                "FROM organizations o "
                "LEFT JOIN users u ON u.org_id = o.id "
                "LEFT JOIN invoices i ON i.org_id = o.id "
                "GROUP BY o.id ORDER BY o.created_at DESC"
            )
        ).mappings().fetchall()
    return [
        SuperadminOrgStats(
            id=str(r["id"]),
            slug=r["slug"],
            name=r["name"],
            plan=r["plan"],
            active=r["active"],
            users_count=r["users_count"],
            invoices_count=r["invoices_count"],
        )
        for r in rows
    ]


@router.get("/superadmin/users")
async def superadmin_list_users(_: dict = Depends(require_superadmin)) -> list[dict]:
    """Todos los usuarios de todas las organizaciones."""
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT u.id, u.email, u.full_name, u.role, u.active,
                       u.admin_requested_at, u.created_at,
                       o.name AS org_name, o.id AS org_id
                FROM users u
                JOIN organizations o ON o.id = u.org_id
                WHERE u.deleted_at IS NULL
                ORDER BY o.name, u.created_at
            """)
        ).mappings().fetchall()
    return [
        {
            "id": str(r["id"]), "email": r["email"], "full_name": r["full_name"],
            "role": r["role"], "active": r["active"],
            "admin_requested_at": r["admin_requested_at"].isoformat() if r["admin_requested_at"] else None,
            "created_at": r["created_at"].isoformat(),
            "org_name": r["org_name"], "org_id": str(r["org_id"]),
        }
        for r in rows
    ]


@router.patch("/superadmin/users/{user_id}/role")
async def superadmin_change_role(
    user_id: str,
    body: ChangeRoleRequest,
    _: dict = Depends(require_superadmin),
) -> dict:
    """Superadmin cambia el rol de cualquier usuario en cualquier org."""
    get_db = _get_db()
    with get_db() as db:
        result = db.execute(
            text(
                "UPDATE users SET role = :r, admin_requested_at = NULL "
                "WHERE id = :id AND deleted_at IS NULL RETURNING id"
            ),
            {"r": body.role, "id": user_id},
        ).fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": f"Rol actualizado a {body.role}"}


@router.post("/superadmin/orgs", response_model=OrgResponse, status_code=201)
async def create_org(
    body: CreateOrgRequest,
    _: dict = Depends(require_superadmin),
) -> OrgResponse:
    get_db = _get_db()
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "INSERT INTO organizations (slug, name, nit, plan) "
                    "VALUES (:slug, :name, :nit, :plan) "
                    "RETURNING id, slug, name, nit, plan, active, created_at"
                ),
                body.model_dump(),
            ).mappings().fetchone()
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Slug ya existe")
        raise HTTPException(status_code=500, detail=str(exc))

    return OrgResponse(
        id=str(row["id"]),
        slug=row["slug"],
        name=row["name"],
        nit=row["nit"],
        plan=row["plan"],
        active=row["active"],
        created_at=row["created_at"],
    )


# ── Sessions / Actividad ──────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(user: dict = Depends(require_admin)) -> list[dict]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT ps.id, ps.total_archivos, ps.procesados, ps.errores,
                       ps.nuevas, ps.duplicadas, ps.status,
                       ps.started_at, ps.finished_at,
                       u.email AS user_email
                FROM processing_sessions ps
                LEFT JOIN users u ON u.id = ps.user_id
                WHERE ps.org_id = :o
                ORDER BY ps.started_at DESC
                LIMIT 100
            """),
            {"o": user["org_id"]},
        ).mappings().fetchall()
    return [dict(r) for r in rows]


# ── Autorretenedores ──────────────────────────────────────────────────────────

@router.get("/autorretenedores")
async def list_autorretenedores(user: dict = Depends(require_admin)) -> list[dict]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text("SELECT id, nit, razon_social, vigente, updated_at FROM autorretenedores ORDER BY nit")
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post("/autorretenedores", status_code=201)
async def add_autorretenedor(body: dict, admin: dict = Depends(require_admin)) -> dict:
    nit = (body.get("nit") or "").strip()
    razon_social = (body.get("razon_social") or "").strip() or None
    if not nit:
        raise HTTPException(status_code=422, detail="NIT requerido")
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text(
                "INSERT INTO autorretenedores (nit, razon_social) VALUES (:nit, :rs) "
                "ON CONFLICT (nit) DO UPDATE SET vigente = TRUE, "
                "razon_social = EXCLUDED.razon_social, updated_at = NOW()"
            ),
            {"nit": nit, "rs": razon_social},
        )
        _log(db, org_id=admin["org_id"], user=admin, action="add_autorretenedor",
             resource_type="autorretenedor", resource_id=nit)
    return {"nit": nit, "message": "Autorretenedor agregado"}


@router.delete("/autorretenedores/{nit}")
async def remove_autorretenedor(nit: str, admin: dict = Depends(require_admin)) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("UPDATE autorretenedores SET vigente = FALSE, updated_at = NOW() WHERE nit = :nit"),
            {"nit": nit},
        )
        _log(db, org_id=admin["org_id"], user=admin, action="remove_autorretenedor",
             resource_type="autorretenedor", resource_id=nit)
    return {"message": "NIT desactivado"}


# ── Ingresos prorrateo ────────────────────────────────────────────────────────

@router.get("/ingresos")
async def list_ingresos(user: dict = Depends(require_admin)) -> list[dict]:
    get_db = _get_db()
    with get_db() as db:
        rows = db.execute(
            text(
                "SELECT id, periodo, ingresos_gravados, ingresos_excluidos, updated_at "
                "FROM ingresos_prorateo WHERE org_id = :o ORDER BY periodo DESC"
            ),
            {"o": user["org_id"]},
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post("/ingresos", status_code=201)
async def upsert_ingreso(body: dict, admin: dict = Depends(require_admin)) -> dict:
    periodo = (body.get("periodo") or "").strip()
    if not periodo:
        raise HTTPException(status_code=422, detail="Periodo requerido (YYYY-MM)")
    gravados = float(body.get("ingresos_gravados") or 0)
    excluidos = float(body.get("ingresos_excluidos") or 0)
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text(
                "INSERT INTO ingresos_prorateo (org_id, periodo, ingresos_gravados, ingresos_excluidos) "
                "VALUES (:o, :p, :g, :e) "
                "ON CONFLICT (org_id, periodo) DO UPDATE "
                "SET ingresos_gravados = EXCLUDED.ingresos_gravados, "
                "    ingresos_excluidos = EXCLUDED.ingresos_excluidos"
            ),
            {"o": admin["org_id"], "p": periodo, "g": gravados, "e": excluidos},
        )
    return {"periodo": periodo, "message": "Ingreso guardado"}


@router.delete("/ingresos/{periodo}")
async def delete_ingreso(periodo: str, admin: dict = Depends(require_admin)) -> dict:
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("DELETE FROM ingresos_prorateo WHERE org_id = :o AND periodo = :p"),
            {"o": admin["org_id"], "p": periodo},
        )
    return {"message": "Ingreso eliminado"}


# ── Organización propia ───────────────────────────────────────────────────────

@router.get("/org")
async def get_org(user: dict = Depends(require_admin)) -> dict:
    get_db = _get_db()
    with get_db() as db:
        row = db.execute(
            text("SELECT id, slug, name, nit, plan, active, created_at FROM organizations WHERE id = :o"),
            {"o": user["org_id"]},
        ).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return dict(row)


@router.patch("/org")
async def update_org(body: dict, admin: dict = Depends(require_admin)) -> dict:
    allowed = {"name", "nit"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=422, detail="Sin cambios válidos")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_org_id"] = admin["org_id"]
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text(f"UPDATE organizations SET {set_clause} WHERE id = :_org_id"),
            updates,
        )
        _log(db, org_id=admin["org_id"], user=admin, action="update_org",
             resource_type="org", details=updates)
    return {"message": "Organización actualizada"}


# ── Invitations ───────────────────────────────────────────────────────────────

from schemas import InviteCreate, InviteResponse  # noqa: E402 (inline to avoid circular at module top)


@router.post("/invitations", response_model=InviteResponse, status_code=201)
async def create_invitation(body: InviteCreate, admin: dict = Depends(require_admin)) -> InviteResponse:
    import secrets
    from datetime import datetime, timedelta, timezone
    from core.config import get_settings

    get_db = _get_db()
    s = get_settings()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    with get_db() as db:
        # Revoke any existing unused invite for same email in org
        db.execute(
            text("DELETE FROM invitations WHERE org_id=:o AND email=:e AND used_at IS NULL"),
            {"o": admin["org_id"], "e": body.email},
        )
        row = db.execute(
            text("""
                INSERT INTO invitations (org_id, created_by, email, role, token, expires_at)
                VALUES (:org, :by, :email, :role, :token, :exp)
                RETURNING id, created_at
            """),
            {"org": admin["org_id"], "by": admin["user_id"], "email": body.email,
             "role": body.role, "token": token, "exp": expires_at},
        ).mappings().fetchone()
        _log(db, org_id=admin["org_id"], user=admin, action="invite_user",
             resource_type="invitation", details={"email": body.email, "role": body.role})

    invite_url = f"{s.FRONTEND_URL.rstrip('/')}/invite/{token}"
    return InviteResponse(
        id=str(row["id"]),
        email=body.email,
        role=body.role,
        invite_url=invite_url,
        expires_at=expires_at,
        created_at=row["created_at"],
    )


@router.get("/invitations", response_model=list[InviteResponse])
async def list_invitations(admin: dict = Depends(require_admin)) -> list[InviteResponse]:
    from core.config import get_settings
    get_db = _get_db()
    s = get_settings()
    with get_db() as db:
        rows = db.execute(
            text("""
                SELECT id, email, role, token, expires_at, used_at, created_at
                FROM invitations
                WHERE org_id = :o AND used_at IS NULL AND expires_at > NOW()
                ORDER BY created_at DESC
            """),
            {"o": admin["org_id"]},
        ).mappings().fetchall()
    return [
        InviteResponse(
            id=str(r["id"]),
            email=r["email"],
            role=r["role"],
            invite_url=f"{s.FRONTEND_URL.rstrip('/')}/invite/{r['token']}",
            expires_at=r["expires_at"],
            used_at=r["used_at"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.delete("/invitations/{invite_id}", status_code=204)
async def revoke_invitation(invite_id: str, admin: dict = Depends(require_admin)):
    get_db = _get_db()
    with get_db() as db:
        db.execute(
            text("DELETE FROM invitations WHERE id=:id AND org_id=:o"),
            {"id": invite_id, "o": admin["org_id"]},
        )
