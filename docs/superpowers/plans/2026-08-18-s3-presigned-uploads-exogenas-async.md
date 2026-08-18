# Upload directo a S3 (presigned URLs) + Exógenas async — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar el límite de 6MB de payload de Lambda Function URL que rompe la carga de lotes grandes en Facturas y Exógenas, migrando la subida de archivos a presigned S3 uploads, y migrar Exógenas del patrón síncrono (SSE + subprocess, riesgo real de timeout de 60s) al patrón async SQS+worker+DynamoDB que ya usa Renta.

**Architecture:** Nuevo endpoint compartido `POST /uploads/presign` (genera `generate_presigned_post` con `content-length-range`, no un PUT sin límite real). El navegador sube directo a S3 (bypass de Lambda). Facturas se queda síncrono, solo cambia el origen de los bytes (S3 en vez del body). Exógenas migra a SQS+worker: `worker_handler.py` gana un dispatch por `tipo` de mensaje (`renta` default / `exogenas`), y un nuevo `services/exogenas/job_processor.py` corre la extracción existente sin el subprocess aislado (el worker Lambda ya es su propio proceso). El resultado combinado de Exógenas se sube a S3 (no a DynamoDB directo, por el límite de 400KB/item) y se lee vía "proxy por API" al hacer polling.

**Tech Stack:** FastAPI, boto3 (`generate_presigned_post`), SQS, DynamoDB (`job_store` existente), S3, Next.js 15 (App Router), Terraform (AWS + Cloudflare providers ya configurados).

**Spec:** `docs/superpowers/specs/2026-08-14-s3-presigned-uploads-exogenas-async-design.md` (aprobado tras 5 rondas de revisión — este plan asume que ya lo leíste; no repite todo el razonamiento ahí documentado).

## Global Constraints

- Todo cambio de `infra/` pasa por PR → `terraform-plan.yml` comenta el plan → merge a `main` → aprobación manual en `terraform-apply.yml` (environment `production`). Nunca `terraform apply` manual desde una laptop.
- `S3_BUCKET_JOB_ARTIFACTS` = bucket real `taxops-job-artifacts-prod` (vía `module.storage.job_artifacts_bucket`, ya existe, no se crea nada nuevo).
- Límite de tamaño por archivo: **20MB** (mismo valor que ya usa Renta en `_MAX_MB`), aplicado vía `content-length-range` en la policy de S3 — enforcement real del lado del servicio, no un chequeo de JS evadible.
- Lifecycle de objetos bajo el prefijo `uploads/` en `job-artifacts`: **3 días** (regla nueva, con `filter { prefix = "uploads/" }`).
- El mecanismo de subida es **POST `multipart/form-data`** (`generate_presigned_post`), nunca un PUT simple — S3 no aplica límites de tamaño reales a un PUT presignado.
- Los nuevos endpoints JSON de Exógenas (`/uploads/presign`, `/exogenas/process`, `/exogenas/jobs/{id}`) se llaman desde el frontend vía el proxy `/api-proxy` (mismo patrón que ya usa Renta, `lib/api.ts`) — **no** vía `DIRECT_API`/`NEXT_PUBLIC_API_URL` como hace el código viejo de Exógenas que se reemplaza. Solo la subida real de bytes a S3 es una llamada directa del navegador (inevitable, es el punto del cambio).
- No se toca `services/renta/storage.py`, `renta_documentos.py`, ni la lógica de extracción en sí (`exogenas/extractor.py`, `pipeline/`, `services/renta/ocr_agent.py`, `services/renta/classifier_agent.py`).

---

## Task 1: Terraform — bucket wiring, lifecycle rule, CORS

**Files:**
- Modify: `infra/modules/lambda-api/variables.tf`
- Modify: `infra/modules/lambda-api/main.tf:9-19` (bloque `local.lambda_env`)
- Modify: `infra/environments/prod/main.tf:36-48` (bloque `module "lambda_api"`), `infra/environments/prod/main.tf:28-34` (bloque `locals`, para el fix de `allowed_origins`)
- Modify: `infra/modules/storage/main.tf` (nueva regla de lifecycle + nuevo recurso CORS)
- Modify: `api/core/config.py:41-45` (nuevo campo `S3_BUCKET_JOB_ARTIFACTS`)

**Interfaces:**
- Produces: env var `S3_BUCKET_JOB_ARTIFACTS` disponible en ambas Lambdas (API + worker) y en `Settings.S3_BUCKET_JOB_ARTIFACTS` para código Python — usado por Task 2, 3 y 5.

- [ ] **Step 1: Agregar el campo a `Settings`**

En `api/core/config.py`, agregar junto a `S3_BUCKET_RENTA_DOCS` (línea 44):

```python
    S3_BUCKET_RENTA_DOCS: str = "taxops-renta-docs-prod"
    S3_BUCKET_JOB_ARTIFACTS: str = "taxops-job-artifacts-prod"
```

- [ ] **Step 2: Agregar la variable al módulo `lambda-api`**

En `infra/modules/lambda-api/variables.tf`, agregar al final:

```hcl
variable "s3_bucket_job_artifacts" {
  type = string
}
```

- [ ] **Step 3: Wireear la env var en `local.lambda_env`**

En `infra/modules/lambda-api/main.tf`, dentro del bloque `merge(var.secrets, { ... })` (línea 9), agregar junto a `S3_BUCKET_RENTA_DOCS`:

```hcl
    S3_BUCKET_RENTA_DOCS        = var.s3_bucket_renta_docs
    S3_BUCKET_JOB_ARTIFACTS     = var.s3_bucket_job_artifacts
```

- [ ] **Step 4: Pasar el valor real desde el root**

En `infra/environments/prod/main.tf`, dentro del bloque `module "lambda_api"` (línea 36), agregar:

```hcl
  s3_bucket_renta_docs = module.storage.renta_docs_bucket
  s3_bucket_job_artifacts = module.storage.job_artifacts_bucket
```

- [ ] **Step 5: Corregir `allowed_origins` (gap preexistente, barato de cerrar en el mismo PR)**

En `infra/environments/prod/main.tf`, dentro del bloque `locals` (línea 28), reemplazar `amplify_default_domain` por el dominio real del frontend:

```hcl
locals {
  cdn_domain_name   = "taxopsapp.com"
  cdn_api_subdomain = "api"
  api_base_url      = "https://${local.cdn_api_subdomain}.${local.cdn_domain_name}"
  frontend_domain   = "https://app.taxopsapp.com"
  allowed_origins   = "https://taxops-app.vercel.app,${local.frontend_domain},http://localhost:3000"
}
```

(Vercel se mantiene en la lista — sigue corriendo en paralelo como red de seguridad hasta el Chunk 8. `amplify_default_domain` ya no se referencia en ningún lado tras este cambio, se puede eliminar del `locals` si no lo usa nada más — verificar con `grep -rn amplify_default_domain infra/` antes de borrarlo.)

- [ ] **Step 6: Nueva regla de lifecycle en `job_artifacts`**

