# Integración de agentes contables existentes a TaxOps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Programar y conectar a TaxOps los 4 agentes standalone de `agents/contabilidad/` (dian-monitor, monitor-niif, vencimientos-tributarios, prospector-clientes-contables), que hoy corren manual y no persisten en ningún lado que la app pueda leer.

**Architecture:** 1 workflow de GitHub Actions (cron semanal + `workflow_dispatch`) con 4 jobs independientes. Cada agente sigue corriendo igual (motor compartido `_shared/agent_core.py` sin tocar); un `publish.py` nuevo por agente valida su salida y escribe directo al storage (Postgres para novedades/leads, S3 para el calendario) — sin pasar por la API ni necesitar un JWT de servicio. Dos endpoints nuevos (`GET /novedades`, `GET /admin/leads`) y dos páginas nuevas en el frontend exponen los datos.

**Tech Stack:** Python (agentes, ya existente), psycopg2 (conexión directa a Neon desde los scripts, sin SQLAlchemy — más liviano para un script standalone), boto3 (S3), Alembic (migración de schema), FastAPI, Next.js/React.

**Spec:** `docs/superpowers/specs/2026-08-23-agentes-contables-integracion-design.md`

## Global Constraints

- Nunca pisar datos existentes (calendario en S3, tablas Postgres) con una corrida de agente fallida o vacía — validar antes de escribir.
- El workflow de GitHub Actions escribe directo al storage (Postgres/S3) usando credenciales ya existentes (`DATABASE_URL` secret, rol OIDC `github_actions_terraform` ya con `AdministratorAccess`) — no se crea autenticación de servicio nueva contra la API.
- `novedades` y `leads_comerciales` son tablas globales (sin `org_id`) — mismo criterio que `reglas_tributarias`.
- `GET /novedades` es accesible para cualquier rol autenticado (`get_current_user`). `GET /admin/leads` requiere `require_admin` (owner/admin), igual que el resto de `/admin/*`.
- `agents/empleo/*` y cualquier cambio a `agents/_shared/agent_core.py` (el motor LLM) están fuera de alcance de este plan.

---

### Task 1: Migración Alembic — tablas `novedades` y `leads_comerciales`

**Files:**
- Create: `api/alembic/versions/007_novedades_leads.py`

**Interfaces:**
- Produces: tablas `novedades (id, tipo, titulo, resumen, fecha_generado, created_at)` y `leads_comerciales (id, empresa, sector, ciudad, contacto, fuente_url, fecha_generado, created_at)`, con `UNIQUE (empresa, ciudad)` en la segunda. Usadas por las Tasks 4-7.

- [ ] **Step 1: Escribir la migración**

```python
"""Add novedades and leads_comerciales tables.

Revision ID: 007
Revises: 006
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS novedades (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tipo            VARCHAR(20) NOT NULL,
            titulo          TEXT NOT NULL,
            resumen         TEXT NOT NULL,
            fecha_generado  DATE NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_novedades_fecha ON novedades (fecha_generado DESC)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS leads_comerciales (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa         TEXT NOT NULL,
            sector          VARCHAR(100),
            ciudad          VARCHAR(100),
            contacto        TEXT,
            fuente_url      TEXT,
            fecha_generado  DATE NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_lead UNIQUE (empresa, ciudad)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS leads_comerciales")
    op.execute("DROP TABLE IF EXISTS novedades")
```

- [ ] **Step 2: Correr la migración localmente contra una DB de prueba**

```bash
cd api && DATABASE_URL="postgresql://localhost/taxops_test" alembic upgrade head
```

Expected: sin errores, `\dt novedades` y `\dt leads_comerciales` muestran las tablas.

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/007_novedades_leads.py
git commit -m "feat: migración — tablas novedades y leads_comerciales"
```

---

### Task 2: `agents/_shared/db_publish.py` — helper compartido de escritura a Postgres

**Files:**
- Create: `agents/_shared/db_publish.py`
- Test: `agents/_shared/test_db_publish.py`

**Interfaces:**
- Consumes: `DATABASE_URL` (variable de entorno)
- Produces: `insert_novedad(tipo: str, titulo: str, resumen: str, fecha_generado: date) -> None`, `insert_lead(empresa: str, sector: str, ciudad: str, contacto: str, fuente_url: str, fecha_generado: date) -> None` — usados por Tasks 4, 5, 6.

- [ ] **Step 1: Escribir el test que falla**

```python
# agents/_shared/test_db_publish.py
"""Tests para db_publish.py — usa una DB Postgres real de test (no mockeable fácilmente,
psycopg2 no tiene un equivalente directo a moto). Requiere DATABASE_URL apuntando a una
DB de test vacía o con las tablas de la migración 007 ya aplicadas."""
import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from _shared.db_publish import insert_lead, insert_novedad  # noqa: E402

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ, reason="requiere DATABASE_URL de una DB de test"
)


@pytest.fixture
def clean_tables():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("DELETE FROM novedades WHERE titulo LIKE 'TEST %'")
        cur.execute("DELETE FROM leads_comerciales WHERE empresa LIKE 'TEST %'")
    conn.commit()
    conn.close()
    yield


def test_insert_novedad(clean_tables):
    insert_novedad("dian", "TEST Resolución nueva", "Resumen de prueba", date(2026, 8, 23))

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("SELECT tipo, titulo, resumen FROM novedades WHERE titulo = 'TEST Resolución nueva'")
        row = cur.fetchone()
    conn.close()
    assert row == ("dian", "TEST Resolución nueva", "Resumen de prueba")


