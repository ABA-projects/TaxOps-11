"""TaxOps FastAPI — entry point.  # 2026-05-20

Estructura de imports:
  - api/ → este directorio (routers, schemas, dependencies, core/)
  - pipeline/, services/, db/, exogenas/ → directorio padre (proyecto-facturas/)

El sys.path.insert garantiza que al ejecutar `uvicorn main:app` desde api/,
el directorio raíz del proyecto quede en el path de Python.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# Asegurar que pipeline/, services/, db/, exogenas/ sean importables ANTES de
# importar routers/core.config (que a su vez importan services.*, db.*, etc.)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import get_settings  # noqa: E402
from routers import (  # noqa: E402
    admin,
    auth,
    calendario,
    chatbot,
    exogenas,
    invoices,
    nomina,
    renta,
    renta_documentos,
    uploads,
)

settings = get_settings()


def _run_migrations() -> None:
    """Corre `alembic upgrade head` en startup para aplicar migraciones pendientes."""
    import os
    from alembic import command
    from alembic.config import Config

    ini = Path(__file__).parent / "alembic.ini"
    if not ini.exists():
        return
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", ""))
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        # No bloquear el arranque si Alembic falla (ej. DB aún no disponible)
        import logging
        logging.getLogger("taxops").warning("Alembic upgrade failed: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    import threading
    # Ejecutar migraciones en background para no bloquear el healthcheck en
    # modo serverless (Railway Develop). El servidor arranca inmediatamente.
    threading.Thread(target=_run_migrations, daemon=True).start()
    yield


app = FastAPI(
    title="TaxOps API",
    version="2.0.1",
    description="API REST para automatización contable colombiana · Facturas DIAN · Exógenas · IA",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(invoices.router)
app.include_router(exogenas.router)
app.include_router(chatbot.router)
app.include_router(admin.router)
app.include_router(nomina.router)
app.include_router(calendario.router)
app.include_router(renta.router)
app.include_router(renta_documentos.router)
app.include_router(uploads.router)


@app.get("/health", tags=["Health"])
async def health() -> dict:
    from db.database import db_available

    return {
        "status": "ok",
        "version": "2.0.1",
        "db": "connected" if db_available() else "unavailable",
    }


@app.post("/setup/bootstrap", tags=["Setup"], include_in_schema=False)
async def bootstrap(secret: str, org_slug: str, org_name: str,
                    email: str, password: str, full_name: str = "") -> dict:
    """Endpoint de setup inicial — protegido por BOOTSTRAP_SECRET en env vars."""
    import os
    expected = os.environ.get("BOOTSTRAP_SECRET", "")
    if not expected or secret != expected:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    from db.database import get_db
    from db.auth import hash_password
    from sqlalchemy import text

    hashed = hash_password(password)
    with get_db() as db:
        org = db.execute(text("""
            INSERT INTO organizations (slug, name, plan)
            VALUES (:slug, :name, 'pro')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id, slug, name
        """), {"slug": org_slug, "name": org_name}).mappings().fetchone()

        user = db.execute(text("""
            INSERT INTO users (org_id, email, hashed_password, full_name, role)
            VALUES (:org_id, :email, :hp, :fn, 'owner')
            ON CONFLICT (email) DO UPDATE
                SET hashed_password = EXCLUDED.hashed_password,
                    full_name = EXCLUDED.full_name,
                    role = 'owner', active = TRUE
            RETURNING id, email, role
        """), {"org_id": org["id"], "email": email.strip().lower(),
               "hp": hashed, "fn": full_name}).mappings().fetchone()

    return {"org": {"id": str(org["id"]), "slug": org["slug"], "name": org["name"]},
            "user": {"id": str(user["id"]), "email": user["email"], "role": user["role"]}}


# lifespan="off": el `lifespan` de este archivo dispara un thread de background
# para migraciones Alembic pensado para un servidor long-running — no es seguro
# bajo el modelo de cold-start/freeze de Lambda. Las migraciones se corren aparte
# (paso de CI), fuera de alcance aquí.
handler = Mangum(app, lifespan="off")