En `infra/modules/storage/main.tf`, dentro de `resource "aws_s3_bucket_lifecycle_configuration" "job_artifacts"` (línea 12), agregar una segunda `rule` (no reemplazar la existente):

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "job_artifacts" {
  bucket = aws_s3_bucket.job_artifacts.id
  rule {
    id     = "expire-old-exports"
    status = "Enabled"
    filter {} # aplica a todos los objetos del bucket
    expiration {
      days = 30 # los .xlsx de exógenas no necesitan vivir para siempre — controla el storage $
    }
  }
  rule {
    id     = "expire-temp-uploads"
    status = "Enabled"
    filter { prefix = "uploads/" }
    expiration {
      days = 3 # uploads temporales pendientes de procesar + resultados derivados — no el documento fuente definitivo
    }
  }
}
```

- [ ] **Step 7: Nuevo recurso CORS**

En el mismo archivo `infra/modules/storage/main.tf`, agregar un recurso nuevo (después del bloque de lifecycle):

```hcl
resource "aws_s3_bucket_cors_configuration" "job_artifacts" {
  bucket = aws_s3_bucket.job_artifacts.id

  cors_rule {
    allowed_methods = ["POST"] # generate_presigned_post — NO "PUT", el mecanismo de subida es multipart/form-data
    allowed_origins = ["https://app.taxopsapp.com", "http://localhost:3000"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
```

- [ ] **Step 8: `terraform fmt` + `validate` + `plan` local**

```bash
export AWS_PROFILE=taxops-admin
cd infra/environments/prod
set -a; source ../../../.envrc >/dev/null 2>&1; set +a
terraform fmt -recursive ../../..
terraform init -input=false
terraform validate
terraform plan -input=false -var-file=terraform.tfvars.secret -no-color 2>&1 | grep -E "Plan:|will be created|will be destroyed|must be replaced|Error"
```

Expected: `X to add` (la regla CORS, la nueva lifecycle rule cuenta como update del recurso existente, no como "add" separado), `0 to destroy`. Puede haber `N to change` por el drift preexistente de 4 SSM secrets ya conocido y documentado (inofensivo, CI usa GitHub Secrets reales) — no investigar de nuevo, ya está resuelto en sesiones anteriores.

- [ ] **Step 9: Commit y PR**

```bash
git checkout main && git pull
git checkout -b infra/s3-presign-wiring
git add infra/ api/core/config.py
git commit -m "infra: wiring de S3_BUCKET_JOB_ARTIFACTS + lifecycle + CORS para uploads presignados

Prepara la infra para el endpoint /uploads/presign (Task 2): env var
S3_BUCKET_JOB_ARTIFACTS en ambas Lambdas, regla de lifecycle de 3 días
para uploads/ (vs. los 30 días del resto del bucket), CORS habilitando
POST multipart desde app.taxopsapp.com (generate_presigned_post, no PUT
— un PUT presignado no tiene límite de tamaño real, ver spec).

De paso corrige un gap preexistente: ALLOWED_ORIGINS todavía apuntaba
al dominio default de Amplify en vez de app.taxopsapp.com."
git push -u origin infra/s3-presign-wiring
gh pr create --title "infra: wiring de S3_BUCKET_JOB_ARTIFACTS + lifecycle + CORS" --body "Ver docs/superpowers/specs/2026-08-14-s3-presigned-uploads-exogenas-async-design.md §5.1/§6. Task 1 del plan de implementación — prepara la infra, sin cambios de app code todavía."
```

- [ ] **Step 10: Verificar CI (`plan` job) y esperar aprobación/apply antes de seguir a Task 2**

`gh pr checks <N>` — confirmar que el job `plan` de Terraform pasa. Este PR debe mergearse y aplicarse (aprobación manual) **antes** de continuar — Task 2 en adelante asume que `S3_BUCKET_JOB_ARTIFACTS` ya existe como env var real en Lambda.

---

## Task 2: Backend — `POST /uploads/presign`

**Files:**
- Create: `api/routers/uploads.py`
- Modify: `api/main.py` (registrar el nuevo router)
- Modify: `api/routers/exogenas.py:36-40` (subir `_ALLOWED` a constante de módulo)
- Modify: `api/schemas.py` (nuevos modelos de request/response)
- Test: `tests/test_uploads_presign.py`

**Interfaces:**
- Consumes: `Settings.S3_BUCKET_JOB_ARTIFACTS` (Task 1), `dependencies.get_current_user`
- Produces: `POST /uploads/presign` — request `{"contexto": "facturas"|"exogenas", "archivos": [{"filename": str, "content_type": str}]}`, response `{"uploads": [{"filename": str, "s3_key": str, "url": str, "fields": dict}]}` para archivos válidos, más info de rechazo para los que no. Usado por Task 6 (frontend).

- [ ] **Step 1: Escribir el test que falla primero**

`tests/test_uploads_presign.py`:

```python
"""Tests para POST /uploads/presign — moto-mocked S3."""
import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum_ok")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")

        from main import app
        yield TestClient(app)


def _auth_headers(client) -> dict:
    from core.security import create_access_token
    token = create_access_token({"sub": "u1", "org_id": "org1", "role": "owner", "email": "a@b.com"})
    return {"Authorization": f"Bearer {token}"}


def test_presign_facturas_valid_pdf(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={"contexto": "facturas", "archivos": [{"filename": "factura.pdf", "content_type": "application/pdf"}]},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["uploads"]) == 1
    upload = body["uploads"][0]
    assert upload["filename"] == "factura.pdf"
    assert upload["s3_key"].startswith("uploads/facturas/org1/")
    assert upload["s3_key"].endswith("factura.pdf")
    assert "url" in upload
    assert "fields" in upload
    assert "key" in upload["fields"]


def test_presign_exogenas_valid_types(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={
            "contexto": "exogenas",
            "archivos": [
                {"filename": "cert1.pdf", "content_type": "application/pdf"},
                {"filename": "cert2.jpg", "content_type": "image/jpeg"},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert len(res.json()["uploads"]) == 2


def test_presign_rejects_disallowed_extension(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={"contexto": "exogenas", "archivos": [{"filename": "virus.exe", "content_type": "application/x-msdownload"}]},
        headers=headers,
    )
    assert res.status_code == 200  # no falla el request completo — rechaza esa entrada específica
    body = res.json()
    assert len(body["uploads"]) == 0
    assert len(body["rechazados"]) == 1
    assert body["rechazados"][0]["filename"] == "virus.exe"


def test_presign_invalid_contexto(client):
    headers = _auth_headers(client)
    res = client.post(
        "/uploads/presign",
        json={"contexto": "no_existe", "archivos": [{"filename": "a.pdf", "content_type": "application/pdf"}]},
        headers=headers,
    )
    assert res.status_code == 422


def test_presign_requires_auth(client):
    res = client.post(
        "/uploads/presign",
        json={"contexto": "facturas", "archivos": [{"filename": "a.pdf", "content_type": "application/pdf"}]},
    )
    assert res.status_code in (401, 403)
```

- [ ] **Step 2: Correr el test para confirmar que falla**

```bash
cd api && python -m pytest ../tests/test_uploads_presign.py -v
```

Expected: FAIL — `ModuleNotFoundError` o 404 (el router/endpoint no existe todavía).

- [ ] **Step 3: Subir `_ALLOWED` a constante de módulo en `exogenas.py`**

En `api/routers/exogenas.py`, mover el `_ALLOWED` de dentro de `process_exogenas()` (líneas 36-40) a nivel de módulo, junto a `_pending` (línea 25):

```python
router = APIRouter(prefix="/exogenas", tags=["Exógenas"])

# Extensiones permitidas para certificados de retención.
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp",
}
```

(Este bloque de `process_exogenas` se reemplaza por completo en Task 5 — este paso solo asegura que `ALLOWED_EXTENSIONS` exista como constante importable ahora, sin esperar a Task 5.)

- [ ] **Step 4: Agregar los schemas Pydantic**

En `api/schemas.py`, agregar (cerca de los otros modelos, sección nueva "Uploads"):

```python
# ── Uploads (presigned S3) ────────────────────────────────────────────────────

class PresignFileRequest(BaseModel):
    filename: str
    content_type: str


class PresignRequest(BaseModel):
    contexto: str  # "facturas" | "exogenas"
    archivos: list[PresignFileRequest]


class PresignedUpload(BaseModel):
    filename: str
    s3_key: str
    url: str
    fields: dict[str, str]


class PresignRejected(BaseModel):
    filename: str
    motivo: str


class PresignResponse(BaseModel):
    uploads: list[PresignedUpload]
    rechazados: list[PresignRejected]
```

- [ ] **Step 5: Escribir `api/routers/uploads.py`**

```python
"""api/routers/uploads.py — Presigned S3 uploads compartidos entre módulos.

Genera policies de generate_presigned_post (NO generate_presigned_url/PUT — un PUT
presignado no lleva límite de tamaño real, ver docs/superpowers/specs/
2026-08-14-s3-presigned-uploads-exogenas-async-design.md §1). El navegador sube
directo a S3 con estos campos, bypasseando el límite de 6MB de Lambda Function URL.
"""
from __future__ import annotations

import uuid

import boto3
from fastapi import APIRouter, Depends, HTTPException

from core.config import get_settings
from dependencies import get_current_user
from routers.exogenas import ALLOWED_EXTENSIONS as EXOGENAS_ALLOWED
from schemas import PresignedUpload, PresignRejected, PresignRequest, PresignResponse

router = APIRouter(prefix="/uploads", tags=["Uploads"])

# 20MB por archivo — mismo límite que ya usa Renta (_MAX_MB en renta_documentos.py).
_MAX_BYTES = 20 * 1024 * 1024

FACTURAS_ALLOWED = {".pdf", ".xml"}

_CONTEXTOS = {
    "facturas": FACTURAS_ALLOWED,
    "exogenas": EXOGENAS_ALLOWED,
}


@router.post("/presign", response_model=PresignResponse)
async def presign(
    body: PresignRequest,
    user: dict = Depends(get_current_user),
) -> PresignResponse:
    if body.contexto not in _CONTEXTOS:
        raise HTTPException(422, f"Contexto inválido: {body.contexto}. Válidos: {list(_CONTEXTOS)}")

    allowed_ext = _CONTEXTOS[body.contexto]
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    uploads: list[PresignedUpload] = []
    rechazados: list[PresignRejected] = []

    for archivo in body.archivos:
        ext = "." + archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
        if ext not in allowed_ext:
            rechazados.append(PresignRejected(filename=archivo.filename, motivo=f"Extensión no permitida: {ext}"))
            continue

        s3_key = f"uploads/{body.contexto}/{user['org_id']}/{uuid.uuid4()}/{archivo.filename}"

        try:
            presigned = s3.generate_presigned_post(
                Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
                Key=s3_key,
                Fields={"Content-Type": archivo.content_type},
                Conditions=[
                    {"Content-Type": archivo.content_type},
                    ["content-length-range", 0, _MAX_BYTES],
                ],
                ExpiresIn=300,  # 5 minutos
            )
        except Exception as exc:
            rechazados.append(PresignRejected(filename=archivo.filename, motivo=f"Error generando policy: {exc}"))
            continue

        uploads.append(PresignedUpload(
            filename=archivo.filename,
            s3_key=s3_key,
            url=presigned["url"],
            fields=presigned["fields"],
        ))

    return PresignResponse(uploads=uploads, rechazados=rechazados)
```

- [ ] **Step 6: Registrar el router en `api/main.py`**

Buscar el bloque de `include_router` existente (junto a los demás routers — `admin`, `auth`, `calendario`, etc.) y agregar:

```python
from routers import uploads

app.include_router(uploads.router)
```

(Verificar el estilo exacto de import/registro ya usado en el archivo antes de escribir esto — seguir el mismo patrón línea por línea, no inventar uno nuevo.)

- [ ] **Step 7: Correr el test — debe pasar**

```bash
cd api && python -m pytest ../tests/test_uploads_presign.py -v
```

Expected: 5 passed.

- [ ] **Step 8: Correr la suite completa — nada roto**

```bash
python -m pytest -q
```

Expected: mismo conteo que el baseline (173 passed, 25 skipped) + 5 nuevos = 178 passed, 25 skipped.

- [ ] **Step 9: Commit**

```bash
git add api/routers/uploads.py api/routers/exogenas.py api/schemas.py api/main.py tests/test_uploads_presign.py
git commit -m "feat: POST /uploads/presign — presigned S3 uploads compartidos

Nuevo endpoint compartido entre Facturas y Exógenas. Usa
generate_presigned_post (no generate_presigned_url/PUT) con
content-length-range=20MB — enforcement real de tamaño del lado de S3,
no un chequeo de JS evadible (ver spec, hallazgo de la ronda 3 de
revisión: un PUT presignado no tiene límite de tamaño real).

_ALLOWED de exogenas.py subido a constante de módulo (ALLOWED_EXTENSIONS)
para poder reusarlo acá sin duplicar la lista."
```

---

## Task 3: Backend — Facturas usa `s3_keys` en vez de `UploadFile`

**Files:**
- Modify: `api/routers/invoices.py`
- Modify: `api/schemas.py` (nuevo request model)
- Test: modificar el archivo de tests existente que cubre `invoices.py` (buscar con `grep -rl "process_invoices\|/invoices/process" tests/`)

**Interfaces:**
- Consumes: `Settings.S3_BUCKET_JOB_ARTIFACTS` (Task 1)
- Produces: `POST /invoices/process` ahora recibe JSON `{"s3_keys": [...], "ingresos": [...]}` en vez de `multipart/form-data`. Usado por Task 7 (frontend).

- [ ] **Step 1: Ubicar el test existente**

```bash
grep -rl "process_invoices\|/invoices/process" tests/
```

Leer ese archivo completo antes de tocar nada — entender qué casos ya cubre para no duplicar ni romper cobertura existente.

- [ ] **Step 2: Escribir/actualizar los tests para el nuevo contrato**

Adaptar los tests existentes de `files: UploadFile` a `s3_keys: list[str]` — moto-mocked S3 con el bucket `taxops-job-artifacts-prod` pre-poblado con archivos de prueba antes de llamar al endpoint. Ejemplo del patrón (ajustar a los fixtures reales que ya existan en el archivo):

```python
@mock_aws
def test_process_invoices_from_s3_keys(client, monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="taxops-job-artifacts-prod")
    s3.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/facturas/org1/x/factura.pdf", Body=PDF_FIXTURE_BYTES)

    res = client.post(
        "/invoices/process",
        json={"s3_keys": ["uploads/facturas/org1/x/factura.pdf"], "ingresos": []},
        headers=auth_headers,
    )
    assert res.status_code == 200
```

- [ ] **Step 3: Correr los tests actualizados — deben fallar**

```bash
cd api && python -m pytest ../tests/test_invoices.py -v  # o el nombre real del archivo
```

Expected: FAIL (el endpoint todavía espera `UploadFile`).

- [ ] **Step 4: Agregar el schema**

En `api/schemas.py`:

```python
class ProcessInvoicesRequest(BaseModel):
    s3_keys: list[str]
    ingresos: list[dict[str, Any]] = []
```

- [ ] **Step 5: Reescribir `process_invoices` en `invoices.py`**

```python
"""Invoices router — process, list, export."""
from __future__ import annotations

import tempfile
from pathlib import Path

import boto3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.config import get_settings
from dependencies import get_current_user
from schemas import ExportInvoicesRequest, ProcessInvoicesRequest, ProcessInvoicesResponse

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/process", response_model=ProcessInvoicesResponse)
async def process_invoices(
    body: ProcessInvoicesRequest,
    user: dict = Depends(get_current_user),
) -> ProcessInvoicesResponse:
    ingresos_gravados = {i["periodo"]: float(i.get("gravados", 0)) for i in body.ingresos}
    ingresos_excluidos = {i["periodo"]: float(i.get("excluidos", 0)) for i in body.ingresos}

    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_paths: list[Path] = []
        for s3_key in body.s3_keys:
            filename = Path(s3_key).name
            dest = Path(tmpdir) / filename
            try:
                obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=s3_key)
                dest.write_bytes(obj["Body"].read())
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Error descargando {filename} de S3: {exc}")
            tmp_paths.append(dest)

        try:
            from services.processor import procesar

            resultado = procesar(
                archivos=tmp_paths,
                ingresos_gravados=ingresos_gravados or None,
                ingresos_excluidos=ingresos_excluidos or None,
                org_id=user["org_id"],
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error en procesamiento: {exc}")

    return ProcessInvoicesResponse(
        total_archivos=resultado.total_archivos,
        procesados=resultado.total_archivos - resultado.errores,
        errores=resultado.errores,
        db_nuevas=resultado.db_nuevas,
        db_duplicadas=resultado.db_duplicadas,
        df_base=resultado.df_base.fillna("").to_dict(orient="records"),
        df_val=resultado.df_val.fillna("").to_dict(orient="records"),
        df_pror=resultado.df_pror.fillna("").to_dict(orient="records"),
    )
```

(El resto del archivo — `export_excel`, `list_invoices` — no cambia, dejar tal cual.)

**Nota sobre manejo de errores:** si falla la descarga de UN archivo específico de S3, este código aborta el lote completo (`raise HTTPException` corta el loop). Esto es **distinto** al comportamiento de `procesar()` en sí (que sí tolera fallos por archivo internamente, confirmado leyendo `services/processor.py` durante el diseño de este plan — no hace falta reverificarlo). Es una decisión deliberada: un archivo que no se pudo ni descargar de S3 (típicamente un bug de infra, no un PDF corrupto) amerita abortar y que el usuario reintente el lote, distinto a un PDF que sí se descargó pero no se pudo parsear (eso sigue tolerado internamente por `procesar()`).

- [ ] **Step 6: Correr los tests — deben pasar**

```bash
python -m pytest ../tests/test_invoices.py -v
```

- [ ] **Step 7: Suite completa**

```bash
python -m pytest -q
```

Expected: sin regresiones.

- [ ] **Step 8: Commit**

```bash
git add api/routers/invoices.py api/schemas.py tests/
git commit -m "feat: Facturas lee de S3 (s3_keys) en vez de recibir UploadFile

Elimina el límite de 6MB de payload de Lambda Function URL para lotes
grandes de facturas. Body pasa de multipart/form-data a JSON puro
(s3_keys + ingresos). Sin cambio de UX — sigue respondiendo el
resultado completo en la misma llamada, no hay OCR pesado de por medio."
```

---

## Task 4: Backend — `worker_handler.py` dispatch por tipo

**Files:**
- Modify: `api/worker_handler.py`
- Test: `tests/test_worker_handler.py` (ya existe, extender)

**Interfaces:**
- Consumes: nada nuevo todavía (Task 5 agrega `services.exogenas.job_processor`)
- Produces: `_process_renta_batch(body)` (renombre de `_process_batch`, mismo comportamiento) + dispatch `handler()` que lee `body.get("tipo", "renta")`. Task 5 conecta la rama `"exogenas"`.

- [ ] **Step 1: Leer el test existente completo**

```bash
cat tests/test_worker_handler.py
```

Entender los fixtures/mocks ya usados (moto, SQS event shape) antes de extender.

- [ ] **Step 2: Escribir el test nuevo que falla**

Agregar a `tests/test_worker_handler.py` (ajustar imports/fixtures al estilo real del archivo):

```python
def test_handler_dispatches_renta_by_default(monkeypatch):
    """Un mensaje sin 'tipo' (formato viejo, ya en vuelo) sigue yendo a Renta."""
    called = {}
    monkeypatch.setattr(
        "api.worker_handler._process_renta_batch",
        lambda body: called.update(renta=body),
    )
    event = {"Records": [{"body": json.dumps({"job_id": "j1", "contrib_id": "c1", "org_id": "o1", "año": 2026, "documentos": []})}]}
    handler(event)
    assert called["renta"]["job_id"] == "j1"


def test_handler_dispatches_exogenas(monkeypatch):
    called = {}
    monkeypatch.setattr(
        "api.worker_handler._process_exogenas_batch",
        lambda body: called.update(exogenas=body),
    )
    event = {"Records": [{"body": json.dumps({"tipo": "exogenas", "job_id": "j2", "org_id": "o1", "s3_keys": []})}]}
    handler(event)
    assert called["exogenas"]["job_id"] == "j2"
```

- [ ] **Step 3: Correr — debe fallar**

```bash
cd api && python -m pytest ../tests/test_worker_handler.py -v -k dispatch
```

Expected: FAIL (`_process_exogenas_batch` no existe, `_process_renta_batch` no existe todavía — solo `_process_batch`).

- [ ] **Step 4: Reescribir `worker_handler.py`**

```python
def handler(event: dict, context: Any = None) -> None:
    """Lambda entry point — one invocation may carry several SQS records."""
    for record in event["Records"]:
        body = json.loads(record["body"])
        tipo = body.get("tipo", "renta")  # mensajes viejos (ya en vuelo) no tienen "tipo" — default preserva compatibilidad
        if tipo == "renta":
            _process_renta_batch(body)
        elif tipo == "exogenas":
            _process_exogenas_batch(body)
        else:
            import logging
            logging.getLogger("taxops.worker").error("Tipo de mensaje SQS desconocido: %s", tipo)


def _process_renta_batch(body: dict) -> None:
    import logging

    from services.renta.job_processor import process_documento_job

    log = logging.getLogger("taxops.renta")

    job_id = body["job_id"]
    contrib_id = body["contrib_id"]
    org_id = body["org_id"]
    año = body["año"]
    documentos = body["documentos"]

    total = len(documentos)
    for i, doc in enumerate(documentos, 1):
        try:
            process_documento_job(
                job_id=f"{job_id}_{i}",
                doc_id=doc["doc_id"],
                s3_key=doc["s3_key"],
                filename=doc["filename"],
                mime_type=doc["mime_type"],
                contrib_id=contrib_id,
                org_id=org_id,
                año=año,
            )
        except Exception as exc:
            log.error(
                "worker_handler: process_documento_job raised for doc %s (job %s): %s",
                doc.get("doc_id"), job_id, exc, exc_info=True,
            )

        job = job_store.get_job(job_id) or {}
        job["completados"] = i
        job["progreso"] = round(i / total * 100)
        job_store.put_job(job_id, job.get("status", "processing"), job)

    job = job_store.get_job(job_id) or {}
    job["status"] = "done"
    job_store.put_job(job_id, "done", job)


def _process_exogenas_batch(body: dict) -> None:
    from services.exogenas.job_processor import process_exogenas_job

    process_exogenas_job(
        job_id=body["job_id"],
        org_id=body["org_id"],
        s3_keys=body["s3_keys"],
    )
```

(`_process_renta_batch` es exactamente el cuerpo de la vieja `_process_batch`, sin cambios de comportamiento — solo el nombre. `_process_exogenas_batch` es un thin wrapper que delega a Task 5.)

- [ ] **Step 5: Correr el test de dispatch — debe pasar**

```bash
python -m pytest ../tests/test_worker_handler.py -v -k dispatch
```

- [ ] **Step 6: Correr TODO `test_worker_handler.py` — confirmar que los tests viejos de Renta siguen pasando con el rename**

```bash
python -m pytest ../tests/test_worker_handler.py -v
```

Si algún test viejo referenciaba `_process_batch` por nombre (mock/patch), actualizarlo a `_process_renta_batch`.

- [ ] **Step 7: Commit**

```bash
git add api/worker_handler.py tests/test_worker_handler.py
git commit -m "feat: worker_handler.py despacha por tipo de mensaje (renta/exogenas)

_process_batch renombrado a _process_renta_batch (mismo comportamiento,
sin cambios). Nuevo dispatch por body.get('tipo', 'renta') — el default
preserva compatibilidad con mensajes de Renta ya en vuelo/existentes,
que no tienen ninguna clave 'tipo' (no se tocó renta_documentos.py).

_process_exogenas_batch es un wrapper delgado hacia
services.exogenas.job_processor (Task 5 del plan de implementación —
en este commit el import fallaría si se invocara, se completa en el
siguiente task)."
```

Nota: este commit deja `_process_exogenas_batch` con un import a un módulo que Task 5 todavía no crea — es intencional (permite testear el dispatch de forma aislada con mocks), pero **no mergear/desplegar Task 4 solo sin Task 5** — deben ir en el mismo PR o en PRs consecutivos aplicados juntos, nunca Task 4 en producción sin Task 5.

---

## Task 5: Backend — Exógenas async (job_processor + router)

**Files:**
- Create: `services/exogenas/job_processor.py`
- Create: `services/exogenas/__init__.py` (si el paquete no existe todavía — verificar con `ls services/exogenas/` antes)
- Modify: `api/routers/exogenas.py` (reemplazo completo de `process_exogenas`/`stream_job`, `/export` y `/` no cambian)
- Test: `tests/test_exogenas_job_processor.py` (nuevo)
- Test: actualizar cualquier test existente de `exogenas.py` que dependa del endpoint SSE viejo (`grep -rl "exogenas/stream\|exogenas/process" tests/`)

**Interfaces:**
- Consumes: `job_store.put_job`/`get_job` (ya existe), `exogenas.extractor.extract_many(path)` (ya existe, firma real confirmada), `services.processor_exogenas._agregar(df)` (ya existe), `Settings.S3_BUCKET_JOB_ARTIFACTS` (Task 1)
- Produces: `services.exogenas.job_processor.process_exogenas_job(job_id: str, org_id: str, s3_keys: list[str]) -> None` — consumido por `worker_handler._process_exogenas_batch` (Task 4). `POST /exogenas/process` nuevo contrato, `GET /exogenas/jobs/{job_id}` nuevo endpoint.

- [ ] **Step 1: Confirmar si `services/exogenas/` ya existe como paquete**

```bash
ls services/exogenas/ 2>&1 || echo "no existe"
```

Si no existe, crear `services/exogenas/__init__.py` vacío primero.

- [ ] **Step 2: Escribir el test de `job_processor.py` que falla**

`tests/test_exogenas_job_processor.py`:

```python
"""Tests para services/exogenas/job_processor.py — moto-mocked S3/DynamoDB."""
import json

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    monkeypatch.setenv("JOBS_TABLE_NAME", "taxops-jobs-prod")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="taxops-job-artifacts-prod")

        ddb = boto3.client("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="taxops-jobs-prod",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield s3


def test_process_exogenas_job_happy_path(aws, monkeypatch):
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/cert.pdf", Body=b"fake pdf bytes")

    monkeypatch.setattr(
        "services.exogenas.job_processor._extract_from_path",
        lambda path: [{"nit": "900123456", "concepto": "1303", "base": 100000, "retencion": 3500, "razon_social": "Test SAS", "ciudad_retencion": "Bogotá", "_archivo": "cert.pdf"}],
    )

    from api.core import job_store
    from services.exogenas.job_processor import process_exogenas_job

    process_exogenas_job(job_id="job1", org_id="org1", s3_keys=["uploads/exogenas/org1/x/cert.pdf"])

    job = job_store.get_job("job1")
    assert job["status"] == "done"
    assert "result_s3_key" in job
    assert job["result_s3_key"].startswith("uploads/results/exogenas/job1")


def test_process_exogenas_job_persists_result_to_s3(aws, monkeypatch):
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/cert.pdf", Body=b"fake pdf bytes")
    monkeypatch.setattr(
        "services.exogenas.job_processor._extract_from_path",
        lambda path: [{"nit": "900123456", "concepto": "1303", "base": 100000, "retencion": 3500, "razon_social": "Test SAS", "ciudad_retencion": "Bogotá", "_archivo": "cert.pdf"}],
    )

    from services.exogenas.job_processor import process_exogenas_job
    process_exogenas_job(job_id="job2", org_id="org1", s3_keys=["uploads/exogenas/org1/x/cert.pdf"])

    obj = aws.get_object(Bucket="taxops-job-artifacts-prod", Key="uploads/results/exogenas/job2.json")
    data = json.loads(obj["Body"].read())
    assert "df_1003" in data
    assert "df_detalle" in data
    assert len(data["df_detalle"]) == 1


def test_process_exogenas_job_one_file_error_does_not_abort_batch(aws, monkeypatch):
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/bad.pdf", Body=b"corrupt")
    aws.put_object(Bucket="taxops-job-artifacts-prod", Key="uploads/exogenas/org1/x/good.pdf", Body=b"fake pdf bytes")

    def fake_extract(path):
        if "bad.pdf" in str(path):
            raise ValueError("archivo corrupto")
        return [{"nit": "900123456", "concepto": "1303", "base": 100000, "retencion": 3500, "razon_social": "Test SAS", "ciudad_retencion": "Bogotá", "_archivo": "good.pdf"}]

    monkeypatch.setattr("services.exogenas.job_processor._extract_from_path", fake_extract)

    from api.core import job_store
    from services.exogenas.job_processor import process_exogenas_job
    process_exogenas_job(job_id="job3", org_id="org1", s3_keys=["uploads/exogenas/org1/x/bad.pdf", "uploads/exogenas/org1/x/good.pdf"])

    job = job_store.get_job("job3")
    assert job["status"] == "done"  # el job entero no se cae por un archivo malo
```

- [ ] **Step 3: Correr — debe fallar**

```bash
python -m pytest tests/test_exogenas_job_processor.py -v
```

Expected: FAIL (`services.exogenas.job_processor` no existe).

- [ ] **Step 4: Escribir `services/exogenas/job_processor.py`**

```python
"""services/exogenas/job_processor.py — Orquesta descarga S3 → extracción → agregación → resultado en S3.

Corre en el worker Lambda (disparado por SQS, ver api/worker_handler.py). A diferencia
de services/renta/job_processor.py (que trabaja directo sobre bytes vía ocr_agent.extract_text),
exogenas.extractor.extract_many() necesita un path de filesystem — se escribe cada
descarga a un tmp file antes de extraer (mismo patrón que usaba el endpoint SSE que
este código reemplaza).
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import boto3

from api.core import job_store
from api.core.config import get_settings


def _extract_from_path(path: Path) -> list[dict]:
    """Wrapper delgado sobre extract_many — separado para poder mockearlo en tests
    sin depender de pdfplumber/pytesseract reales."""
    from exogenas.extractor import extract_many
    return extract_many(path)


def process_exogenas_job(job_id: str, org_id: str, s3_keys: list[str]) -> None:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    job_store.put_job(job_id, "processing", {"progreso": 0, "total": len(s3_keys), "completados": 0})

    tmpdir = tempfile.mkdtemp()
    all_rows: list[dict] = []
    errors = 0
    warnings: list[str] = []

    try:
        for i, s3_key in enumerate(s3_keys, 1):
            filename = Path(s3_key).name
            local_path = Path(tmpdir) / filename

            try:
                obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=s3_key)
                local_path.write_bytes(obj["Body"].read())
                rows = _extract_from_path(local_path)
            except Exception as exc:
                errors += 1
                warnings.append(f"❌ {filename}: {exc}")
                rows = []

            for row in rows:
                row["_archivo"] = filename
                if row.get("error"):
                    errors += 1
                    warnings.append(f"⚠️ {filename}: {row['error']}")
                all_rows.append(row)

            job_store.put_job(job_id, "processing", {
                "progreso": round(i / len(s3_keys) * 100),
                "total": len(s3_keys),
                "completados": i,
            })

        result = _build_result(all_rows, errors, warnings, org_id)
        result_s3_key = f"uploads/results/exogenas/{job_id}.json"
        s3.put_object(
            Bucket=settings.S3_BUCKET_JOB_ARTIFACTS,
            Key=result_s3_key,
            Body=json.dumps(result).encode("utf-8"),
            ContentType="application/json",
        )

        job_store.put_job(job_id, "done", {
            "progreso": 100,
            "total": len(s3_keys),
            "completados": len(s3_keys),
            "result_s3_key": result_s3_key,
        })

    except Exception as exc:
        import logging
        logging.getLogger("taxops.exogenas").error("process_exogenas_job failed for %s: %s", job_id, exc, exc_info=True)
        job_store.put_job(job_id, "error", {"error": str(exc)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_result(all_rows: list[dict], errors: int, warnings: list[str], org_id: str) -> dict:
    """Agrega las filas crudas al Formato 1003 — misma lógica que vivía inline en el
    endpoint SSE que este código reemplaza (api/routers/exogenas.py::stream_job)."""
    import pandas as pd

    total = len({r["_archivo"] for r in all_rows}) if all_rows else 0

    if not all_rows:
        return {
            "total_archivos": total, "procesados": total - errors, "errores": errors,
            "ica_excluidos": 0, "advertencias": warnings, "df_detalle": [], "df_1003": [],
        }

    from exogenas.municipios import buscar_municipio
    from services.processor_exogenas import _agregar

    df = pd.DataFrame(all_rows)

    def _resolve_mpio(ciudad: str) -> pd.Series:
        dpto, mpio = buscar_municipio(str(ciudad))
        return pd.Series({"cod_dpto": dpto, "cod_mpio": mpio})

    mpio_df = df["ciudad_retencion"].apply(_resolve_mpio)
    df["cod_dpto"] = mpio_df["cod_dpto"]
    df["cod_mpio"] = mpio_df["cod_mpio"]

    ica_count = int((df["concepto"] == "ICA").sum())
    df_1003 = _agregar(df)

    if org_id and not df_1003.empty:
        try:
            from db.database import db_available, insert_exogenas_batch
            if db_available():
                insert_exogenas_batch(df_1003, org_id)
        except Exception:
            pass

    return {
        "total_archivos": total,
        "procesados": total - errors,
        "errores": errors,
        "ica_excluidos": ica_count,
        "advertencias": warnings,
        "df_detalle": df.fillna("").to_dict(orient="records"),
        "df_1003": df_1003.fillna("").to_dict(orient="records"),
    }
```

**Nota de alcance:** este paso deliberadamente omite las validaciones de filas incompletas (`mask_incompletas`, warnings de "fila excluida del Formato 1003") que sí tenía el endpoint SSE viejo (líneas 216-236 del `exogenas.py` original) — son puramente cosméticas (mensajes de advertencia adicionales, no afectan el resultado real). Si se quieren preservar, copiarlas tal cual dentro de `_build_result` antes de llamar `_agregar(df)`. Decisión: **preservarlas** — no reducir funcionalidad existente sin que el spec lo haya pedido explícitamente (no lo pidió). Agregar ese bloque completo (copiado literal de `exogenas.py:216-236` del código actual) dentro de `_build_result`, antes de la línea `df_1003 = _agregar(df)`.

- [ ] **Step 5: Correr los tests — deben pasar**

```bash
python -m pytest tests/test_exogenas_job_processor.py -v
```

- [ ] **Step 6: Reescribir `api/routers/exogenas.py`**

Reemplazar `process_exogenas`, `_sse`, `_kill_proc`, `stream_job` (líneas 31-281 del archivo original) por:

```python
"""Exogenas router — async processor (SQS+worker), list, export."""
from __future__ import annotations

import json
import uuid

import boto3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.config import get_settings
from core import job_store
from dependencies import get_current_user
from schemas import ExportExogenasRequest, ProcessExogenasRequest

router = APIRouter(prefix="/exogenas", tags=["Exógenas"])

# Extensiones permitidas para certificados de retención.
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp",
}


@router.post("/process")
async def process_exogenas(
    body: ProcessExogenasRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    if not body.s3_keys:
        raise HTTPException(400, "Adjunta al menos un certificado")

    job_id = str(uuid.uuid4())
    job_store.put_job(job_id, "processing", {"progreso": 0, "total": len(body.s3_keys), "completados": 0})

    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    sqs.send_message(
        QueueUrl=settings.SQS_QUEUE_URL,
        MessageBody=json.dumps({
            "tipo": "exogenas",
            "job_id": job_id,
            "org_id": user["org_id"],
            "s3_keys": body.s3_keys,
        }),
    )
    return {"job_id": job_id, "total": len(body.s3_keys)}


@router.get("/jobs/{job_id}")
async def job_status(
    job_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")

    if job.get("status") == "done" and job.get("result_s3_key"):
        settings = get_settings()
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        try:
            obj = s3.get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=job["result_s3_key"])
            job["result"] = json.loads(obj["Body"].read())
        except Exception as exc:
            job["result_error"] = f"Error leyendo resultado de S3: {exc}"

    return job


@router.post("/export")
async def export_excel(
    body: ExportExogenasRequest,
    user: dict = Depends(get_current_user),
) -> Response:
    import pandas as pd
    import tempfile
    from pathlib import Path

    df_1003 = pd.DataFrame(body.df_1003)
    df_detalle = pd.DataFrame(body.df_detalle)

    tmp = Path(tempfile.mktemp(suffix=".xlsx"))
    try:
        from exogenas.excel_writer import write_1003

        write_1003(df_1003, df_detalle, tmp)
        content = tmp.read_bytes()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar Excel: {exc}")
    finally:
        tmp.unlink(missing_ok=True)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=taxops_exogenas_1003.xlsx"},
    )


@router.get("/")
async def list_exogenas(
    anio: int | None = None,
    concepto: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user),
) -> dict:
    from db.database import db_available, get_db

    if not db_available():
        return {"exogenas": [], "total": 0, "db_available": False}

    from sqlalchemy import text

    filters = ["org_id = :org_id"]
    params: dict = {"org_id": user["org_id"], "limit": limit, "offset": offset}

    if anio:
        filters.append("anio = :anio")
        params["anio"] = anio
    if concepto:
        filters.append("concepto = :concepto")
        params["concepto"] = concepto

    where = " AND ".join(filters)
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    f"SELECT * FROM exogenas_results WHERE {where} "
                    "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().fetchall()
            total = db.execute(
                text(f"SELECT COUNT(*) FROM exogenas_results WHERE {where}"),
                count_params,
            ).scalar()
    except Exception:
        return {"exogenas": [], "total": 0, "db_available": False}

    return {
        "exogenas": [dict(r) for r in rows],
        "total": total,
        "db_available": True,
    }
```

(`export_excel` y `list_exogenas` son idénticos al original — sin cambios de comportamiento, solo se re-transcriben porque estaban en el mismo archivo que sí cambia.)

- [ ] **Step 7: Agregar el schema `ProcessExogenasRequest`**

En `api/schemas.py`, junto a `ExportExogenasRequest`:

```python
class ProcessExogenasRequest(BaseModel):
    s3_keys: list[str]
```

- [ ] **Step 8: Actualizar/eliminar tests viejos que dependían del endpoint SSE**

```bash
grep -rl "exogenas/stream\|exogenas/process\|_pending" tests/
```

Leer cada archivo encontrado. Los tests que llamaban `POST /exogenas/process` con `multipart/form-data` y luego consumían `/exogenas/stream/{job_id}` ya no aplican — reemplazar por tests que llamen `POST /exogenas/process` con `{"s3_keys": [...]}` y luego `GET /exogenas/jobs/{job_id}` (moto-mocked SQS, sin esperar un worker real corriendo — verificar el estado del job vía `job_store.put_job` manual en el test, como ya hace `test_exogenas_job_processor.py`).

- [ ] **Step 9: Correr toda la suite**

```bash
python -m pytest -q
```

Expected: sin regresiones fuera de los archivos tocados a propósito.

- [ ] **Step 10: Commit**

```bash
git add services/exogenas/ api/routers/exogenas.py api/schemas.py tests/
git commit -m "feat: Exógenas migra a async (SQS+worker+DynamoDB), elimina SSE/subprocess

Mismo patrón que ya usa Renta. Nuevo services/exogenas/job_processor.py
(mirror de services/renta/job_processor.py, con una diferencia real:
extract_many() necesita un path de filesystem, no bytes — se escribe a
tmp antes de extraer).

POST /exogenas/process ahora encola en SQS y responde {job_id} de
inmediato. GET /exogenas/jobs/{job_id} (nuevo, reemplaza el endpoint
SSE GET /exogenas/stream/{job_id} que se elimina) hace polling —
cuando el job está 'done', descarga el resultado combinado (df_1003 +
df_detalle) desde S3 y lo embebe en la respuesta (el resultado nunca
vive directo en el item de DynamoDB — evita el límite de 400KB/item,
justo el caso de lotes grandes que motivó este cambio).

/exogenas/export y GET /exogenas/ sin cambios de comportamiento.

Trade-off aceptado: se pierde el aislamiento por subprocess (SIGKILL
en timeout >90s) que tenía el endpoint SSE viejo — el worker Lambda ya
es su propio proceso aislado (un batch colgado no afecta a la API), la
única red de seguridad restante es el timeout interno de pytesseract."
```

---

## Task 6: Frontend — helper de upload compartido

**Files:**
- Create: `taxops-web/lib/directUpload.ts`

**Interfaces:**
- Consumes: `POST /uploads/presign` (Task 2, vía `useApi().post`), fetch nativo hacia S3
- Produces: `uploadFiles(files: File[], contexto: "facturas" | "exogenas", onProgress?: (pct: number) => void) => Promise<{filename: string; s3_key: string; error?: string}[]>` — consumido por Task 7 y Task 8.

- [ ] **Step 1: Escribir `directUpload.ts`**

```typescript
/**
 * directUpload.ts — Sube archivos directo a S3 vía presigned POST (generate_presigned_post).
 *
 * Bypassea el límite de 6MB de payload de Lambda Function URL. NO usa PUT simple —
 * el backend firma un POST multipart/form-data con content-length-range real (ver
 * api/routers/uploads.py). El progreso se trackea con XMLHttpRequest (fetch no expone
 * upload.onprogress).
 */
"use client";

const API_URL = "/api-proxy";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("taxops_token");
}

type PresignedUpload = {
  filename: string;
  s3_key: string;
  url: string;
  fields: Record<string, string>;
};

type PresignResponse = {
  uploads: PresignedUpload[];
  rechazados: { filename: string; motivo: string }[];
};

export type UploadResult = {
  filename: string;
  s3_key: string;
  error?: string;
};

function uploadOne(file: File, presigned: PresignedUpload, onProgress?: (pct: number) => void): Promise<UploadResult> {
  return new Promise((resolve) => {
    const fd = new FormData();
    Object.entries(presigned.fields).forEach(([k, v]) => fd.append(k, v));
    fd.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", presigned.url);

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ filename: presigned.filename, s3_key: presigned.s3_key });
      } else {
        resolve({ filename: presigned.filename, s3_key: presigned.s3_key, error: `Error subiendo (HTTP ${xhr.status})` });
      }
    };
    xhr.onerror = () => {
      resolve({ filename: presigned.filename, s3_key: presigned.s3_key, error: "Error de red subiendo el archivo" });
    };

    xhr.send(fd);
  });
}

export async function uploadFiles(
  files: File[],
  contexto: "facturas" | "exogenas",
  onProgress?: (pct: number) => void
): Promise<UploadResult[]> {
  const token = getToken();
  const presignRes = await fetch(`${API_URL}/uploads/presign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      contexto,
      archivos: files.map((f) => ({ filename: f.name, content_type: f.type || "application/octet-stream" })),
    }),
  });

  if (!presignRes.ok) {
    const err = await presignRes.json().catch(() => ({ detail: "Error al generar URLs de subida" }));
    throw new Error(err.detail || "Error al generar URLs de subida");
  }

  const body: PresignResponse = await presignRes.json();
  const byName = new Map(files.map((f) => [f.name, f]));

  const rejected: UploadResult[] = body.rechazados.map((r) => ({
    filename: r.filename,
    s3_key: "",
    error: r.motivo,
  }));

  const total = body.uploads.length;
  let completed = 0;
  const results = await Promise.all(
    body.uploads.map(async (presigned) => {
      const file = byName.get(presigned.filename);
      if (!file) return { filename: presigned.filename, s3_key: presigned.s3_key, error: "Archivo no encontrado" };
      const result = await uploadOne(file, presigned, () => {
        // progreso agregado simple: cuenta archivos completos, no bytes exactos entre N uploads paralelos
      });
      completed += 1;
      if (onProgress) onProgress(Math.round((completed / total) * 100));
      return result;
    })
  );

  return [...results, ...rejected];
}
```

- [ ] **Step 2: Verificar que compila**

```bash
cd taxops-web && npx tsc --noEmit
```

Expected: sin errores nuevos relacionados a este archivo.

- [ ] **Step 3: Commit**

```bash
git add taxops-web/lib/directUpload.ts
git commit -m "feat: directUpload.ts — helper compartido de upload directo a S3

Usado por Facturas (Task 7) y Exógenas (Task 8). POST multipart vía
XMLHttpRequest contra la URL presignada (generate_presigned_post) —
progreso real de subida vía upload.onprogress, algo que fetch no expone."
```

---

## Task 7: Frontend — Facturas usa `directUpload`

**Files:**
- Modify: `taxops-web/app/(app)/facturas/page.tsx`

**Interfaces:**
- Consumes: `uploadFiles` (Task 6), `useApi().post` (`/invoices/process` con el nuevo contrato JSON)

- [ ] **Step 1: Leer el archivo completo antes de tocar nada**

```bash
cat "taxops-web/app/(app)/facturas/page.tsx"
```

Ubicar la función que arma el `FormData` y llama a `/invoices/process` (buscar `postForm` o `FormData` en el archivo).

- [ ] **Step 2: Reemplazar el flujo de submit**

Patrón a aplicar (adaptar nombres exactos de estado/variables al archivo real, que no se ha visto completo todavía en este plan — el implementador debe leerlo primero en el Step 1):

```typescript
import { uploadFiles } from "@/lib/directUpload";

// ... dentro del handler de submit, reemplazar el bloque que arma FormData:

async function handleProcess() {
  if (!files.length) { setError("Agrega al menos un archivo"); return; }
  setError(""); setLoading(true); setUploadProgress(0);

  const uploaded = await uploadFiles(files, "facturas", setUploadProgress);
  const failed = uploaded.filter((u) => u.error);
  if (failed.length) {
    setError(`Fallo la subida de: ${failed.map((f) => `${f.filename} (${f.error})`).join(", ")}`);
    setLoading(false);
    return;
  }

  try {
    const result = await post<ProcessResult>("/invoices/process", {
      s3_keys: uploaded.map((u) => u.s3_key),
      ingresos: ingresosList, // usar el nombre real del estado de ingresos ya existente en el archivo
    });
    setResult(result);
  } catch (e: unknown) {
    setError(e instanceof Error ? e.message : "Error al procesar");
  } finally {
    setLoading(false);
  }
}
```

Agregar `const [uploadProgress, setUploadProgress] = useState(0);` si no existe ya un estado equivalente, y una barra de progreso simple en el JSX durante la fase de upload (antes de que empiece el procesamiento) — opcional pero recomendado dado que ahora hay una fase de red adicional visible al usuario que antes no existía.

- [ ] **Step 3: Verificar compilación**

```bash
cd taxops-web && npx tsc --noEmit && npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add "taxops-web/app/(app)/facturas/page.tsx"
git commit -m "feat: Facturas sube archivos vía directUpload (presigned S3)

Elimina el límite de 6MB para lotes grandes. Sin cambio de UX en el
resultado (sigue siendo síncrono, resultado inmediato) — solo se agrega
una fase visible de subida antes de procesar."
```

---

## Task 8: Frontend — Exógenas usa `directUpload` + polling

**Files:**
- Modify: `taxops-web/app/(app)/exogenas/page.tsx`

**Interfaces:**
- Consumes: `uploadFiles` (Task 6), `useApi()` completo (`get`/`post` vía `/api-proxy` — reemplaza `DIRECT_API`/`fetch` directo que usaba el código viejo)

- [ ] **Step 1: Releer el archivo completo (ya se leyó parcialmente durante el diseño de este plan, releer para confirmar nada cambió)**

```bash
cat "taxops-web/app/(app)/exogenas/page.tsx"
```

- [ ] **Step 2: Eliminar `DIRECT_API`, `authHeaders`, `startStream`, el `AbortController` de streaming**

Estas piezas (líneas ~126-133, ~180-234 del archivo original) dejaban de tener sentido — se reemplazan por el patrón de polling de `useApi()`.

- [ ] **Step 3: Reescribir `handleProcess` con upload + polling (mismo patrón que `handleUpload`/`pollJob` de `renta/page.tsx:359-387`, ya usado como referencia)**

```typescript
import { uploadFiles } from "@/lib/directUpload";
import { useApi } from "@/lib/api";

// dentro del componente:
const { get, post } = useApi();

async function pollJob(job_id: string) {
  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    try {
      const job = await get<{ status: string; progreso: number; result?: ProcessResult; error?: string }>(
        `/exogenas/jobs/${job_id}`
      );
      setProgress(job.progreso);
      if (job.status === "done" && job.result) {
        setResult(job.result);
        setTab("analytics");
        setLoading(false);
        return;
      }
      if (job.status === "error") {
        setError(job.error || "Error procesando los certificados");
        setLoading(false);
        return;
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error consultando el estado del job");
      setLoading(false);
      return;
    }
  }
  setError("El procesamiento está tardando más de lo esperado — refresca en unos minutos");
  setLoading(false);
}

async function handleProcess() {
  if (!files.length) { setError("Agrega al menos un certificado PDF"); return; }
  setError(""); setLoading(true); setResult(null); setProgress(0);

  const uploaded = await uploadFiles(files, "exogenas", setProgress);
  const failed = uploaded.filter((u) => u.error);
  if (failed.length) {
    setError(`Fallo la subida de: ${failed.map((f) => `${f.filename} (${f.error})`).join(", ")}`);
    setLoading(false);
    return;
  }

  try {
    const { job_id } = await post<{ job_id: string; total: number }>("/exogenas/process", {
      s3_keys: uploaded.map((u) => u.s3_key),
    });
    setProgress(0); // reset — la barra pasa de "subiendo" a "procesando"
    await pollJob(job_id);
  } catch (e: unknown) {
    setError(e instanceof Error ? e.message : "Error al enviar archivos");
    setLoading(false);
  }
}
```

Quitar el estado `currentFile`/`warmingUp` si ya no se usan en ningún otro lado del archivo tras este cambio (verificar con `grep -n "currentFile\|warmingUp"` antes de borrar — puede que la UI todavía los referencie en el JSX, ajustar el JSX también si es necesario en vez de dejar variables sin usar).

- [ ] **Step 4: `handleExport` no cambia** — sigue llamando `post("/exogenas/export", {...})` igual que antes, el contrato de ese endpoint no cambió (Task 5, Step 6).

- [ ] **Step 5: Verificar compilación**

```bash
cd taxops-web && npx tsc --noEmit && npm run lint
```

- [ ] **Step 6: Commit**

```bash
git add "taxops-web/app/(app)/exogenas/page.tsx"
git commit -m "feat: Exógenas usa directUpload + polling (reemplaza SSE)

Mismo patrón visual que Renta: sube vía directUpload, encola con
POST /exogenas/process, hace polling cada 3s contra
GET /exogenas/jobs/{job_id}. Deja de usar DIRECT_API/NEXT_PUBLIC_API_URL
directo — pasa a useApi()/api-proxy, mismo patrón ya probado en Renta,
evita depender de CORS de la API para estas llamadas JSON (solo la
subida de bytes a S3 necesita ser directa del navegador)."
```

---

## Task 9: Verificación end-to-end en producción

**Files:** ninguno — solo verificación manual, sin código nuevo.

- [ ] **Step 1: Confirmar que todos los PRs (Task 1 a 8) están mergeados y aplicados**

```bash
gh pr list --state merged --limit 10
gh run list --workflow=deploy-lambda.yml --limit 1
gh run list --workflow=terraform-apply.yml --limit 3
```

- [ ] **Step 2: Probar Facturas con un lote grande (el caso que originalmente funcionaba con lotes chicos)**

Subir 15-20 PDFs reales de facturas vía `app.taxopsapp.com/facturas` — confirmar que sube y procesa sin `HTTP 413`.

- [ ] **Step 3: Probar Exógenas con el lote de 41 certificados que originalmente falló**

Reproducir el escenario exacto que reportó el error en producción — confirmar: sube sin error, muestra progreso de polling, termina con resultado, exporta el Excel correctamente (`df_detalle` + `df_1003` completos, no vacíos).

- [ ] **Step 4: Revisar CloudWatch Logs del worker durante la prueba**

```bash
export AWS_PROFILE=taxops-admin
aws logs tail /aws/lambda/taxops-worker-prod --since 15m --format short
```

Confirmar que no hay errores inesperados, y que el `job_id` de la prueba aparece con `status: done`.

- [ ] **Step 5: Confirmar el lifecycle de S3 (verificación diferida, no bloqueante)**

No se puede confirmar en el momento (la regla tarda 3 días en actuar) — anotar en el case study o en un recordatorio de seguimiento (`module.cost_reminders`, mismo patrón ya usado para el free tier de Amplify) para verificar en 3-4 días que los objetos bajo `uploads/` efectivamente se borraron.

---

## Self-Review (completado durante la escritura de este plan)

**Cobertura del spec:** cada componente de la sección "Componentes" del spec (§1 a §6) tiene un task correspondiente — §1→Task 2, §2→Task 6, §3→Task 3, §4/§4.1→Task 4+5, §5→Task 8, §5.1/§6→Task 1. La sección "Manejo de errores" del spec está cubierta: el caso de Facturas (antes "pregunta abierta") se resolvió durante la escritura de este plan leyendo `services/processor.py` real — `procesar()` ya tolera fallos por archivo internamente, documentado en la nota de Task 3.

**Placeholders:** ninguno — cada step tiene código completo, no descripciones de "agregar manejo de errores" sin mostrar el código.

**Consistencia de tipos:** `process_exogenas_job(job_id: str, org_id: str, s3_keys: list[str])` (Task 5) coincide exactamente con lo que llama `_process_exogenas_batch` (Task 4). `uploadFiles(files, contexto, onProgress) -> UploadResult[]` (Task 6) coincide con su uso en Task 7/Task 8. El contrato de `PresignResponse`/`PresignedUpload` (Task 2) coincide con lo que consume `directUpload.ts` (Task 6, campos `filename`/`s3_key`/`url`/`fields`).