def test_insert_lead_dedups_by_empresa_ciudad(clean_tables):
    insert_lead("TEST Restaurante XYZ", "restaurantes", "Medellín", "contacto@xyz.com", "https://x.com", date(2026, 8, 23))
    insert_lead("TEST Restaurante XYZ", "restaurantes", "Medellín", "otro@xyz.com", "https://y.com", date(2026, 8, 24))

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM leads_comerciales WHERE empresa = 'TEST Restaurante XYZ'")
        count = cur.fetchone()[0]
    conn.close()
    assert count == 1  # la segunda inserción no duplicó — ON CONFLICT DO NOTHING
```

- [ ] **Step 2: Correr — debe fallar**

```bash
cd agents/_shared && python -m pytest test_db_publish.py -v
```

Expected: FAIL (`ModuleNotFoundError: No module named '_shared.db_publish'`) o SKIPPED si no hay `DATABASE_URL` — en ese caso, exportar `DATABASE_URL` de una DB de test antes de continuar.

- [ ] **Step 3: Escribir `db_publish.py`**

```python
"""agents/_shared/db_publish.py — Escritura directa a Postgres (Neon) para los publish.py de
cada agente. Usa psycopg2 crudo (no SQLAlchemy/db.database.py del API) porque estos scripts
corren standalone en GitHub Actions, no como parte de la app FastAPI.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg2


def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está seteado")
    return psycopg2.connect(url)


def insert_novedad(tipo: str, titulo: str, resumen: str, fecha_generado: date) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO novedades (tipo, titulo, resumen, fecha_generado) "
                "VALUES (%s, %s, %s, %s)",
                (tipo, titulo, resumen, fecha_generado),
            )
        conn.commit()
    finally:
        conn.close()


def insert_lead(
    empresa: str, sector: str, ciudad: str, contacto: str, fuente_url: str, fecha_generado: date
) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO leads_comerciales (empresa, sector, ciudad, contacto, fuente_url, fecha_generado) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (empresa, ciudad) DO NOTHING",
                (empresa, sector, ciudad, contacto, fuente_url, fecha_generado),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/_shared && DATABASE_URL="postgresql://localhost/taxops_test" python -m pytest test_db_publish.py -v
```

Expected: 2 passed (requiere que la migración 007 ya esté aplicada en esa DB de test).

- [ ] **Step 5: Commit**

```bash
git add agents/_shared/db_publish.py agents/_shared/test_db_publish.py
git commit -m "feat: db_publish.py — helper compartido de INSERT para agentes contables"
```

---

### Task 3: `api/routers/calendario.py` migra de archivo local a S3

**Files:**
- Modify: `api/routers/calendario.py`
- Test: `tests/test_calendario.py` (nuevo — no existía ningún test para este router)

**Interfaces:**
- Consumes: `Settings.S3_BUCKET_JOB_ARTIFACTS`, `Settings.AWS_REGION` (ya existen, usados igual que en `uploads.py`/`invoices.py`)
- Produces: mismo contrato HTTP (`GET`/`PUT`/`POST`/`DELETE /calendario/eventos`) — el frontend no cambia. `_load()`/`_save()` cambian de firma solo internamente.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_calendario.py
"""Tests para /calendario/eventos — moto-mocked S3 (el storage cambió de archivo local a S3)."""
import sys
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402

_CALENDARIO_KEY = "config/calendario_2026.json"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")
        yield TestClient(load_fastapi_app())


def _auth_headers(role: str = "owner", is_superadmin: bool = False) -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role=role, email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def _superadmin_headers(monkeypatch) -> dict:
    monkeypatch.setenv("TAXOPS_SUPERADMIN_EMAILS", "super@taxops.com")
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="owner", email="super@taxops.com")
    return {"Authorization": f"Bearer {token}"}


def test_get_eventos_empty_when_no_s3_object(client):
    res = client.get("/calendario/eventos", headers=_auth_headers())
    assert res.status_code == 200
    assert res.json() == []


def test_put_eventos_persists_to_s3_and_get_returns_it(client, monkeypatch):
    headers = _superadmin_headers(monkeypatch)
    evento = {
        "id": "1", "fecha": "2026-09-15", "titulo": "IVA bimestral",
        "descripcion": "Vencimiento IVA", "tipo": "iva", "urgencia": "alta",
    }
    put_res = client.put("/calendario/eventos", json=[evento], headers=headers)
    assert put_res.status_code == 200

    get_res = client.get("/calendario/eventos", headers=_auth_headers())
    assert get_res.status_code == 200
    assert get_res.json() == [evento | {"articulo": None, "link": None, "alertaDias": None}]


def test_put_eventos_requires_superadmin(client):
    res = client.put("/calendario/eventos", json=[], headers=_auth_headers())
    assert res.status_code == 403
```

- [ ] **Step 2: Correr — debe fallar**

```bash
cd api && python -m pytest ../tests/test_calendario.py -v
```

Expected: FAIL — `test_get_eventos_empty_when_no_s3_object` pasa (el archivo local tampoco existe, así que ya devuelve `[]`), pero `test_put_eventos_persists_to_s3_and_get_returns_it` falla porque hoy escribe a disco local, no a S3 (el `GET` posterior no lo vería vía el mock de S3 en un ambiente de test real donde el filesystem sí persiste entre el PUT y el GET de la misma llamada — para forzar el fallo real, confirmar corriendo el test tal cual: sin el cambio, el PUT escribe a `api/data/calendario_2026.json` en disco, así que el test en realidad "pasaría por accidente" escribiendo al filesystem real. Este es exactamente el bug que estamos corrigiendo — el test debe fallar por otra vía: verificar explícitamente que el objeto quedó en el S3 mockeado).

Ajustar el test para que la verificación real sea contra S3 directamente:

```python
def test_put_eventos_writes_to_s3(client, monkeypatch):
    headers = _superadmin_headers(monkeypatch)
    evento = {
        "id": "1", "fecha": "2026-09-15", "titulo": "IVA bimestral",
        "descripcion": "Vencimiento IVA", "tipo": "iva", "urgencia": "alta",
    }
    client.put("/calendario/eventos", json=[evento], headers=headers)

    s3 = boto3.client("s3", region_name="us-east-1")
    obj = s3.get_object(Bucket="taxops-job-artifacts-prod", Key=_CALENDARIO_KEY)
    import json
    data = json.loads(obj["Body"].read())
    assert data[0]["titulo"] == "IVA bimestral"
```

Correr de nuevo — este SÍ debe fallar limpio: `botocore.errorfactory.NoSuchKey` (nada se escribió a S3 porque el código todavía usa filesystem).

- [ ] **Step 3: Reescribir `calendario.py`**

```python
"""Calendario Tributario DIAN — router.

