# TaxOps — Plataforma Contable SaaS Colombia

> Automatización contable para empresas colombianas: facturas DIAN, nómina CST 2026, calendario tributario, exógenas Formato 1003 y chatbot contable con IA.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.3-black?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)](https://postgresql.org)
[![Render](https://img.shields.io/badge/API-Render-46E3B7?logo=render)](https://taxops-api.onrender.com)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel-black?logo=vercel)](https://tax-ops-11.vercel.app)

**Producción:**
- Frontend: [https://tax-ops-11.vercel.app](https://tax-ops-11.vercel.app)
- API: [https://taxops-api.onrender.com](https://taxops-api.onrender.com)
- API Docs: [https://taxops-api.onrender.com/docs](https://taxops-api.onrender.com/docs)

---

## Índice

1. [¿Qué hace TaxOps?](#qué-hace-taxops)
2. [Stack tecnológico](#stack-tecnológico)
3. [Arquitectura](#arquitectura)
4. [Módulos implementados](#módulos-implementados)
5. [Inicio rápido (local)](#inicio-rápido-local)
6. [Variables de entorno](#variables-de-entorno)
7. [API Reference](#api-reference)
8. [Despliegue (Render + Vercel)](#despliegue-render--vercel)
9. [Estructura del repositorio](#estructura-del-repositorio)
10. [Roadmap](#roadmap)

---

## ¿Qué hace TaxOps?

| Módulo | Descripción |
|--------|-------------|
| **Facturas DIAN** | Extrae y valida PDFs/XMLs electrónicos (CUFE, NIT, IVA, totales) |
| **Prorrateo IVA** | Cálculo Art. 490 ET para IVA descontable parcial |
| **Nómina CST 2026** | Nómina mensual + liquidación definitiva con parafiscales correctos |
| **Exógenas 1003** | Generación Formato 1003 DIAN para proveedores |
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
| Extracción PDF/XML | pdfplumber 0.11 + lxml 5.3 |
| Streamlit (legacy) | Interfaz original — mantiene compatibilidad local |
| Deploy API | Render (Docker, free tier) |
| Deploy Frontend | Vercel (Next.js, hobby tier) |

---

## Arquitectura

```
┌─────────────────────────────────────────────────┐
│   https://tax-ops-11.vercel.app                 │
│           Next.js 15 — App Router               │
│   middleware.ts → auth gate (JWT cookie)        │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS / useApi hook
┌──────────────────▼──────────────────────────────┐
│   https://taxops-api.onrender.com               │
│            FastAPI + Uvicorn (Docker)           │
│   /auth  /nomina  /facturas  /exogenas          │
│   /chatbot  /admin  /calendario                 │
└──────────────────┬──────────────────────────────┘
                   │ SQLAlchemy / psycopg2
┌──────────────────▼──────────────────────────────┐
│           PostgreSQL 16 (Neon)                  │
│   multi-tenant · Alembic migrations             │
└─────────────────────────────────────────────────┘
```

### Flujo de autenticación

```
Browser → POST /api/auth/login (Next.js route) → POST /auth/token (FastAPI)
       ← Set-Cookie: taxops_access_token (httpOnly, 30 min)
       ← Set-Cookie: taxops_refresh_token (httpOnly, 7 d)

Requests protegidos → middleware.ts verifica cookie
                    → useApi hook añade Authorization: Bearer <token>
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
- PostgreSQL (o `DATABASE_URL` de Neon/Supabase)

### 1. Instalar dependencias

```bash
# Backend
pip install -r requirements.txt
pip install -e .          # expone CLI `taxops`

# API
pip install -r api/requirements-api.txt

# Frontend
cd taxops-web && npm install
```

### 2. Variables de entorno

```bash
cp .env.example .env
cp api/.env.example api/.env
```

Editar `api/.env`:
```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
SECRET_KEY=cambia_esto_por_minimo_32_caracteres_aleatorios
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
| `DATABASE_URL` | Conexión PostgreSQL (Neon/local) | ✅ |
| `SECRET_KEY` | Firma JWT (mín. 32 chars) | ✅ |
| `GROQ_API_KEY` | API key Groq | ✅ |
| `BOOTSTRAP_SECRET` | Secret para endpoint de arranque | ✅ |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | ✅ |
| `ALGORITHM` | Algoritmo JWT | No (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración access token | No (default: 30) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración refresh token | No (default: 7) |
| `TAXOPS_SUPERADMIN_EMAILS` | Emails con acceso superadmin | No |

### Frontend (`taxops-web/.env.local`)

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `NEXT_PUBLIC_API_URL` | URL pública de la API | ✅ |

---

## API Reference

Documentación interactiva completa: [https://taxops-api.onrender.com/docs](https://taxops-api.onrender.com/docs)

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
| DELETE | `/admin/users/{id}/permanent` | require_owner | Eliminar usuario |
| GET/POST | `/admin/groups` | require_admin/owner | CRUD grupos |
| GET | `/admin/audit-logs` | require_admin | Logs de auditoría |

### Calendario

| Método | Endpoint | Guard | Descripción |
|--------|----------|-------|-------------|
| GET | `/calendario/eventos` | get_current_user | Eventos DIAN del año en curso |
| PUT | `/calendario/eventos` | require_superadmin | Reemplazar todos los eventos |
| POST | `/calendario/eventos` | require_superadmin | Agregar evento |
| DELETE | `/calendario/eventos/{id}` | require_superadmin | Eliminar evento |

---

## Despliegue (Render + Vercel)

### Render — API

```
Repo: ABA-projects/TaxOps-11 / branch: main
Dockerfile: api/Dockerfile-api
URL: https://taxops-api.onrender.com
```

**Variables de entorno requeridas en Render:**

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Conexión Neon PostgreSQL |
| `SECRET_KEY` | Clave JWT |
| `GROQ_API_KEY` | API key Groq |
| `BOOTSTRAP_SECRET` | Secret de arranque |
| `ALLOWED_ORIGINS` | `https://tax-ops-11.vercel.app,http://localhost:3000` |

Alembic corre automáticamente en el startup del contenedor (`api/main.py` llama `alembic upgrade head`).

### Vercel — Frontend

```
Repo: ABA-projects/TaxOps-11 / branch: main
Root Directory: taxops-web
Framework: Next.js
URL: https://tax-ops-11.vercel.app
```

**Variables de entorno requeridas en Vercel:**

| Variable | Valor |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://taxops-api.onrender.com` |

### CI/CD

- Push a `main` → Vercel redeploya automáticamente (webhook GitHub)
- Push a `main` → Render redeploya automáticamente (webhook GitHub)
- `.github/workflows/ci.yml` — flake8+mypy (api-lint), pytest (api-test), ESLint+tsc (web-lint), next build (web-build)

---

## Estructura del repositorio

```
TaxOps-11/
├── api/                          # FastAPI backend
│   ├── Dockerfile-api
│   ├── main.py                   # App, CORS, routers, Alembic startup
│   ├── requirements-api.txt
│   ├── .env.example
│   ├── alembic/                  # Migraciones DB
│   ├── core/                     # config.py, security.py
│   ├── data/
│   │   └── calendario_2026.json  # 31 eventos DIAN (fuente de verdad)
│   └── routers/
│       ├── auth.py
│       ├── admin.py
│       ├── nomina.py
│       ├── facturas.py
│       ├── exogenas.py
│       ├── chatbot.py
│       └── calendario.py
│
├── taxops-web/                   # Next.js 15.3 frontend
│   ├── vercel.json               # { "framework": "nextjs" }
│   ├── next.config.ts
│   ├── middleware.ts             # Auth gate JWT
│   ├── app/
│   │   ├── page.tsx              # Landing pública
│   │   ├── login/
│   │   ├── api/auth/             # login / logout / session / callback
│   │   └── (app)/               # Rutas autenticadas
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
├── pipeline/                     # Procesamiento facturas DIAN
│   ├── extractor.py              # PDF/XML → dict (thread-safe)
│   ├── validator.py              # CUFE, NIT, cuadre
│   ├── prorateo.py               # Art. 490 ET
│   ├── excel_writer.py           # Workbook 3 hojas
│   └── autorretenedores.txt      # 3.287 NITs DIAN (feb 2026)
│
├── exogenas/
│   └── extractor.py             # Certificados retención (12+ layouts)
│
├── services/
│   ├── processor.py             # Orquestación pipeline facturas
│   ├── processor_exogenas.py    # Orquestación pipeline exógenas
│   ├── chatbot.py               # Multi-provider (Groq/OpenAI/Anthropic/Google)
│   └── nomina.py                # Cálculos CST 2026
│
├── db/
│   ├── init.sql                 # Schema multi-tenant completo
│   └── database.py              # Capa SQLAlchemy (degraded mode)
│
├── manage.py                    # CLI: init-db, create-org
├── home_gate.py                 # Auth gate Streamlit (local/SaaS)
├── Home.py                      # Streamlit landing (legacy)
├── render.yaml                  # Render deployment config
├── vercel.json                  # { "framework": "nextjs" }
├── requirements.txt             # Dependencias Streamlit
└── tests/
    ├── test_extractor.py        # 44 tests
    ├── test_validator.py        # 19 tests
    ├── test_prorateo.py         # 12 tests
    ├── test_chatbot.py          # 11 tests
    ├── test_e2e.py              # 32 tests (requieren PDFs)
    ├── test_auth.py
    ├── test_home_login_gate.py
    ├── test_manage.py
    ├── test_database_lazy.py
    ├── test_get_org_id.py
    ├── test_processor_db.py
    └── test_processor_exogenas_db.py
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
- [x] Exógenas Formato 1003 (12+ layouts)
- [x] Admin panel (usuarios, grupos, audit logs)
- [x] Deploy Render (API) + Vercel (Frontend)
- [x] CI/CD automático en push a main

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

## Licencia

Propietario — ABA Projects. Todos los derechos reservados.
