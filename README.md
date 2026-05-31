# TaxOps — Plataforma Contable SaaS Colombia

> Automatización contable para empresas colombianas: facturas DIAN, nómina CST 2026, calendario tributario, exógenas Formato 1003 y chatbot contable con IA.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.3-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Cloud Run](https://img.shields.io/badge/API-Cloud%20Run-4285F4?logo=googlecloud&logoColor=white)](https://taxops-api-fh5jvzgf7q-uc.a.run.app)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel-black?logo=vercel&logoColor=white)](https://taxops-app.vercel.app)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/ABA-projects/TaxOps-11/deploy-cloud-run.yml?label=deploy&logo=githubactions&logoColor=white)](https://github.com/ABA-projects/TaxOps-11/actions)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)

**Producción:**

| Servicio | URL |
|----------|-----|
| Frontend | [https://taxops-app.vercel.app](https://taxops-app.vercel.app) |
| API | [https://taxops-api-fh5jvzgf7q-uc.a.run.app](https://taxops-api-fh5jvzgf7q-uc.a.run.app) |
| Swagger UI | [https://taxops-api-fh5jvzgf7q-uc.a.run.app/docs](https://taxops-api-fh5jvzgf7q-uc.a.run.app/docs) |

---

## Índice

1. [¿Qué hace TaxOps?](#qué-hace-taxops)
2. [Stack tecnológico](#stack-tecnológico)
3. [Arquitectura](#arquitectura)
4. [Módulos implementados](#módulos-implementados)
5. [Inicio rápido (local)](#inicio-rápido-local)
6. [Variables de entorno](#variables-de-entorno)
7. [API Reference](#api-reference)
8. [Despliegue en Google Cloud Run](#despliegue-en-google-cloud-run)
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
| **Calendario DIAN** | 31 fechas tributarias 2026 con alertas automáticas |
| **Chatbot IA** | Asistente contable sobre Groq llama-3.3-70b-versatile |
| **Dashboard** | Métricas, accesos rápidos y notificaciones de vencimiento |

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 15.3 · App Router · TypeScript · Tailwind CSS |
| Backend | FastAPI 0.115 + Uvicorn · Python 3.12 · Docker |
| Base de datos | PostgreSQL 16 — **Neon** (serverless, multi-tenant) |
| Auth | JWT (access 30 min / refresh 7 d) + bcrypt |
| IA | Groq API — llama-3.3-70b-versatile |
| PDF export | ReportLab 4.2 |
| Excel export | openpyxl 3.1 |
| Extracción PDF/XML | pdfplumber 0.11 + lxml 5.3 · Tesseract OCR (imágenes) |
| Deploy API | **Google Cloud Run** — us-central1 · 2 GB RAM · scale-to-zero |
| Image Registry | **Google Artifact Registry** — us-central1-docker.pkg.dev |
| Deploy Frontend | **Vercel** — hobby tier, Next.js nativo |
| CI/CD | **GitHub Actions** — lint + test + build + deploy |
| GCP APIs habilitadas | `run.googleapis.com` · `artifactregistry.googleapis.com` |

---

## Arquitectura

### Vista general del sistema

```mermaid
graph TD
    subgraph Internet
        U([👤 Usuario])
    end

    subgraph Vercel
        FE["🌐 Frontend\nNext.js 15.3\ntaxops-app.vercel.app\n\nmiddleware.ts → auth gate\nuseApi hook → Bearer token"]
    end

    subgraph GCP["Google Cloud — taxops-497921 (us-central1)"]
        CR["⚙️ Cloud Run\ntaxops-api\nFastAPI 0.115 + Uvicorn\n2 GB RAM · 1 vCPU · timeout 600s\nscale-to-zero · max-instances 1"]
        AR["📦 Artifact Registry\nus-central1-docker.pkg.dev\ntaxops-497921/taxops/api\nImagen por SHA de commit"]
        CR -->|docker pull| AR
    end

    subgraph Neon["Neon Cloud"]
        DB[("🗄️ PostgreSQL 16\nMulti-tenant\nAlembic migrations\nON CONFLICT DO NOTHING")]
    end

    subgraph Groq["Groq Cloud"]
        AI["🤖 llama-3.3-70b-versatile\nChatbot contable"]
    end

    U -->|HTTPS| FE
    FE -->|HTTPS REST| CR
    CR -->|SQLAlchemy / psycopg2| DB
    CR -->|API Key| AI
```

### Flujo de autenticación

```mermaid
sequenceDiagram
    actor Browser
    participant Next as Next.js<br/>vercel.app
    participant API as FastAPI<br/>Cloud Run
    participant DB as PostgreSQL<br/>Neon

    Browser->>Next: POST /api/auth/login<br/>{email, password}
    Next->>API: POST /auth/token
    API->>DB: SELECT users WHERE email=?
    DB-->>API: user row + hashed_password
    API-->>Next: {access_token, refresh_token}
    Next-->>Browser: Set-Cookie taxops_access_token (httpOnly, 30min)<br/>Set-Cookie taxops_refresh_token (httpOnly, 7d)

    note over Browser,API: Requests autenticados
    Browser->>Next: GET /dashboard
    Next->>Next: middleware.ts verifica cookie
    Next->>API: GET /admin/stats<br/>Authorization: Bearer <token>
    API-->>Browser: 200 OK

    note over Browser,API: Token expirado → refresh automático
    Browser->>Next: POST /api/auth/session
    Next->>API: POST /auth/refresh
    API-->>Browser: nuevo access_token (transparente)
```

### Flujo exógenas — background job con polling

```mermaid
sequenceDiagram
    actor Browser
    participant API as FastAPI<br/>Cloud Run
    participant Pool as ThreadPoolExecutor<br/>max_workers=1
    participant OCR as Tesseract OCR<br/>+ pdfplumber
    participant FS as /tmp/taxops_jobs/

    Browser->>API: POST /exogenas/process<br/>multipart: 41 archivos PDF
    API->>Pool: submit(_run_job, job_id, paths)
    API-->>Browser: 200 {job_id, status: "processing"}

    loop Polling cada 3s
        Browser->>API: GET /exogenas/status/{job_id}
        API-->>Browser: {status, progress: N%, current_file}
    end

    Pool->>OCR: extract_many(archivo_1) — timeout 90s
    OCR-->>Pool: [{nit, base, retencion, concepto...}]
    Pool->>API: on_progress(i, total, nombre)

    note over Pool,OCR: Repite para cada archivo secuencialmente

    Pool->>FS: Escribe job_id.json (resultado completo)
    Pool->>API: _jobs[job_id] = {status: "done", result}

    Browser->>API: GET /exogenas/status/{job_id}
    API-->>Browser: {status: "done", df_1003, df_detalle}

    Browser->>API: POST /exogenas/export<br/>{df_1003, df_detalle}
    API-->>Browser: taxops_exogenas.xlsx
```

### Pipeline CI/CD

```mermaid
graph LR
    DEV([👨‍💻 Developer\ngit push main]) --> GH

    subgraph GH["GitHub Actions"]
        CI["CI\nflake8 + mypy\npytest\nESLint + tsc\nnext build"]
        DEPLOY["Deploy to Cloud Run\ncheckout → auth GCP\ndocker build\ndocker push\ngcloud run deploy"]
        CI --> DEPLOY
    end

    subgraph GCP["Google Cloud"]
        AR2["Artifact Registry\napi:SHA"]
        CR2["Cloud Run\ntaxops-api\nZero-downtime rolling deploy"]
        DEPLOY -->|docker push| AR2
        DEPLOY -->|gcloud run deploy| CR2
        CR2 -->|docker pull| AR2
    end

    style DEV fill:#f0f0f0,stroke:#666
    style GH fill:#e8f4fd,stroke:#0969da
    style GCP fill:#e6f4ea,stroke:#34a853
```

---

## Módulos implementados

### 1. Landing page pública (`/`)
- Completamente pública (no requiere auth)
- Hero + features + pricing mensual/anual (−20%)
- Preview calendario DIAN + testimonios

### 2. Autenticación
- Login en `/login` con JWT (access + refresh cookie httpOnly)
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
- Procesamiento en background (ThreadPoolExecutor) con polling de progreso cada 3s
- Timeout por archivo (90s) — previene OCR colgado en archivos corruptos
- Resultado persistido en `/tmp` — sobrevive reinicios menores del contenedor
- Export Excel compatible DIAN

### 8. Chatbot Contable (`/chatbot`)
- Groq llama-3.3-70b-versatile
- Contexto: ET 2026, CST, DIAN, normativa colombiana
- Tool use: `consultar_iva_mes`, `top_proveedores`, `buscar_factura`

### 9. Admin (`/admin`)
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

### API (`api/.env`)

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `DATABASE_URL` | Conexión PostgreSQL (Neon) | ✅ |
| `SECRET_KEY` | Firma JWT — mín. 32 chars aleatorios | ✅ |
| `GROQ_API_KEY` | API key Groq (`gsk_...`) | ✅ |
| `ALLOWED_ORIGINS` | CORS origins separados por coma | ✅ |
| `ALGORITHM` | Algoritmo JWT | No (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vida del access token | No (default: `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Vida del refresh token | No (default: `7`) |
| `TAXOPS_SUPERADMIN_EMAILS` | Emails con acceso superadmin | No |

### Frontend (`taxops-web/.env.local`)

| Variable | Descripción | Valor producción |
|----------|-------------|-----------------|
| `NEXT_PUBLIC_API_URL` | URL pública de la API | `https://taxops-api-fh5jvzgf7q-uc.a.run.app` |

---

## API Reference

Documentación interactiva Swagger: [https://taxops-api-fh5jvzgf7q-uc.a.run.app/docs](https://taxops-api-fh5jvzgf7q-uc.a.run.app/docs)

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

### Exógenas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/exogenas/process` | Inicia job de extracción → retorna `job_id` inmediatamente |
| GET | `/exogenas/status/{job_id}` | Progreso (`0-100%`) y resultado del job |
| POST | `/exogenas/export` | Genera Excel Formato 1003 a partir de los datos |
| GET | `/exogenas/` | Lista exógenas persistidas en DB |

---

## Despliegue en Google Cloud Run

### GCP APIs habilitadas

Solo se necesitan **dos APIs** en el proyecto `taxops-497921`:

```
run.googleapis.com              — ejecutar el contenedor Cloud Run
artifactregistry.googleapis.com — almacenar imágenes Docker
```

### Setup inicial (una sola vez)

**1. Crear proyecto y habilitar APIs**
```bash
gcloud projects create taxops-497921 --name="TaxOps"
gcloud config set project taxops-497921
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

**2. Crear repositorio en Artifact Registry**
```bash
gcloud artifacts repositories create taxops \
  --repository-format=docker \
  --location=us-central1
```

**3. Crear service account `taxops-deployer` con 3 roles**
```bash
SA=taxops-deployer@taxops-497921.iam.gserviceaccount.com

gcloud iam service-accounts create taxops-deployer

gcloud projects add-iam-policy-binding taxops-497921 \
  --member="serviceAccount:$SA" --role="roles/run.admin"

gcloud projects add-iam-policy-binding taxops-497921 \
  --member="serviceAccount:$SA" --role="roles/artifactregistry.writer"

gcloud iam service-accounts add-iam-policy-binding $SA \
  --member="serviceAccount:$SA" --role="roles/iam.serviceAccountUser"
```

**4. Descargar JSON key y configurar GitHub Secrets**

```bash
gcloud iam service-accounts keys create taxops-key.json --iam-account=$SA
```

| GitHub Secret | Valor |
|---------------|-------|
| `GCP_PROJECT_ID` | `taxops-497921` |
| `GCP_SA_KEY` | Contenido completo de `taxops-key.json` |
| `DATABASE_URL` | `postgresql://...` (Neon) |
| `SECRET_KEY` | Clave JWT (32+ chars) |
| `GROQ_API_KEY` | `gsk_...` |

### Configuración del servicio Cloud Run

| Parámetro | Valor | Razón |
|-----------|-------|-------|
| `--memory 2Gi` | **2 GB RAM** | Tesseract OCR requiere ~500 MB por archivo; necesario para lotes grandes |
| `--cpu 1` | 1 vCPU | Free tier |
| `--timeout 600` | 10 min | Procesamiento de lotes de PDFs con OCR |
| `--max-instances 1` | 1 instancia | Controla costos en free tier |
| `--allow-unauthenticated` | Sí | JWT se valida en FastAPI, no en Cloud Run |
| `--region us-central1` | Iowa | Incluido en free tier de Cloud Run |

### Troubleshooting

**Error `Bad syntax for dict arg` en `--set-env-vars`**

Los valores con `:` o `,` (URLs) rompen el parser. Solución: prefijo `^|^` cambia el delimitador de `,` a `|`:
```bash
--set-env-vars="^|^KEY=val|ALLOWED_ORIGINS=https://app.vercel.app,http://localhost:3000"
```

**Exógenas stuck en "Procesando... 0%"**

Causas posibles y verificación:
```bash
# Ver logs en vivo
gcloud run services logs tail taxops-api --region us-central1 --project taxops-497921
```

- **OOM** → aumentar memoria: `gcloud run services update taxops-api --memory 2Gi --region us-central1`
- **Job colgado** → un archivo corrupto trabó el thread; el timeout de 90s lo resuelve automáticamente en el siguiente intento

---

## CI/CD Pipeline

Cada `git push` a `main` dispara el workflow completo:

| Paso | Herramienta | Descripción |
|------|-------------|-------------|
| 1 | `actions/checkout@v4` | Clona el repositorio |
| 2 | `google-github-actions/auth@v2` | Autentica con `GCP_SA_KEY` |
| 3 | `google-github-actions/setup-gcloud@v2` | Instala `gcloud` CLI |
| 4 | `gcloud auth configure-docker` | Configura Docker para Artifact Registry |
| 5 | `docker build` | Construye imagen desde `api/Dockerfile-api` |
| 6 | `docker push` | Sube imagen tagueada con el SHA del commit |
| 7 | `gcloud run deploy` | Zero-downtime rolling deploy |
| 8 | `gcloud run services describe` | Imprime la URL en el Summary del workflow |

**Importante:** el parámetro `--memory 2Gi` en el workflow sobreescribe cualquier cambio manual en la consola GCP. No cambiar la memoria desde la consola — editar el workflow.

---

## Estructura del repositorio

```
TaxOps-11/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint + tests (Python + Next.js)
│       └── deploy-cloud-run.yml      # Build → Artifact Registry → Cloud Run
│
├── api/                              # FastAPI backend
│   ├── Dockerfile-api                # Build desde raíz del repo (no api/)
│   ├── main.py                       # App entry point: CORS, routers, Alembic
│   ├── requirements-api.txt
│   ├── .env.example
│   ├── alembic/                      # Migraciones DB (corre automático al iniciar)
│   ├── core/                         # config.py, security.py
│   ├── data/
│   │   └── calendario_2026.json      # 31 eventos DIAN (fuente de verdad)
│   └── routers/
│       ├── auth.py
│       ├── admin.py
│       ├── nomina.py
│       ├── facturas.py
│       ├── exogenas.py               # Background jobs + persistencia /tmp
│       ├── chatbot.py
│       └── calendario.py
│
├── taxops-web/                       # Next.js 15.3 frontend
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
│   ├── processor_exogenas.py        # Orquestación pipeline exógenas + timeout 90s
│   ├── chatbot.py                   # Multi-provider (Groq/OpenAI/Anthropic/Google)
│   └── nomina.py                    # Cálculos CST 2026
│
├── db/
│   ├── init.sql                     # Schema multi-tenant completo
│   └── database.py                  # Capa SQLAlchemy — degraded mode si no hay DB
│
├── docs/
│   └── GCP_MONITORING.md            # Guía de monitoreo Google Cloud
│
├── manage.py                        # CLI operator: init-db, create-org
├── Home.py                          # Streamlit UI (legacy local)
├── requirements.txt                 # Dependencias Streamlit
└── tests/                           # 150+ tests
    ├── test_extractor.py            # 44 tests
    ├── test_validator.py            # 19 tests
    ├── test_prorateo.py             # 12 tests
    ├── test_chatbot.py              # 11 tests
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

- [x] Autenticación JWT multi-tenant (login/logout/refresh/cookies httpOnly)
- [x] Dashboard con KPIs y quick actions
- [x] Nómina mensual CST 2026 (parafiscales, HE, exoneración SENA/ICBF)
- [x] Liquidación definitiva (cesantías, prima, vacaciones, indemnización)
- [x] Export nómina Excel y PDF (ReportLab)
- [x] Batch import empleados desde Excel/CSV
- [x] Calendario DIAN 2026 (31 eventos, filtros, export ICS)
- [x] Notification bell con alertas 30 días
- [x] Chatbot IA (Groq) embebible por módulo
- [x] Facturas DIAN PDF/XML (extracción, validación, prorrateo, deduplicación)
- [x] Exógenas Formato 1003 (12+ layouts, background job con polling)
- [x] Admin panel (usuarios, grupos, audit logs)
- [x] Migración a **Google Cloud Run** (2 GB RAM, scale-to-zero, deploy automático)
- [x] CI/CD GitHub Actions → Artifact Registry → Cloud Run (zero-downtime)
- [x] Timeout 90s por archivo en OCR — previene cuelgues en archivos corruptos
- [x] Persistencia de resultados en `/tmp` — sobrevive reinicios menores

### 🚧 v1.1 — Próximo

- [ ] Rate limiting por organización
- [ ] Invitaciones por email (hoy el owner crea usuarios directamente)
- [ ] Permisos por grupo (módulos bloqueados en frontend según grupo asignado)
- [ ] Script auto-update calendario DIAN (parsear PDF DIAN anual → JSON)
- [ ] Fixes extractor exógenas (5 layouts pendientes — ver `CLAUDE.md`)

### 🔮 v2.0 — Futuro

- [ ] Multi-empresa / clientes por contador
- [ ] ZIP batch upload de facturas
- [ ] Integración ERP (SIIGO / Helisa)
- [ ] App móvil (React Native / Expo)

---

## Licencia

Propietario — ABA Projects. Todos los derechos reservados.