GET    /calendario/eventos          → lista de eventos (usuario autenticado)
PUT    /calendario/eventos          → reemplaza la lista completa (superadmin)
POST   /calendario/eventos          → agrega un evento (superadmin)
DELETE /calendario/eventos/{id}     → elimina un evento (superadmin)

Persistencia: S3 (config/calendario_2026.json, fuera del prefijo "uploads/" — no cae en el
lifecycle de 3 días). Antes usaba un archivo local (api/data/calendario_2026.json) — eso
funcionaba en Cloud Run (proceso continuo) pero no sobrevive en Lambda: cada execution
environment arranca desde la imagen del container, así que un PUT se perdía en el siguiente
cold start.
"""
from __future__ import annotations

import json

import boto3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import get_settings
from dependencies import get_current_user, require_superadmin

router = APIRouter(prefix="/calendario", tags=["Calendario"])

_S3_KEY = "config/calendario_2026.json"


def _load() -> list[dict]:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    try:
        obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=_S3_KEY)
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        return []


def _save(eventos: list[dict]) -> None:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    s3.put_object(
        Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
        Key=_S3_KEY,
        Body=json.dumps(eventos, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


class EventoCalendario(BaseModel):
    id: str
    fecha: str            # YYYY-MM-DD
    titulo: str
    descripcion: str
    tipo: str             # retencion | iva | renta | exogenas | ica | patrimonio | otro
    urgencia: str         # critica | alta | media | baja
    articulo: str | None = None
    link: str | None = None
    alertaDias: int | None = None


@router.get("/eventos", response_model=list[EventoCalendario])
async def get_eventos(current_user=Depends(get_current_user)):
    """Devuelve todos los eventos del calendario tributario activo."""
    return _load()


@router.put("/eventos", response_model=list[EventoCalendario])
async def replace_eventos(
    eventos: list[EventoCalendario],
    current_user=Depends(require_superadmin),
):
    """Reemplaza la lista completa de eventos. Solo superadmin."""
    data = [e.model_dump() for e in eventos]
    data.sort(key=lambda e: e["fecha"])
    _save(data)
    return data


@router.post("/eventos", response_model=EventoCalendario, status_code=201)
async def add_evento(
    evento: EventoCalendario,
    current_user=Depends(require_superadmin),
):
    """Agrega un evento individual. Solo superadmin."""
    eventos = _load()
    if any(e["id"] == evento.id for e in eventos):
        raise HTTPException(status_code=409, detail="Ya existe un evento con ese id")
    eventos.append(evento.model_dump())
    eventos.sort(key=lambda e: e["fecha"])
    _save(eventos)
    return evento


@router.delete("/eventos/{evento_id}", status_code=204)
async def delete_evento(
    evento_id: str,
    current_user=Depends(require_superadmin),
):
    """Elimina un evento por id. Solo superadmin."""
    eventos = _load()
    new = [e for e in eventos if e["id"] != evento_id]
    if len(new) == len(eventos):
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    _save(new)
```

- [ ] **Step 4: Correr — debe pasar**

```bash
python -m pytest tests/test_calendario.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Migrar el contenido actual de `calendario_2026.json` a S3 (una sola vez, a mano, antes de mergear)**

```bash
export AWS_PROFILE=taxops-admin
aws s3 cp api/data/calendario_2026.json s3://taxops-job-artifacts-prod/config/calendario_2026.json
```

- [ ] **Step 6: Correr la suite completa — nada roto**

```bash
python -m pytest -q
```

Expected: mismo conteo que el baseline + 4 nuevos.

- [ ] **Step 7: Commit**

```bash
git add api/routers/calendario.py tests/test_calendario.py
git commit -m "fix: Calendario DIAN migra de archivo local a S3

El archivo local no sobrevivía cold starts de Lambda (bug latente desde
la migración a AWS) — cada PUT se perdía. Mismo contrato HTTP, storage
real ahora en S3 (config/calendario_2026.json)."
```

---

### Task 4: `publish.py` de dian-monitor y monitor-niif (novedades)

**Files:**
- Create: `agents/contabilidad/dian-monitor/publish.py`
- Create: `agents/contabilidad/monitor-niif/publish.py`
- Modify: `agents/contabilidad/dian-monitor/agent.py` (llamar a publish tras `write_report`)
- Modify: `agents/contabilidad/monitor-niif/agent.py` (ídem)

**Interfaces:**
- Consumes: `agents._shared.db_publish.insert_novedad` (Task 2)
- Produces: filas en `novedades` con `tipo="dian"` / `tipo="niif"`

- [ ] **Step 1: Escribir `dian-monitor/publish.py`**

```python
"""agents/contabilidad/dian-monitor/publish.py — Valida el reporte del agente y lo inserta
en la tabla novedades. Falla (exit code != 0) si el reporte está vacío — eso hace que el job
de GitHub Actions se marque en rojo, visible, en vez de fallar en silencio."""
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))  # repo root, para "from agents._shared..."

from agents._shared.db_publish import insert_novedad  # noqa: E402


def publish(report: str) -> None:
    if not report or not report.strip():
        raise ValueError("El reporte del agente está vacío — no se publica nada")

    today = date.today()
    titulo = f"Novedades DIAN — semana del {today.isoformat()}"
    insert_novedad(tipo="dian", titulo=titulo, resumen=report, fecha_generado=today)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    publish(content)
    print("Novedad DIAN publicada en la tabla novedades.")
```

- [ ] **Step 2: Escribir `monitor-niif/publish.py`** (idéntico salvo `tipo`/título)

```python
"""agents/contabilidad/monitor-niif/publish.py — ver dian-monitor/publish.py, misma lógica
con tipo="niif"."""
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))

from agents._shared.db_publish import insert_novedad  # noqa: E402


def publish(report: str) -> None:
    if not report or not report.strip():
        raise ValueError("El reporte del agente está vacío — no se publica nada")

    today = date.today()
    titulo = f"Novedades NIIF — semana del {today.isoformat()}"
    insert_novedad(tipo="niif", titulo=titulo, resumen=report, fecha_generado=today)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    publish(content)
    print("Novedad NIIF publicada en la tabla novedades.")
```

- [ ] **Step 3: Conectar `agent.py` de ambos — modificar `main()`**

En `dian-monitor/agent.py`, reemplazar:

```python
def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run_agent(build_system_prompt(config), build_user_prompt(config), AGENT_DIR)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"reporte-dian-{today}.md", report)
    print(f"Reporte escrito en {output_path}")
```

por:

```python
def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run_agent(build_system_prompt(config), build_user_prompt(config), AGENT_DIR)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"reporte-dian-{today}.md", report)
    print(f"Reporte escrito en {output_path}")

    from publish import publish
    publish(report)
```

(Mismo cambio en `monitor-niif/agent.py`, ajustando el nombre del archivo de reporte si difiere — verificar con `grep "reporte-" monitor-niif/agent.py` antes de editar, no asumir el mismo nombre literal.)

- [ ] **Step 4: Test manual — correr end-to-end contra una DB de test**

```bash
cd agents/contabilidad/dian-monitor
DATABASE_URL="postgresql://localhost/taxops_test" GROQ_API_KEY="gsk_..." python agent.py
```

Expected: termina sin error, y `SELECT * FROM novedades WHERE tipo='dian'` en la DB de test muestra la fila nueva.

- [ ] **Step 5: Commit**

```bash
git add agents/contabilidad/dian-monitor/publish.py agents/contabilidad/dian-monitor/agent.py \
        agents/contabilidad/monitor-niif/publish.py agents/contabilidad/monitor-niif/agent.py
git commit -m "feat: dian-monitor y monitor-niif publican a la tabla novedades"
```

---

### Task 5: `publish.py` de prospector-clientes-contables (leads)

**Files:**
- Create: `agents/contabilidad/prospector-clientes-contables/publish.py`
- Modify: `agents/contabilidad/prospector-clientes-contables/agent.py`

**Interfaces:**
- Consumes: `agents._shared.db_publish.insert_lead` (Task 2)
- Produces: filas en `leads_comerciales`

**Nota**: a diferencia de dian-monitor/monitor-niif (reporte de texto libre → una fila), acá el agente debe devolver una LISTA de leads estructurados para poder insertar cada uno como fila separada — mismo criterio que vencimientos-tributarios (Task 6): pedirle al modelo un bloque ` ```json ` al final del reporte.

- [ ] **Step 1: Modificar el prompt para pedir salida JSON estructurada**

En `prospector-clientes-contables/agent.py`, ubicar `build_system_prompt` y agregar al final del prompt existente (no reemplazar el resto):

```python
    return f"""Eres un agente de prospección comercial para una firma contable colombiana.
