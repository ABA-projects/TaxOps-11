# TaxOps — Plataforma Contable SaaS Colombia

> Automatización contable para empresas colombianas: facturas DIAN, nómina CST 2026, calendario tributario, exógenas Formato 1003 y chatbot contable con IA.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.3-black?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)](https://postgresql.org)
[![Cloud Run](https://img.shields.io/badge/API-Cloud%20Run-4285F4?logo=googlecloud)](https://taxops-api-fh5jvzgf7q-uc.a.run.app)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel-black?logo=vercel)](https://taxops-app.vercel.app)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/jaimehenao8126/TaxOps-11/deploy-cloud-run.yml?label=deploy&logo=githubactions)](https://github.com/jaimehenao8126/TaxOps-11/actions)

**Producción:**
- Frontend: [https://taxops-app.vercel.app](https://taxops-app.vercel.app)
- API: [https://taxops-api-fh5jvzgf7q-uc.a.run.app](https://taxops-api-fh5jvzgf7q-uc.a.run.app)
- API Docs: [https://taxops-api-fh5jvzgf7q-uc.a.run.app/docs](https://taxops-api-fh5jvzgf7q-uc.a.run.app/docs)

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
| **Exógenas 1003** | Generación Formato 1003 DIAN para proveedores (12+ layouts) |
| **Calendario DIAN** | 31 fechas tributarias 2026 con alertas automáticas |
| **Chatbot IA** | Asistente contable sobre Groq llama-3.3-70b-versatile |
| **Dashboard** | Métricas, accesos rápidos y notificaciones de vencimiento |

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 15.3 · App Router · TypeScript · Tailwind CSS |
| Backend | FastAPI 0.115 + Uvicorn · Docker |
| Base de datos | PostgreSQL 16 (Neon) |
| Auth | JWT (access 30 min / refresh 7 d) + bcrypt |
| IA | Groq API — llama-3.3-70b-versatile |
| PDF export | ReportLab 4.2 |
| Excel export | openpyxl 3.1 |
| Extracción PDF/XML | pdfplumber 0.11 + lxml 5.3 · Tesseract OCR |
| Deploy API | **Google Cloud Run** (Docker, us-central1, 1 GB RAM) |
| Registry | **Google Artifact Registry** (us-central1-docker.pkg.dev) |
| Deploy Frontend | Vercel (Next.js, hobby tier) |
| CI/CD | GitHub Actions |

---

## Arquitectura

### Vista general del sistema

```
┌──────────────────────────────────────────────────────┐
│            https://taxops-app.vercel.app             │
│              Next.js 15 — App Router                 │
│        middleware.ts → auth gate (JWT cookie)        │
└──────────────────────┬───────────────────────────────┘
                       │ HTTPS / useApi hook
┌──────────────────────▼───────────────────────────────┐
│     https://taxops-api-fh5jvzgf7q-uc.a.run.app      │
│          FastAPI + Uvicorn — Google Cloud Run        │
│      us-central1 · 1 GB RAM · scale-to-zero          │
│  /auth  /nomina  /facturas  /exogenas  /chatbot      │
│  /admin  /calendario                                  │
└──────────────────────┬───────────────────────────────┘
                       │ SQLAlchemy / psycopg2
┌──────────────────────▼───────────────────────────────┐
│              PostgreSQL 16 (Neon Cloud)              │
│         multi-tenant · Alembic migrations            │
└──────────────────────────────────────────────────────┘

Infraestructura Google Cloud (Proyecto: taxops-497921)
┌───────────────────────────────────────────────────────┐
│  Artifact Registry                                    │
│  us-central1-docker.pkg.dev/taxops-497921/taxops      │
│  └─ api:<git-sha>  (imagen Docker por commit)         │
└───────────────────────────────────────────────────────┘
```

### Flujo de autenticación

```
Browser ──► POST /api/auth/login (Next.js proxy)
                    │
                    ▼
            POST /auth/token (FastAPI)
                    │
                    ▼
         ◄── Set-Cookie: taxops_access_token  (httpOnly, 30 min)
         ◄── Set-Cookie: taxops_refresh_token (httpOnly, 7 d)

Requests autenticados:
  Browser ──► middleware.ts (verifica cookie) ──► API
              useApi hook añade Authorization: Bearer <token>

Token expirado:
  useApi ──► POST /api/auth/session ──► POST /auth/refresh
          ◄── nuevo access token (transparente al usuario)
```

### Flujo de procesamiento exógenas (background job)

```
Frontend                    FastAPI                   Thread Pool
   │                           │                          │
   │── POST /exogenas/process ─►│                          │
   │   (archivos PDF/IMG/XLS)   │── submit(_run_job) ─────►│
   │◄─── { job_id, status }     │                     extrae OCR
   │                            │                     procesa
   │── GET /exogenas/status ───►│◄── progress update       │
   │◄─── { progress: 45% }      │                          │
   │    (polling cada 2s)        │                          │
   │── GET /exogenas/status ───►│◄── status: done          │
   │◄─── { result: {...} }       │   (df_1003, df_detalle)  │
   │                            │                          │
   │── POST /exogenas/export ──►│ genera Excel             │
   │◄─── archivo .xlsx           │                          │
```

### Pipeline CI/CD

```
git push main
      │
      ▼
GitHub Actions (.github/workflows/deploy-cloud-run.yml)
      │
      ├─ actions/checkout@v4
      ├─ google-github-actions/auth@v2  (GCP_SA_KEY secret)
      ├─ google-github-actions/setup-gcloud@v2
      │
      ├─ docker build -f api/Dockerfile-api
      ├─ docker push → Artifact Registry
      │   us-central1-docker.pkg.dev/taxops-497921/taxops/api:<sha>
      │
      └─ gcloud run deploy taxops-api
            --image <imagen>
            --memory 1Gi  --cpu 1
            --timeout 600  --max-instances 1
            --allow-unauthenticated
            --set-env-vars DATABASE_URL | SECRET_KEY | GROQ_API_KEY | ...
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

**Parámetros legales CST 2026:**

| Concepto | Valor |
|----------|-------|
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
- 12+ layouts soportados (SAP bilingüe, Mekano ERP, narrativo, ICA 4-col…)
- Procesamiento en background con polling de progreso
- Export Excel compatible DIAN

### 8. Chatbot Contable (`/chatbot`)
- Groq llama-3.3-70b-versatile
- Contexto: ET 2026, CST, DIAN, normativa colombiana
- Tool use: `consultar_iva_mes`, `top_proveedores`, `buscar_factura`

### 9. Admin (`/admin`)
- Gestión de usuarios (crear, desactivar, reactivar, eliminar)
- Gestión de grupos con módulos asignados
- Audit logs con filtros por módulo/acción/email
- KPIs del tenant

---

## Inicio rápido (local)

### Prerrequisitos
- Python 3.10+
- Node.js 22+
- PostgreSQL (o `DATABASE_URL` de Neon)
- Tesseract OCR instalado (`tesseract-ocr tesseract-ocr-spa` en Debian/Ubuntu)

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

Editar `api/.env`:
```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
SECRET_KEY=genera_uno_con___python3_-c_"import_secrets;print(secrets.token_hex(32))"
GROQ_API_KEY=gsk_...
ALLOWED_ORIGINS=http://localhost:3000
```

Generar un SECRET_KEY seguro:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Inicializar base de datos

```bash
export DATABASE_URL=postgresql://...
python manage.py init-db
python manage.py create-org --name "Mi Empresa" --email admin@empresa.co --password Admin1234!
```

### 4. Arrancar servicios

```bash
# API (terminal 1)
cd api && uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd taxops-web && npm run dev

# Streamlit legacy opcional (terminal 3)
python -m streamlit run Home.py
```

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Streamlit | http://localhost:8501 |

---

## Variables de entorno

### API (`api/.env`)

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `DATABASE_URL` | Conexión PostgreSQL (Neon) | ✅ |
| `SECRET_KEY` | Firma JWT (mín. 32 chars) | ✅ |
| `GROQ_API_KEY` | API key Groq | ✅ |
| `ALLOWED_ORIGINS` | CORS origins separados por coma | ✅ |
| `ALGORITHM` | Algoritmo JWT | No (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración access token | No (default: 30) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración refresh token | No (default: 7) |
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

### Admin

| Método | Endpoint | Guard | Descripción |
|--------|----------|-------|-------------|
| GET | `/admin/stats` | require_admin | Dashboard KPIs |
| GET/POST | `/admin/users` | require_admin | Listar / crear usuarios |
| DELETE | `/admin/users/{id}/permanent` | require_owner | Eliminar usuario (soft-hard delete) |
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
| POST | `/exogenas/process` | Inicia job de extracción → retorna `job_id` |
| GET | `/exogenas/status/{job_id}` | Progreso / resultado del job |
| POST | `/exogenas/export` | Genera Excel Formato 1003 |
| GET | `/exogenas/` | Lista exógenas guardadas en DB |

---

## Despliegue en Google Cloud Run

### Prerequisitos en Google Cloud

Antes de activar el workflow por primera vez, realizar una vez estos pasos manuales:

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
  --location=us-central1 \
  --description="TaxOps Docker images"
```

**3. Crear service account con los roles necesarios**
```bash
gcloud iam service-accounts create taxops-deployer \
  --display-name="TaxOps Deployer"

PROJECT=taxops-497921
SA=taxops-deployer@${PROJECT}.iam.gserviceaccount.com

# Rol 1: desplegar y gestionar servicios Cloud Run
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/run.admin"

# Rol 2: push/pull de imágenes Docker
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/artifactregistry.writer"

# Rol 3: actuar como service account en el deploy
gcloud iam service-accounts add-iam-policy-binding \
  $SA --member="serviceAccount:$SA" \
  --role="roles/iam.serviceAccountUser"
```

**4. Descargar JSON key**
```bash
gcloud iam service-accounts keys create taxops-key.json \
  --iam-account=$SA
```

**5. Configurar GitHub Secrets** (Settings → Secrets → Actions)

| Secret | Descripción |
|--------|-------------|
| `GCP_PROJECT_ID` | `taxops-497921` |
| `GCP_SA_KEY` | Contenido completo del archivo `taxops-key.json` |
| `DATABASE_URL` | `postgresql://...` (Neon) |
| `SECRET_KEY` | Clave JWT (32+ chars, aleatoria) |
| `GROQ_API_KEY` | `gsk_...` |

### Configuración del servicio Cloud Run

El workflow despliega con estos parámetros optimizados para el plan gratuito:

| Parámetro | Valor | Razón |
|-----------|-------|-------|
| `--memory 1Gi` | 1 GB RAM | Suficiente para OCR con 2 workers paralelos |
| `--cpu 1` | 1 vCPU | Free tier |
| `--timeout 600` | 10 min | Procesamiento de lotes de PDFs con OCR |
| `--max-instances 1` | 1 instancia | Controla costos en free tier |
| `--allow-unauthenticated` | Sí | JWT se valida en FastAPI, no en Cloud Run |
| `--region us-central1` | Iowa | Menor latencia para el free tier |

### Troubleshooting

**Error: `Bad syntax for dict arg`** en `--set-env-vars`

Causa: los valores con `:` o `,` (URLs) confunden al parser de gcloud.

Solución aplicada: prefijo `^|^` cambia el separador de `,` a `|`:
```bash
--set-env-vars="^|^KEY1=val1|KEY2=val2|ALLOWED_ORIGINS=https://...,http://..."
```

**Error: `PERMISSION_DENIED`**

Verificar que los 3 roles están asignados a la service account:
```bash
gcloud projects get-iam-policy taxops-497921 \
  --flatten="bindings[].members" \
  --filter="bindings.members:taxops-deployer"
```

**Ver logs en tiempo real**
```bash
gcloud run services logs read taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --limit 50
```

---

## CI/CD Pipeline

### Workflows activos

| Workflow | Archivo | Trigger | Descripción |
|----------|---------|---------|-------------|
| **CI** | `ci.yml` | push / PR a `main` | Lint + tests (Python + Next.js) |
| **Deploy** | `deploy-cloud-run.yml` | push a `main` (CI pass) | Build Docker → push Artifact Registry → deploy Cloud Run |

### Jobs del workflow CI (`ci.yml`)

| Job | Pasos |
|-----|-------|
| `api-lint` | flake8 + mypy sobre `api/` |
| `api-test` | pytest con cobertura |
| `web-lint` | ESLint + tsc sobre `taxops-web/` |
| `web-build` | `next build` (verifica que compile) |

### Jobs del workflow Deploy (`deploy-cloud-run.yml`)

```
1. actions/checkout@v4
2. google-github-actions/auth@v2        ← autentica con GCP_SA_KEY
3. google-github-actions/setup-gcloud@v2
4. gcloud auth configure-docker         ← configura Docker para Artifact Registry
5. docker build + docker push           ← imagen tagueada con el SHA del commit
6. gcloud run deploy taxops-api         ← zero-downtime rolling deploy
7. gcloud run services describe         ← imprime la URL en el Summary
```

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
│   ├── Dockerfile-api                # Multi-stage build desde raíz del repo
│   ├── main.py                       # App, CORS, routers, Alembic startup
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
│       ├── exogenas.py               # Background jobs con ThreadPoolExecutor
│       ├── chatbot.py
│       └── calendario.py
│
├── taxops-web/                       # Next.js 15.3 frontend
│   ├── vercel.json
│   ├── next.config.ts
│   ├── middleware.ts                 # Auth gate JWT (protege /dashboard /*)
│   ├── app/
│   │   ├── page.tsx                  # Landing pública
│   │   ├── login/
│   │   ├── api/auth/                 # login / logout / session / callback
│   │   └── (app)/                    # Rutas autenticadas
│   │       ├── dashboard/
│   │       ├── nomina/
│   │       ├── calendario/
│   │       ├── facturas/
│   │       ├── exogenas/
│   │       ├── chatbot/
│   │       ├── admin/
│   │       └── perfil/
│   ├── components/
│   └── lib/
│
├── pipeline/                         # Procesamiento facturas DIAN
│   ├── extractor.py                  # PDF/XML → dict (thread-safe)
│   ├── validator.py                  # CUFE, NIT, cuadre
│   ├── prorateo.py                   # Art. 490 ET
│   ├── excel_writer.py               # Workbook 3 hojas
│   └── autorretenedores.txt          # 3.287 NITs DIAN (feb 2026)
│
├── exogenas/
│   └── extractor.py                 # Certificados retención (12+ layouts)
│
├── services/
│   ├── processor.py                 # Orquestación pipeline facturas
│   ├── processor_exogenas.py        # Orquestación pipeline exógenas
│   ├── chatbot.py                   # Multi-provider (Groq/OpenAI/Anthropic/Google)
│   └── nomina.py                    # Cálculos CST 2026
│
├── db/
│   ├── init.sql                     # Schema multi-tenant completo
│   └── database.py                  # Capa SQLAlchemy (degraded mode)
│
├── docs/
│   └── GCP_MONITORING.md            # Guía de monitoreo Google Cloud
│
├── manage.py                        # CLI: init-db, create-org
├── home_gate.py                     # Auth gate Streamlit (local/SaaS)
├── Home.py                          # Streamlit landing (legacy)
├── vercel.json
├── requirements.txt                 # Dependencias Streamlit
└── tests/
    ├── test_extractor.py            # 44 tests
    ├── test_validator.py            # 19 tests
    ├── test_prorateo.py             # 12 tests
    ├── test_chatbot.py              # 11 tests
    ├── test_e2e.py                  # 32 tests (requieren PDFs)
    ├── test_auth.py
    ├── test_home_login_gate.py
    ├── test_manage.py
    ├── test_database_lazy.py
    ├── test_get_org_id.py
    ├── test_processor_db.py
    └── test_processor_exogenas_db.py
```

---

## Tests

```bash
# Unitarios (sin PDFs ni DB)
python -m pytest tests/test_extractor.py tests/test_validator.py \
                 tests/test_prorateo.py tests/test_chatbot.py -v

# End-to-end (requieren PDFs en pipeline/)
python -m pytest tests/test_e2e.py -v

# Con cobertura
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
- [x] Migración a **Google Cloud Run** (1 GB RAM, scale-to-zero, deploy automático)
- [x] CI/CD GitHub Actions → Artifact Registry → Cloud Run

### 🚧 v1.1 — Próximo

- [ ] Rate limiting por organización
- [ ] Invitaciones por email (hoy el owner crea usuarios directamente)
- [ ] Permisos por grupo (módulos bloqueados en frontend)
- [ ] Script auto-update calendario DIAN (parsear PDF DIAN anual)
- [ ] Fixes extractor exógenas (5 layouts pendientes)

### 🔮 v2.0 — Futuro

- [ ] Multi-empresa / clientes por contador
- [ ] ZIP batch upload de facturas
- [ ] Integración ERP (SIIGO / Helisa)
- [ ] App móvil (React Native / Expo)

---

## Licencia

Propietario — ABA Projects. Todos los derechos reservados.
