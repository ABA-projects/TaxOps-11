# TaxOps — Plataforma Contable SaaS Colombia

> Automatización contable para empresas colombianas: facturas DIAN, nómina CST 2026, calendario tributario, exógenas Formato 1003 y chatbot contable con IA.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.3-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://neon.tech)
[![AWS Lambda](https://img.shields.io/badge/API-AWS%20Lambda-FF9900?logo=awslambda&logoColor=white)](https://api.taxopsapp.com)
[![AWS Amplify](https://img.shields.io/badge/Frontend-AWS%20Amplify-FF9900?logo=awsamplify&logoColor=white)](https://app.taxopsapp.com)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform&logoColor=white)](infra/)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/ABA-projects/TaxOps-11/deploy-lambda.yml?label=deploy&logo=githubactions&logoColor=white)](https://github.com/ABA-projects/TaxOps-11/actions)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)

**Producción (AWS — migrado desde GCP Cloud Run + Vercel, ver [case study](docs/MIGRACION-AWS-CASE-STUDY.md)):**

| Servicio | URL |
|----------|-----|
| Frontend | [https://app.taxopsapp.com](https://app.taxopsapp.com) (AWS Amplify) |
| API | [https://api.taxopsapp.com](https://api.taxopsapp.com) (CloudFront → Lambda) |
| Swagger UI | [https://api.taxopsapp.com/docs](https://api.taxopsapp.com/docs) |

---

## Índice

1. [¿Qué hace TaxOps?](#qué-hace-taxops)
2. [Stack tecnológico](#stack-tecnológico)
3. [Arquitectura](#arquitectura)
4. [Módulos implementados](#módulos-implementados)
5. [Inicio rápido (local)](#inicio-rápido-local)
6. [Variables de entorno](#variables-de-entorno)
7. [API Reference](#api-reference)
8. [Infraestructura AWS (Terraform)](#infraestructura-aws-terraform)
9. [CI/CD Pipeline](#cicd-pipeline)
10. [Estructura del repositorio](#estructura-del-repositorio)
11. [Tests](#tests)
12. [Roadmap](#roadmap)

---

## ¿Qué hace TaxOps?

| Módulo | Descripción |
|--------|-------------|
| **Facturas DIAN** | Extrae y valida PDFs/XMLs electrónicos (CUFE, NIT, IVA, totales) |
| **Prorrateo IVA** | Cálculo Art. 490 ET para IVA descontable parcial |
| **Nómina CST 2026** | Nómina mensual + liquidación definitiva con parafiscales correctos |
| **Exógenas 1003** | Generación Formato 1003 DIAN — soporta 12+ layouts de certificados |
| **Renta** | Formulario 210, documentos soporte con OCR, motor de liquidación |
| **Calendario DIAN** | 31 fechas tributarias 2026 con alertas automáticas |
| **Chatbot IA** | Asistente contable sobre Groq llama-3.3-70b-versatile |
| **Dashboard** | Métricas, accesos rápidos y notificaciones de vencimiento |

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 15.3 · App Router · TypeScript · Tailwind CSS |
| Backend | FastAPI 0.115 + Mangum (adaptador ASGI→Lambda) · Python 3.12 · Docker |
| Base de datos | PostgreSQL 16 — **Neon** (serverless, multi-tenant, se queda fuera de AWS a propósito — evita el costo de un NAT Gateway) |
| Auth | JWT (access 30 min / refresh 7 d) + bcrypt + Google OAuth |
| IA | Groq API — llama-3.3-70b-versatile |
| PDF export | ReportLab 4.2 |
| Excel export | openpyxl 3.1 |
| Extracción PDF/XML | pdfplumber 0.11 + lxml 5.3 · Tesseract OCR (imágenes, baked en la imagen Lambda) |
| Compute API | **AWS Lambda** (container image) — Function URL detrás de CloudFront |
| Compute Worker | **AWS Lambda** — disparado por SQS, jobs largos (OCR/exógenas) |
| CDN + TLS | **CloudFront** + **ACM** (`api.taxopsapp.com`) |
| Job state | **DynamoDB** + **SQS** (reemplaza el `ThreadPoolExecutor` in-memory original) |
| Storage | **S3** (documentos de Renta, artefactos de exógenas) |
| Secretos | **SSM Parameter Store** (SecureString, no Secrets Manager — gratis) |
| Deploy Frontend | **AWS Amplify Hosting** (`app.taxopsapp.com`) — SSR nativo Next.js 15 |
| DNS + Registro | **Cloudflare** (registrador + DNS, no Route53 — evita el costo del hosted zone) |
| IaC | **Terraform** — todo el stack AWS, PR-gated (`infra/`) |
| CI/CD | **GitHub Actions** — lint + test + build + deploy, OIDC (sin llaves AWS de larga duración) |

---

## Arquitectura

### Vista general del sistema

```mermaid
graph TD
    subgraph Internet
        U([👤 Usuario])
    end

    subgraph Cloudflare["Cloudflare — DNS + Registro"]
        DNS["taxopsapp.com\napp.* → Amplify\napi.* → CloudFront"]
    end

    subgraph Amplify["AWS Amplify Hosting"]
        FE["🌐 Frontend\nNext.js 15.3 SSR\napp.taxopsapp.com"]
    end

    subgraph AWS["AWS (us-east-1)"]
        CF["☁️ CloudFront\napi.taxopsapp.com\nACM cert"]
        LAPI["⚙️ Lambda API\ntaxops-api-prod\nMangum + FastAPI\n1024MB · timeout 60s"]
        LWRK["⚙️ Lambda Worker\ntaxops-worker-prod\nOCR/exógenas · timeout 14min"]
        SQS[("📬 SQS\ntaxops-jobs-prod")]
        DDB[("🗄️ DynamoDB\ntaxops-jobs-prod\nTTL 48h")]
        S3[("📦 S3\nrenta-docs · job-artifacts")]
        SSM["🔐 SSM Parameter Store\nSecureString"]
        ECR["📦 ECR\ntaxops-api"]

        CF -->|Function URL| LAPI
        LAPI -->|enqueue| SQS
        SQS -->|trigger| LWRK
        LAPI --> DDB
        LWRK --> DDB
        LAPI --> S3
        LWRK --> S3
        LAPI -.->|env vars| SSM
        LAPI -.->|docker pull| ECR
        LWRK -.->|docker pull| ECR
    end

    subgraph Neon["Neon Cloud"]
        DB[("🗄️ PostgreSQL 16\nMulti-tenant\nAlembic migrations")]
    end

    subgraph Groq["Groq Cloud"]
        AI["🤖 llama-3.3-70b-versatile\nChatbot contable"]
    end

    U -->|HTTPS| DNS
    DNS --> FE
    DNS --> CF
    FE -->|HTTPS REST| CF
    LAPI -->|SQLAlchemy| DB
    LWRK -->|SQLAlchemy| DB
    LAPI -->|API Key| AI
```

### Flujo exógenas/renta — background job vía SQS

```mermaid
sequenceDiagram
    actor Browser
    participant API as Lambda API
    participant S3 as S3
    participant SQS as SQS
    participant Worker as Lambda Worker
    participant DDB as DynamoDB

    Browser->>API: POST /renta/documentos<br/>multipart: N archivos
    API->>S3: upload_to_s3() por archivo (síncrono)
    API->>SQS: send_message({job_id, s3_keys[]})
    API->>DDB: put_job(status="processing")
    API-->>Browser: 200 {job_id}

    SQS->>Worker: trigger (batch_size=1)
    loop Por documento
        Worker->>S3: download_from_s3()
        Worker->>Worker: OCR (Tesseract) + clasificación
        Worker->>DDB: update_job(progreso, status)
    end

    loop Polling cada 3s
        Browser->>API: GET /renta/jobs/{job_id}
        API->>DDB: get_job(job_id)
        API-->>Browser: {status, progreso, resultado}
    end
```

### Pipeline CI/CD

```mermaid
graph LR
    DEV([👨‍💻 Developer\ngit push main]) --> GH

    subgraph GH["GitHub Actions"]
        CI["CI\nflake8 + pytest\nESLint + tsc\nnext build"]
        DEPLOY["Deploy to Lambda\ndocker build/push ECR\nalembic upgrade\nupdate-function-code"]
        TFPLAN["Terraform Plan\n(en PRs que tocan infra/)"]
        TFAPPLY["Terraform Apply\n(push a main, gate manual)"]
        CI --> DEPLOY
        TFPLAN --> TFAPPLY
    end

    subgraph AWS["AWS"]
        ECR2["ECR\napi:SHA"]
        L2["Lambda API + Worker"]
        DEPLOY -->|push| ECR2
        DEPLOY -->|update-function-code| L2
        L2 -->|pull| ECR2
        TFAPPLY -.->|infra/**| L2
    end

    style DEV fill:#f0f0f0,stroke:#666
    style GH fill:#e8f4fd,stroke:#0969da
    style AWS fill:#fff4e6,stroke:#ff9900
```

---

## Módulos implementados

### 1. Landing page pública (`/`)
- Completamente pública (no requiere auth)
- Hero + features + pricing mensual/anual (−20%)
- Preview calendario DIAN + testimonios

### 2. Autenticación
- Login en `/login` con JWT (access + refresh cookie httpOnly) + Google OAuth
- Refresh automático via `/api/auth/session`
- `useApi` hook maneja Authorization header en todas las llamadas

### 3. Dashboard (`/dashboard`)
- KPIs: facturas procesadas, IVA acumulado, nóminas calculadas
- Quick actions por módulo
- Notificaciones inline de vencimientos DIAN

### 4. Nómina CST 2026 (`/nomina`)

**4 tabs:** Nómina Mensual · Liquidación Definitiva · Empleados · Analítica

| Concepto | Valor 2026 |
|----------|------------|
| SMLMV | $1,750,905 |
| Auxilio de transporte | $249,095 (aplica ≤2 SMLMV) |
| Salario integral mínimo | $22,761,765 (13× SMLMV) |
| Jornada máxima | 42 h/sem (Ley 2101/2021) |

- Parafiscales empleador: Salud 8.5%, Pensión 12%, ARL I–V, SENA 2%, ICBF 3%, Caja 4%
- Exoneración SENA+ICBF automática para salarios ≤10 SMLMV (Art. 114-1 ET)
- Export Excel (.xlsx) y PDF (ReportLab, branding navy/orange)
- Batch import: drag-and-drop Excel/CSV → resultados batch

### 5. Calendario DIAN 2026 (`/calendario`)
- 31 eventos tributarios agrupados por mes
- Alerta visual para eventos ≤10 días
- Filtros por tipo: retención, IVA, renta, exógenas, ICA, patrimonio
- Export ICS → Google Calendar / Apple Calendar
- Actualizable sin redeploy vía `PUT /calendario/eventos` (superadmin)

### 6. Facturas DIAN (`/facturas`)
- Upload PDF/XML electrónicos (pdfplumber + lxml UBL 2.1)
- Extracción: CUFE, NIT/nombre emisor, fecha, base, IVA, total
- Validación: cuadre (base + IVA = total), CUFE 96 chars, formato NIT
- Detección: Nota Crédito/Débito, Mandato/Peaje, Soporte, Equivalente
- Deduplicación por CUFE (`ON CONFLICT DO NOTHING`)
- Autorretenedores: 3.287 NITs DIAN
- Prorrateo IVA Art. 490 ET automático
- Export Excel 3 hojas: BASE_DATOS, VALIDACION, PRORRATEO_IVA

### 7. Exógenas Formato 1003 (`/exogenas`)
- Extracción de certificados de retención (PDF, imagen, Excel, Word)
- 12+ layouts soportados: SAP bilingüe, Mekano ERP, narrativo, ICA 4-col, Bodega de Moda, Tennis, MEDIFE, PUBLIK MAGIC, SAN JUAN DE DIOS, Multi-concepto tabla…
- Procesamiento en background vía SQS + Lambda worker (ver diagrama arriba)
- Resultado persistido en DynamoDB (TTL 48h) — sobrevive cold starts/redeploys
- Export Excel compatible DIAN

### 8. Renta (`/renta`)
- Documentos soporte con OCR (Tesseract, mismo worker que exógenas)
- Formulario 210 — motor de liquidación
- Documentos en S3 (versionado, cifrado SSE)

### 9. Chatbot Contable (`/chatbot`)
- Groq llama-3.3-70b-versatile
- Contexto: ET 2026, CST, DIAN, normativa colombiana
- Tool use: `consultar_iva_mes`, `top_proveedores`, `buscar_factura`

### 10. Admin (`/admin`)
- Gestión de usuarios (crear, desactivar, reactivar, eliminar soft-hard)
- Gestión de grupos con módulos asignados
- Audit logs con filtros por módulo/acción/email
- KPIs del tenant + sesiones recientes

---

## Inicio rápido (local)

### Prerrequisitos

- Python 3.10+
- Node.js 22+
- PostgreSQL (o `DATABASE_URL` de Neon)
- Tesseract OCR: `apt install tesseract-ocr tesseract-ocr-spa` (Debian/Ubuntu)

### 1. Instalar dependencias

```bash
# Backend / pipeline
pip install -r requirements.txt
pip install -e .              # expone CLI `taxops`

# API
pip install -r api/requirements-api.txt

# Frontend
cd taxops-web && npm install
```

### 2. Variables de entorno

```bash
cp api/.env.example api/.env
```

`api/.env`:
```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
SECRET_KEY=<genera con: python3 -c "import secrets; print(secrets.token_hex(32))">
GROQ_API_KEY=gsk_...
ALLOWED_ORIGINS=http://localhost:3000
```

### 3. Inicializar base de datos

```bash
export DATABASE_URL=postgresql://...
python manage.py init-db
python manage.py create-org --name "Mi Empresa" --email admin@empresa.co --password Admin1234!
```

### 4. Arrancar servicios

```bash
# Terminal 1 — API
cd api && uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd taxops-web && npm run dev
```

| Servicio | URL local |
|----------|-----------|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |

---

## Variables de entorno

### API (`api/.env` local — en AWS se inyectan como env vars de Lambda desde SSM/Terraform)

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `DATABASE_URL` | Conexión PostgreSQL (Neon) | ✅ |
| `SECRET_KEY` | Firma JWT — mín. 32 chars aleatorios | ✅ |
| `GROQ_API_KEY` | API key Groq (`gsk_...`) | ✅ |
| `ALLOWED_ORIGINS` | CORS origins separados por coma | ✅ |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth Google | No |
| `API_BASE_URL` | URL pública de la API (redirect Google OAuth) | No (default localhost) |
| `FRONTEND_URL` | URL pública del frontend (redirect post-login) | No (default localhost) |
| `JOBS_TABLE_NAME` | Tabla DynamoDB de jobs | Solo en Lambda |
| `S3_BUCKET_RENTA_DOCS` | Bucket S3 documentos Renta | Solo en Lambda |
| `SQS_QUEUE_URL` | Cola SQS de jobs | Solo en Lambda |
| `ALGORITHM` | Algoritmo JWT | No (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vida del access token | No (default: `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Vida del refresh token | No (default: `7`) |
| `TAXOPS_SUPERADMIN_EMAILS` | Emails con acceso superadmin | No |

### Frontend (`taxops-web/.env.local`)

| Variable | Descripción | Valor producción |
|----------|-------------|-----------------|
| `NEXT_PUBLIC_API_URL` | URL pública de la API | `https://api.taxopsapp.com` |
| `INTERNAL_API_URL` | URL que usa el server-side de Next.js para llamar la API | `https://api.taxopsapp.com` |

---

## API Reference

Documentación interactiva Swagger: [https://api.taxopsapp.com/docs](https://api.taxopsapp.com/docs)

### Auth

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/login` | Login → access + refresh token |
| POST | `/auth/register` | Crear organización + usuario owner |
| GET | `/auth/me` | Perfil del usuario autenticado |
| POST | `/auth/refresh` | Renovar access token con refresh token |

### Admin

| Método | Endpoint | Guard | Descripción |
|--------|----------|-------|-------------|
| GET | `/admin/stats` | require_admin | Dashboard KPIs |
| GET/POST | `/admin/users` | require_admin | Listar / crear usuarios |
| DELETE | `/admin/users/{id}/permanent` | require_owner | Eliminar usuario (soft-hard delete) |
| POST | `/admin/users/{id}/reactivate` | require_admin | Reactivar usuario inactivo |
| GET/POST | `/admin/groups` | require_admin/owner | CRUD grupos |
| GET | `/admin/audit-logs` | require_admin | Logs de auditoría |

### Calendario

| Método | Endpoint | Guard | Descripción |
|--------|----------|-------|-------------|
| GET | `/calendario/eventos` | get_current_user | Eventos DIAN del año en curso |
| PUT | `/calendario/eventos` | require_superadmin | Reemplazar todos los eventos |
| POST | `/calendario/eventos` | require_superadmin | Agregar evento individual |
| DELETE | `/calendario/eventos/{id}` | require_superadmin | Eliminar evento |

### Renta / Exógenas (background jobs)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/renta/documentos` | Sube a S3 + encola en SQS → retorna `job_id` inmediatamente |
| GET | `/renta/jobs/{job_id}` | Progreso y resultado del job (lee de DynamoDB) |
| POST | `/exogenas/process` | Inicia job de extracción → retorna `job_id` |
| GET | `/exogenas/status/{job_id}` | Progreso (`0-100%`) y resultado del job |
| POST | `/exogenas/export` | Genera Excel Formato 1003 a partir de los datos |

---

## Infraestructura AWS (Terraform)

Todo el stack AWS vive en `infra/`, gestionado 100% por Terraform — **ningún recurso se crea a mano**, salvo el bootstrap del state (`infra/bootstrap/`, con local state, la única excepción documentada).

```
infra/
├── bootstrap/              # S3 bucket para el state remoto (local state, una sola vez)
├── environments/prod/      # Root module — wiring de todos los módulos
└── modules/
    ├── ecr/                 # Repo de imágenes Docker
    ├── secrets/             # SSM Parameter Store (SecureString)
    ├── github-oidc/         # OIDC provider + rol para GitHub Actions (sin llaves)
    ├── jobs/                # SQS + DynamoDB (estado de jobs largos)
    ├── storage/             # Buckets S3 (renta docs, job artifacts)
    ├── lambda-api/          # Lambda API + Worker + IAM + Function URL
    ├── cdn/                 # CloudFront + ACM + DNS (Cloudflare) para la API
    ├── amplify/             # Amplify Hosting + dominio propio del frontend
    └── cost-reminders/      # EventBridge Scheduler + SNS — alertas de free tier
```

**Flujo de cambios (regla de oro, sin excepción):**

1. Rama nueva → cambios en `infra/`
2. PR → `terraform-plan.yml` corre y comenta el plan en el PR
3. Merge a `main` → `terraform-apply.yml` se dispara, pero **pausa esperando aprobación manual** (GitHub Environment `production`)
4. Aprobación → `terraform apply` real

Nunca `terraform apply` manual desde una laptop, salvo el bootstrap inicial.

**Principio de costo — "todo gratis, siempre":** cada recurso nuevo se evalúa primero por su capa gratuita (perpetua > 12 meses > pago). Detalle completo de decisiones de costo en el [case study de la migración](docs/MIGRACION-AWS-CASE-STUDY.md).

---

## CI/CD Pipeline

Cada `git push` a `main` que toca código de app (`api/`, `pipeline/`, `services/`, etc.) dispara `deploy-lambda.yml`:

| Paso | Descripción |
|------|-------------|
| 1 | Checkout + auth AWS vía OIDC (`aws-actions/configure-aws-credentials`, sin llaves de larga duración) |
| 2 | `docker build` desde `api/Dockerfile-lambda` (multi-stage, Tesseract embebido) |
| 3 | `docker push` a ECR, tag = SHA del commit (repo `IMMUTABLE`) |
| 4 | `alembic upgrade head` como paso de CI separado (no al arrancar Lambda — evita condición de carrera bajo cold-start) |
| 5 | `aws lambda update-function-code` para `taxops-api-prod` y `taxops-worker-prod` |
| 6 | Smoke test: `curl` a `/health`, verifica `"status":"ok"` |

El frontend (`taxops-web/`) se despliega automáticamente vía el webhook nativo de GitHub que Amplify configura al conectar el repo — push a `main` dispara un build de Amplify sin workflow propio.

Cambios en `infra/**` van por el flujo de Terraform descrito arriba (`terraform-plan.yml` / `terraform-apply.yml`), separado del deploy de código — `lifecycle.ignore_changes = [image_uri]` en los recursos Lambda evita que ambos flujos se pisen.

---

## Estructura del repositorio

```
TaxOps-11/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint + tests (Python + Next.js) — gatea PRs
│       ├── deploy-lambda.yml         # Build → ECR → Lambda (API + Worker)
│       ├── terraform-plan.yml        # Comenta el plan en PRs que tocan infra/
│       └── terraform-apply.yml       # Apply con gate manual (push a main)
│
├── infra/                            # Terraform — ver sección de arriba
│
├── api/                              # FastAPI backend
│   ├── Dockerfile-lambda             # Imagen Lambda (Amazon Linux + Tesseract embebido)
│   ├── Dockerfile-api                # Legacy (Cloud Run) — histórico
│   ├── main.py                       # App entry point: CORS, routers, Mangum handler
│   ├── worker_handler.py             # Entry point del Lambda worker (SQS trigger)
│   ├── requirements-api.txt
│   ├── .env.example
│   ├── alembic/                      # Migraciones DB (corren en CI, no al arrancar)
│   ├── core/                         # config.py, security.py, job_store.py (DynamoDB)
│   ├── data/
│   │   └── calendario_2026.json      # 31 eventos DIAN (fuente de verdad)
│   └── routers/
│       ├── auth.py
│       ├── admin.py
│       ├── nomina.py
│       ├── facturas.py
│       ├── exogenas.py
│       ├── renta_documentos.py       # Upload S3 + encolado SQS
│       ├── chatbot.py
│       └── calendario.py
│
├── taxops-web/                       # Next.js 15.3 frontend
│   ├── eslint.config.mjs             # Flat config, next/core-web-vitals + typescript
│   ├── middleware.ts                 # Auth gate JWT (protege rutas /dashboard /*)
│   ├── app/
│   │   ├── page.tsx                  # Landing pública
│   │   ├── login/
│   │   ├── api/auth/                 # login / logout / session / refresh
│   │   └── (app)/                    # Rutas autenticadas (layout con sidebar)
│   │       ├── dashboard/
│   │       ├── nomina/
│   │       ├── calendario/
│   │       ├── facturas/
│   │       ├── renta/
│   │       ├── exogenas/
│   │       ├── chatbot/
│   │       ├── admin/
│   │       └── perfil/
│   ├── components/
│   └── lib/                          # useApi hook, auth helpers
│
├── pipeline/                         # Procesamiento facturas DIAN
│   ├── extractor.py                  # PDF/XML → dict (thread-safe)
│   ├── validator.py                  # CUFE, NIT, cuadre aritmético
│   ├── prorateo.py                   # Art. 490 ET — IVA descontable
│   ├── excel_writer.py               # Workbook 3 hojas
│   └── autorretenedores.txt          # 3.287 NITs DIAN (feb 2026)
│
├── exogenas/
│   └── extractor.py                 # Certificados retención — 12+ layouts
│
├── services/
│   ├── processor.py                 # Orquestación pipeline facturas
│   ├── processor_exogenas.py        # Orquestación pipeline exógenas
│   ├── chatbot.py                   # Multi-provider (Groq/OpenAI/Anthropic/Google)
│   ├── nomina.py                    # Cálculos CST 2026
│   └── renta/                       # Formulario 210, OCR agent, tax engine, storage S3
│
├── db/
│   ├── init.sql                     # Schema multi-tenant completo
│   └── database.py                  # Capa SQLAlchemy — degraded mode si no hay DB
│
├── docs/
│   ├── MIGRACION-AWS-CASE-STUDY.md  # Case study de portafolio — migración GCP→AWS
│   ├── MIGRACION-AWS-DISCOVERY.md   # Discovery inicial
│   ├── AWS-ACCOUNT-SETUP-GUIDE.md   # Setup de cuenta AWS (seguridad, billing)
│   ├── CI-CD-GITOPS-GUIDE.md        # Roadmap de madurez del pipeline
│   ├── DIRENV-AWS-PROFILE.md        # Aislamiento de credenciales vía direnv
│   ├── superpowers/plans/           # Plan ejecutable de la migración (8 chunks)
│   └── GCP_MONITORING.md            # Histórico — arquitectura ya no vigente
│
├── manage.py                        # CLI operator: init-db, create-org
├── Home.py                          # Streamlit UI (legacy local)
├── requirements.txt                 # Dependencias Streamlit
└── tests/                           # 170+ tests
    ├── test_extractor.py            # 44 tests
    ├── test_validator.py            # 19 tests
    ├── test_prorateo.py             # 12 tests
    ├── test_chatbot.py              # 11 tests
    ├── test_worker_handler.py       # Lambda worker (moto-mocked SQS/S3)
    ├── test_job_store.py            # DynamoDB (moto-mocked)
    ├── test_e2e.py                  # 32 tests (requieren PDFs reales)
    └── ...
```

---

## Tests

```bash
# Unitarios — no requieren PDFs ni DB
python -m pytest tests/test_extractor.py tests/test_validator.py \
                 tests/test_prorateo.py tests/test_chatbot.py -v

# End-to-end — requieren PDFs en pipeline/
python -m pytest tests/test_e2e.py -v

# Con cobertura completa
python -m pytest --cov=. --cov-report=term-missing
```

---

## Roadmap

### ✅ v1.0 — Implementado

- [x] Autenticación JWT multi-tenant (login/logout/refresh/cookies httpOnly) + Google OAuth
- [x] Dashboard con KPIs y quick actions
- [x] Nómina mensual CST 2026 (parafiscales, HE, exoneración SENA/ICBF)
- [x] Liquidación definitiva (cesantías, prima, vacaciones, indemnización)
- [x] Export nómina Excel y PDF (ReportLab)
- [x] Batch import empleados desde Excel/CSV
- [x] Calendario DIAN 2026 (31 eventos, filtros, export ICS)
- [x] Notification bell con alertas 30 días
- [x] Chatbot IA (Groq) embebible por módulo
- [x] Facturas DIAN PDF/XML (extracción, validación, prorrateo, deduplicación)
- [x] Exógenas Formato 1003 (12+ layouts, background job vía SQS)
- [x] Renta — Formulario 210, OCR de documentos soporte
- [x] Admin panel (usuarios, grupos, audit logs)
- [x] **Migración completa GCP→AWS**: Lambda (API+Worker) · CloudFront+ACM · SQS+DynamoDB · S3 · Amplify Hosting · Cloudflare DNS — 100% Terraform, PR-gated
- [x] CI/CD GitHub Actions → ECR → Lambda (zero llaves de larga duración, OIDC)
- [x] flake8/ESLint configurados y en verde en CI (deuda de estilo preexistente resuelta)

### 🚧 v1.1 — Próximo

- [ ] Decomisión completa de Vercel (soak period de Amplify en curso)
- [ ] Rate limiting por organización
- [ ] Invitaciones por email (hoy el owner crea usuarios directamente)
- [ ] Permisos por grupo (módulos bloqueados en frontend según grupo asignado)
- [ ] Script auto-update calendario DIAN (parsear PDF DIAN anual → JSON)
- [ ] Acotar el rol OIDC de GitHub Actions (hoy `AdministratorAccess`, deuda técnica documentada)

### 🔮 v2.0 — Futuro

- [ ] Multi-empresa / clientes por contador
- [ ] ZIP batch upload de facturas
- [ ] Integración ERP (SIIGO / Helisa)
- [ ] App móvil (React Native / Expo)
- [ ] Agentes con AWS Bedrock (en evaluación)

---

## Licencia

Propietario — ABA Projects. Todos los derechos reservados.