[... resto del prompt existente sin cambios ...]

Al final de tu respuesta, agrega un bloque ```json con la lista de leads encontrados en este
formato exacto (lista vacía si no encontraste ninguno verificable):

```json
[
  {{"empresa": "...", "sector": "...", "ciudad": "...", "contacto": "...", "fuente_url": "..."}}
]
```
"""
```

- [ ] **Step 2: Escribir `publish.py`**

```python
"""agents/contabilidad/prospector-clientes-contables/publish.py — Extrae el bloque JSON del
reporte del agente y lo inserta en leads_comerciales (dedup por empresa+ciudad, ver Task 2)."""
import json
import re
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))

from agents._shared.db_publish import insert_lead  # noqa: E402

_JSON_BLOCK = re.compile(r"```json\s*(\[.*?\])\s*```", re.DOTALL)


def extract_leads(report: str) -> list[dict]:
    match = _JSON_BLOCK.search(report)
    if not match:
        raise ValueError("El reporte no contiene un bloque ```json``` con la lista de leads")
    leads = json.loads(match.group(1))
    if not isinstance(leads, list):
        raise ValueError("El bloque JSON no es una lista")
    return leads


def publish(report: str) -> int:
    leads = extract_leads(report)
    today = date.today()
    for lead in leads:
        insert_lead(
            empresa=lead["empresa"],
            sector=lead.get("sector", ""),
            ciudad=lead.get("ciudad", ""),
            contacto=lead.get("contacto", ""),
            fuente_url=lead.get("fuente_url", ""),
            fecha_generado=today,
        )
    return len(leads)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    n = publish(content)
    print(f"{n} lead(s) publicados en leads_comerciales.")
```

- [ ] **Step 3: Test unitario del parseo (sin DB, el punto frágil es el regex/JSON)**

```python
# agents/contabilidad/prospector-clientes-contables/test_publish.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from publish import extract_leads  # noqa: E402

_VALID_REPORT = """
## Leads encontrados
Encontré 2 empresas.

```json
[
  {"empresa": "Restaurante A", "sector": "restaurantes", "ciudad": "Medellín", "contacto": "a@a.com", "fuente_url": "https://a.com"},
  {"empresa": "Consultorio B", "sector": "salud", "ciudad": "Envigado", "contacto": "", "fuente_url": ""}
]
```
"""


def test_extract_leads_valid_json():
    leads = extract_leads(_VALID_REPORT)
    assert len(leads) == 2
    assert leads[0]["empresa"] == "Restaurante A"


def test_extract_leads_no_json_block_raises():
    with pytest.raises(ValueError, match="no contiene un bloque"):
        extract_leads("Reporte sin bloque json.")


def test_extract_leads_empty_list_is_valid():
    leads = extract_leads("```json\n[]\n```")
    assert leads == []
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/contabilidad/prospector-clientes-contables && python -m pytest test_publish.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Conectar en `agent.py`** (mismo patrón que Task 4, Step 3 — agregar `from publish import publish; publish(report)` al final de `main()`)

- [ ] **Step 6: Commit**

```bash
git add agents/contabilidad/prospector-clientes-contables/publish.py \
        agents/contabilidad/prospector-clientes-contables/test_publish.py \
        agents/contabilidad/prospector-clientes-contables/agent.py
git commit -m "feat: prospector-clientes-contables publica a leads_comerciales (JSON estructurado)"
```

---

### Task 6: `publish.py` de vencimientos-tributarios (Calendario DIAN vía S3)

**Files:**
- Create: `agents/contabilidad/vencimientos-tributarios/publish.py`
- Modify: `agents/contabilidad/vencimientos-tributarios/agent.py`

**Interfaces:**
- Consumes: mismo bucket/key que Task 3 (`S3_BUCKET_JOB_ARTIFACTS`, key `config/calendario_2026.json`) — pero escrito directo con boto3, no vía la API.
- Produces: eventos nuevos mezclados con los existentes en el calendario (no reemplaza la lista completa — un vencimiento generado hoy no debe borrar eventos curados a mano de otras fuentes).

**Nota de diseño**: a diferencia de dian-monitor/monitor-niif (una fila nueva por corrida) y de leads (dedup por empresa+ciudad), acá se necesita **merge por id** — si el agente vuelve a encontrar el mismo vencimiento (mismo `id` derivado de fecha+tipo), actualiza en vez de duplicar; eventos existentes que el agente no tocó se preservan.

- [ ] **Step 1: Modificar el prompt (agregar bloque JSON, mismo criterio que Task 5)**

En `vencimientos-tributarios/agent.py`, al final de `build_system_prompt`:

```python
Al final de tu respuesta, agrega un bloque ```json con los vencimientos encontrados en este
formato exacto (mismo shape que usa el Calendario Tributario DIAN de la plataforma):

```json
[
  {{
    "id": "vencimiento-2026-09-iva-bimestral",
    "fecha": "2026-09-15",
    "titulo": "Vencimiento IVA bimestral",
    "descripcion": "Declaración y pago IVA período jul-ago 2026",
    "tipo": "iva",
    "urgencia": "alta",
    "articulo": null,
    "link": null,
    "alertaDias": 5
  }}
]
```

El campo "id" debe ser estable y descriptivo (no un UUID aleatorio) para que corridas futuras
puedan actualizar el mismo evento en vez de duplicarlo.
"""
```

- [ ] **Step 2: Escribir `publish.py`**

```python
"""agents/contabilidad/vencimientos-tributarios/publish.py — Extrae el bloque JSON del reporte,
lo valida, y hace merge por id contra el calendario ya existente en S3 (no reemplaza la lista
completa — preserva eventos curados a mano o de otras fuentes)."""
import json
import re
import sys
from pathlib import Path

import boto3

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))

_JSON_BLOCK = re.compile(r"```json\s*(\[.*?\])\s*```", re.DOTALL)
_BUCKET = "taxops-job-artifacts-prod"
_KEY = "config/calendario_2026.json"
_REQUIRED_FIELDS = {"id", "fecha", "titulo", "descripcion", "tipo", "urgencia"}


def extract_eventos(report: str) -> list[dict]:
    match = _JSON_BLOCK.search(report)
    if not match:
        raise ValueError("El reporte no contiene un bloque ```json``` con los vencimientos")
    eventos = json.loads(match.group(1))
    if not isinstance(eventos, list):
        raise ValueError("El bloque JSON no es una lista")
    for e in eventos:
        faltantes = _REQUIRED_FIELDS - e.keys()
        if faltantes:
            raise ValueError(f"Evento sin campos obligatorios {faltantes}: {e}")
    return eventos


def merge_eventos(existentes: list[dict], nuevos: list[dict]) -> list[dict]:
    por_id = {e["id"]: e for e in existentes}
    for evento in nuevos:
        por_id[evento["id"]] = evento
    return sorted(por_id.values(), key=lambda e: e["fecha"])


def publish(report: str) -> int:
    nuevos = extract_eventos(report)

    s3 = boto3.client("s3", region_name="us-east-1")
    try:
        obj = s3.get_object(Bucket=_BUCKET, Key=_KEY)
        existentes = json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        existentes = []

    merged = merge_eventos(existentes, nuevos)
    s3.put_object(
        Bucket=_BUCKET, Key=_KEY,
        Body=json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return len(nuevos)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    n = publish(content)
    print(f"{n} vencimiento(s) mergeados en el Calendario DIAN.")
```

- [ ] **Step 3: Tests (parseo + merge, con moto para S3)**

```python
# agents/contabilidad/vencimientos-tributarios/test_publish.py
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent))
from publish import _BUCKET, _KEY, extract_eventos, merge_eventos, publish  # noqa: E402

_VALID_REPORT = """
## Vencimientos

```json
[
  {"id": "v1", "fecha": "2026-09-15", "titulo": "IVA bimestral", "descripcion": "desc",
   "tipo": "iva", "urgencia": "alta"}
]
```
"""


def test_extract_eventos_valid():
    eventos = extract_eventos(_VALID_REPORT)
    assert eventos[0]["id"] == "v1"


def test_extract_eventos_missing_field_raises():
    bad = '```json\n[{"id": "v1", "fecha": "2026-09-15"}]\n```'
    with pytest.raises(ValueError, match="campos obligatorios"):
        extract_eventos(bad)


def test_extract_eventos_no_block_raises():
    with pytest.raises(ValueError, match="no contiene un bloque"):
        extract_eventos("sin bloque json")


def test_merge_eventos_updates_by_id_preserves_others():
    existentes = [
        {"id": "v1", "fecha": "2026-01-01", "titulo": "viejo"},
        {"id": "v2", "fecha": "2026-02-01", "titulo": "otro evento, no tocado"},
    ]
    nuevos = [{"id": "v1", "fecha": "2026-09-15", "titulo": "IVA bimestral actualizado"}]

    merged = merge_eventos(existentes, nuevos)

    assert len(merged) == 2
    v1 = next(e for e in merged if e["id"] == "v1")
    assert v1["titulo"] == "IVA bimestral actualizado"
    assert any(e["id"] == "v2" for e in merged)  # v2 se preservó intacto


@mock_aws
def test_publish_end_to_end_writes_merged_to_s3():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=_BUCKET)
    import json
    s3.put_object(
        Bucket=_BUCKET, Key=_KEY,
        Body=json.dumps([{"id": "v2", "fecha": "2026-02-01", "titulo": "existente"}]).encode(),
    )

    n = publish(_VALID_REPORT)

    assert n == 1
    obj = s3.get_object(Bucket=_BUCKET, Key=_KEY)
    data = json.loads(obj["Body"].read())
    assert len(data) == 2  # el existente + el nuevo, ninguno se perdió
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/contabilidad/vencimientos-tributarios && python -m pytest test_publish.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Conectar en `agent.py`** (mismo patrón — agregar `from publish import publish; publish(report)` en `main()`)

- [ ] **Step 6: Commit**

```bash
git add agents/contabilidad/vencimientos-tributarios/publish.py \
        agents/contabilidad/vencimientos-tributarios/test_publish.py \
        agents/contabilidad/vencimientos-tributarios/agent.py
git commit -m "feat: vencimientos-tributarios publica al Calendario DIAN vía S3 (merge por id)"
```

---

### Task 7: Backend — `GET /novedades`

**Files:**
- Create: `api/routers/novedades.py`
- Modify: `api/schemas.py` (agregar `NovedadResponse`)
- Modify: `api/main.py` (registrar el router)
- Test: `tests/test_novedades.py`

**Interfaces:**
- Consumes: tabla `novedades` (Task 1)
- Produces: `GET /novedades?tipo=&limit=&offset=` — consumido por el frontend (Task 9)

- [ ] **Step 1: Agregar el schema**

En `api/schemas.py`, junto a los demás (buscar la sección `# ── Chatbot` y agregar antes, una sección nueva):

```python
# ── Novedades ─────────────────────────────────────────────────────────────────

class NovedadResponse(BaseModel):
    id: str
    tipo: str
    titulo: str
    resumen: str
    fecha_generado: str
```

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_novedades.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    return TestClient(load_fastapi_app())


def _auth_headers() -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role="contador", email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_list_novedades_requires_auth(client):
    res = client.get("/novedades")
    assert res.status_code in (401, 403)


def test_list_novedades_returns_list(client, monkeypatch):
    # db_available() será False sin una Postgres real — el endpoint debe degradar a lista vacía,
    # no crashear (mismo criterio que list_exogenas/list_invoices existentes)
    res = client.get("/novedades", headers=_auth_headers())
    assert res.status_code == 200
    assert res.json() == []
```

- [ ] **Step 3: Correr — debe fallar**

```bash
python -m pytest tests/test_novedades.py -v
```

Expected: FAIL — 404 (el router no existe todavía).

- [ ] **Step 4: Escribir `novedades.py`**

```python
"""Novedades router — feed de cambios DIAN/NIIF generado por los agentes contables
(agents/contabilidad/dian-monitor, monitor-niif). Ver docs/superpowers/specs/
2026-08-23-agentes-contables-integracion-design.md."""
from __future__ import annotations

from dependencies import get_current_user
from fastapi import APIRouter, Depends
from schemas import NovedadResponse

router = APIRouter(prefix="/novedades", tags=["Novedades"])


@router.get("/", response_model=list[NovedadResponse])
async def list_novedades(
    tipo: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
) -> list[NovedadResponse]:
    from db.database import db_available, get_db

    if not db_available():
        return []

    from sqlalchemy import text

    filters = []
    params: dict = {"limit": limit, "offset": offset}
    if tipo:
        filters.append("tipo = :tipo")
        params["tipo"] = tipo
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    f"SELECT id, tipo, titulo, resumen, fecha_generado FROM novedades {where} "
                    "ORDER BY fecha_generado DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().fetchall()
    except Exception:
        return []

    return [
        NovedadResponse(
            id=str(r["id"]), tipo=r["tipo"], titulo=r["titulo"],
            resumen=r["resumen"], fecha_generado=str(r["fecha_generado"]),
        )
        for r in rows
    ]
```

- [ ] **Step 5: Registrar en `main.py`**

Buscar el bloque `from routers import (...)` y `app.include_router(...)` (junto a `calendario`, `uploads`, etc.) y agregar `novedades` en ambos — seguir el mismo estilo exacto ya usado, verificar leyendo el archivo antes de editar.

- [ ] **Step 6: Correr — debe pasar**

```bash
python -m pytest tests/test_novedades.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Correr la suite completa + flake8**

```bash
python -m pytest -q
flake8 api/ --max-line-length=120
```

- [ ] **Step 8: Commit**

```bash
git add api/routers/novedades.py api/schemas.py api/main.py tests/test_novedades.py
git commit -m "feat: GET /novedades — feed de cambios DIAN/NIIF"
```

---

### Task 8: Backend — `GET /admin/leads`

**Files:**
- Modify: `api/routers/admin.py` (agregar el endpoint al router ya existente)
- Modify: `api/schemas.py` (agregar `LeadComercialResponse`)
- Test: `tests/test_admin_leads.py`

**Interfaces:**
- Consumes: tabla `leads_comerciales` (Task 1)
- Produces: `GET /admin/leads?ciudad=&sector=&limit=&offset=` (`require_admin`) — consumido por el frontend (Task 10)

- [ ] **Step 1: Agregar el schema** (junto a `NovedadResponse` en `api/schemas.py`)

```python
class LeadComercialResponse(BaseModel):
    id: str
    empresa: str
    sector: str | None = None
    ciudad: str | None = None
    contacto: str | None = None
    fuente_url: str | None = None
    fecha_generado: str
```

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_admin_leads.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import load_fastapi_app  # noqa: E402
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    return TestClient(load_fastapi_app())


def _headers(role: str) -> dict:
    from core.security import create_access_token
    token = create_access_token(sub="u1", org_id="org1", role=role, email="a@b.com")
    return {"Authorization": f"Bearer {token}"}


def test_list_leads_requires_admin(client):
    res = client.get("/admin/leads", headers=_headers("contador"))
    assert res.status_code == 403


def test_list_leads_returns_list_for_admin(client):
    res = client.get("/admin/leads", headers=_headers("owner"))
    assert res.status_code == 200
    assert res.json() == []
```

- [ ] **Step 3: Correr — debe fallar**

```bash
python -m pytest tests/test_admin_leads.py -v
```

Expected: FAIL — 404 (el endpoint no existe todavía).

- [ ] **Step 4: Agregar el endpoint a `api/routers/admin.py`**

Leer el archivo completo primero para copiar el estilo exacto de un endpoint `GET` existente (ej. `list_users`), luego agregar al final del archivo:

```python
@router.get("/leads", response_model=list[LeadComercialResponse])
async def list_leads(
    ciudad: str | None = None,
    sector: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(require_admin),
) -> list[LeadComercialResponse]:
    """Lista leads comerciales generados por el agente prospector-clientes-contables."""
    from db.database import db_available, get_db

    if not db_available():
        return []

    from sqlalchemy import text

    filters = []
    params: dict = {"limit": limit, "offset": offset}
    if ciudad:
        filters.append("ciudad = :ciudad")
        params["ciudad"] = ciudad
    if sector:
        filters.append("sector = :sector")
        params["sector"] = sector
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    f"SELECT id, empresa, sector, ciudad, contacto, fuente_url, fecha_generado "
                    f"FROM leads_comerciales {where} "
                    "ORDER BY fecha_generado DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().fetchall()
    except Exception:
        return []

    return [
        LeadComercialResponse(
            id=str(r["id"]), empresa=r["empresa"], sector=r["sector"], ciudad=r["ciudad"],
            contacto=r["contacto"], fuente_url=r["fuente_url"], fecha_generado=str(r["fecha_generado"]),
        )
        for r in rows
    ]
```

Agregar `LeadComercialResponse` al import de `schemas` al inicio del archivo (junto a los demás imports de `schemas` ya usados en `admin.py`).

- [ ] **Step 5: Correr — debe pasar**

```bash
python -m pytest tests/test_admin_leads.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Suite completa + flake8**

```bash
python -m pytest -q
flake8 api/ --max-line-length=120
```

- [ ] **Step 7: Commit**

```bash
git add api/routers/admin.py api/schemas.py tests/test_admin_leads.py
git commit -m "feat: GET /admin/leads — leads comerciales del agente prospector"
```

---

### Task 9: Frontend — página `/novedades`

**Files:**
- Create: `taxops-web/app/(app)/novedades/page.tsx`
- Modify: `taxops-web/components/layout/sidebar.tsx`

**Interfaces:**
- Consumes: `useApi().get("/novedades")` → `NovedadResponse[]` (Task 7)

- [ ] **Step 1: Agregar el ítem de menú**

En `sidebar.tsx`, importar el ícono `Newspaper` de `lucide-react` (agregar a la lista de imports existente) y agregar a `NAV_ITEMS` (después de "Calendario DIAN"):

```typescript
  { label: "Novedades", href: "/novedades", icon: <Newspaper size={18} /> },
```

- [ ] **Step 2: Escribir la página**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Newspaper } from "lucide-react";
import { useApi } from "@/lib/api";

type Novedad = {
  id: string;
  tipo: string;
  titulo: string;
  resumen: string;
  fecha_generado: string;
};

const TIPO_LABEL: Record<string, string> = { dian: "DIAN", niif: "NIIF" };
const TIPO_COLOR: Record<string, string> = {
  dian: "bg-blue-50 text-blue-700",
  niif: "bg-purple-50 text-purple-700",
};

export default function NovedadesPage() {
  const { get } = useApi();
  const [novedades, setNovedades] = useState<Novedad[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    get<Novedad[]>("/novedades")
      .then(setNovedades)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Error cargando novedades"))
      .finally(() => setLoading(false));
  }, [get]);

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-2">
        <Newspaper size={20} className="text-brand-orange" />
        <h1 className="text-lg font-semibold text-gray-900">Novedades tributarias y NIIF</h1>
      </div>
      <p className="text-sm text-gray-400">
        Resúmenes semanales generados automáticamente — DIAN (resoluciones, circulares, decretos) y NIIF.
      </p>

      {loading && <p className="text-sm text-gray-400">Cargando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && novedades.length === 0 && (
        <p className="text-sm text-gray-400">Todavía no hay novedades publicadas.</p>
      )}

      <div className="space-y-3">
        {novedades.map((n) => (
          <div key={n.id} className="card">
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TIPO_COLOR[n.tipo] ?? "bg-gray-50 text-gray-700"}`}>
                {TIPO_LABEL[n.tipo] ?? n.tipo.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400">{n.fecha_generado}</span>
            </div>
            <h2 className="font-medium text-gray-900 mb-1">{n.titulo}</h2>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{n.resumen}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verificar compilación**

```bash
cd taxops-web && npx tsc --noEmit && npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add taxops-web/app/\(app\)/novedades/page.tsx taxops-web/components/layout/sidebar.tsx
git commit -m "feat: página Novedades — feed de cambios DIAN/NIIF"
```

---

### Task 10: Frontend — página `/admin/leads`

**Files:**
- Create: `taxops-web/app/(app)/admin/leads/page.tsx`
- Modify: `taxops-web/components/layout/sidebar.tsx`

**Interfaces:**
- Consumes: `useApi().get("/admin/leads")` → `LeadComercialResponse[]` (Task 8)

- [ ] **Step 1: Agregar el ítem de menú (adminOnly)**

En `sidebar.tsx`, importar `Target` de `lucide-react` y agregar a `ADMIN_ITEMS`:

```typescript
  { label: "Leads", href: "/admin/leads", icon: <Target size={18} />, adminOnly: true },
```

- [ ] **Step 2: Escribir la página**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Target } from "lucide-react";
import { useApi } from "@/lib/api";

type Lead = {
  id: string;
  empresa: string;
  sector: string | null;
  ciudad: string | null;
  contacto: string | null;
  fuente_url: string | null;
  fecha_generado: string;
};

export default function LeadsPage() {
  const { get } = useApi();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    get<Lead[]>("/admin/leads")
      .then(setLeads)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Error cargando leads"))
      .finally(() => setLoading(false));
  }, [get]);

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center gap-2">
        <Target size={20} className="text-brand-orange" />
        <h1 className="text-lg font-semibold text-gray-900">Leads comerciales</h1>
      </div>
      <p className="text-sm text-gray-400">
        Empresas prospectadas automáticamente que podrían necesitar servicios contables.
      </p>

      {loading && <p className="text-sm text-gray-400">Cargando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && leads.length === 0 && (
        <p className="text-sm text-gray-400">Todavía no hay leads publicados.</p>
      )}

      {leads.length > 0 && (
        <div className="card p-0 overflow-hidden overflow-x-auto">
          <table className="text-sm w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Empresa</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Sector</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Ciudad</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Contacto</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2 text-gray-900">{l.empresa}</td>
                  <td className="px-3 py-2 text-gray-600">{l.sector ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-600">{l.ciudad ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-600">{l.contacto ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-400 text-xs">{l.fecha_generado}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verificar compilación**

```bash
cd taxops-web && npx tsc --noEmit && npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add taxops-web/app/\(app\)/admin/leads/page.tsx taxops-web/components/layout/sidebar.tsx
git commit -m "feat: página Leads comerciales (admin-only)"
```

---

### Task 11: Workflow de GitHub Actions — cron semanal

**Files:**
- Create: `.github/workflows/agentes-contables.yml`

**Interfaces:**
- Consumes: `GROQ_API_KEY`, `DATABASE_URL` (GitHub Secrets ya existentes), rol OIDC `github_actions_terraform` (ya existente, `AdministratorAccess`) para S3.

- [ ] **Step 1: Escribir el workflow**

```yaml
name: Agentes contables (cron semanal)

on:
  schedule:
    - cron: "0 11 * * 1"  # lunes 6am hora Colombia (UTC-5)
  workflow_dispatch: {}

permissions:
  id-token: write   # para el rol OIDC (escritura a S3)
  contents: read

jobs:
  dian-monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r agents/contabilidad/dian-monitor/requirements.txt
      - run: cd agents/contabilidad/dian-monitor && python agent.py
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

  monitor-niif:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r agents/contabilidad/monitor-niif/requirements.txt
      - run: cd agents/contabilidad/monitor-niif && python agent.py
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

  vencimientos-tributarios:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r agents/contabilidad/vencimientos-tributarios/requirements.txt boto3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_TERRAFORM_ROLE_ARN }}
          aws-region: us-east-1
      - run: cd agents/contabilidad/vencimientos-tributarios && python agent.py
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}

  prospector-clientes-contables:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r agents/contabilidad/prospector-clientes-contables/requirements.txt
      - run: cd agents/contabilidad/prospector-clientes-contables && python agent.py
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

(`AWS_TERRAFORM_ROLE_ARN` ya existe como GitHub Variable — usado igual por `terraform-plan.yml`/`terraform-apply.yml`, confirmar el nombre exacto leyendo uno de esos dos workflows antes de escribir este.)

- [ ] **Step 2: Probar manual antes de confiar en el cron**

Mergear a `main`, luego desde GitHub → Actions → "Agentes contables (cron semanal)" → "Run workflow" (dispara `workflow_dispatch`). Confirmar los 4 jobs en verde, y verificar:

```bash
export AWS_PROFILE=taxops-admin
aws s3 cp s3://taxops-job-artifacts-prod/config/calendario_2026.json - | python3 -m json.tool | tail -20
```

y una consulta directa a Neon confirmando filas nuevas en `novedades`/`leads_comerciales`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/agentes-contables.yml
git commit -m "feat: cron semanal para los 4 agentes contables (GitHub Actions)"
```

---

## Verificación final

1. `python -m pytest -q` — suite completa, 0 regresiones vs. baseline.
2. `flake8 api/ pipeline/ services/ agents/ --max-line-length=120`.
3. `cd taxops-web && npx tsc --noEmit && npm run lint`.
4. `terraform plan` — este plan no toca `infra/`, no debería haber diff de Terraform en absoluto (si aparece alguno inesperado, investigar antes de continuar).
5. Correr el workflow manual una vez (Task 11, Step 2) antes de dejar el cron activo sin supervisión.
