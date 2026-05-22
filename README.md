---
title: TaxOps SaaS
emoji: 🧾
colorFrom: orange
colorTo: blue
sdk: docker
pinned: false
---

# TaxOps — Plataforma Contable SaaS Colombia

> Automatización contable para empresas colombianas: facturas DIAN, nómina CST 2026, calendario tributario, exógenas Formato 1003 y chatbot contable con IA.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.3-black?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)

---

## Índice

1. [¿Qué hace TaxOps?](#qué-hace-taxops)
2. [Stack tecnológico](#stack-tecnológico)
3. [Arquitectura](#arquitectura)
4. [Módulos implementados](#módulos-implementados)
5. [Inicio rápido (local)](#inicio-rápido-local)
6. [Variables de entorno](#variables-de-entorno)
7. [API Reference](#api-reference)
8. [Despliegue en Railway](#despliegue-en-railway)
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
| **Calendario DIAN** | 17 fechas tributarias 2026 con alertas automáticas |
| **Chatbot IA** | Asistente contable sobre Groq llama-3.3-70b-versatile |
| **Dashboard** | Métricas, accesos rápidos y notificaciones de vencimiento |

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 15.3 · App Router · TypeScript · Tailwind CSS |
| Backend | FastAPI 0.115 + Uvicorn |
| Base de datos | PostgreSQL 16 |
| Auth | JWT (access 30 min / refresh 7 d) + bcrypt |
| IA | Groq API — llama-3.3-70b-versatile |
| PDF export | ReportLab 4.2 |
| Excel export | openpyxl 3.1 |
| Extracción PDF/XML | pdfplumber 0.11 + lxml 5.3 |
| Contenedores | Docker + Docker Compose |
| Deploy | Railway (api + web + postgres) |
| PWA | Web App Manifest + shortcuts |

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│              :3000  (taxops-web)            │
│           Next.js 15 — App Router           │
│  middleware.ts → auth gate (JWT cookie)     │
└──────────────────┬──────────────────────────┘
                   │ HTTP / useApi hook
┌──────────────────▼──────────────────────────┐
│              :8000  (api/)                  │
│            FastAPI + Uvicorn                │
│  /auth  /nomina  /facturas  /exogenas       │
│  /chatbot  /admin                           │
└──────────────────┬──────────────────────────┘
                   │ SQLAlchemy / psycopg2
┌──────────────────▼──────────────────────────┐
│              :5432  (db)                    │
│           PostgreSQL 16                     │
│  db=taxops · multi-tenant ready             │
└─────────────────────────────────────────────┘
       :8080 → Adminer (solo local)
```

### Flujo de autenticación

```
Browser → POST /api/auth/login (Next.js route) → POST /auth/token (FastAPI)
       ← Set-Cookie: taxops_access_token (httpOnly, 30 min)
       ← Set-Cookie: taxops_refresh_token (httpOnly, 7 d)

Requests protegidos → middleware.ts verifica cookie
                    → useApi hook añade Authorization: Bearer <token>
```

### Rutas públicas vs protegidas

`middleware.ts` deja pasar sin auth:
- `/` — landing page
- `/login`
- `/api/auth/*`
- `/manifest.json`, `/_next/*`, `/icons/*` (estáticos)

Todo lo demás redirige a `/login`.

---

## Módulos implementados

### 1. Landing page pública (`/`)

- Completamente pública (no requiere auth)
- Hero + 3-step explainer + 9 features + pricing mensual/anual (−20%)
- Preview calendario DIAN + 3 testimonios + formulario de contacto
- Responsive · dark mode compatible · PWA installable

### 2. Autenticación

- Login en `/login` con JWT
- Refresh automático de access token via cookie httpOnly
- Logout limpia ambas cookies vía `/api/auth/logout`
- `useApi` hook: maneja Authorization header en todas las llamadas

### 3. Dashboard (`/dashboard`)

- KPIs: facturas procesadas, IVA acumulado, nóminas calculadas
- Quick actions con colores por módulo: Facturas (orange), Nómina (blue), Calendario DIAN (cyan), Chatbot (purple)
- Notificaciones inline de vencimientos próximos DIAN

### 4. Nómina CST 2026 (`/nomina`)

**4 tabs:**

#### Nómina Mensual
- Presets SMLMV: 1×, 2×, 3×, 5×, 10×, Integral (botón → activo naranja)
- Horas extras y recargos: HED +25%, HEN +75%, RN +35%, HOD +75%, HEDD +100%, HEND +150%, RND +110%
- Parafiscales empleador: Salud 8.5%, Pensión 12%, ARL clase I–V, SENA 2%, ICBF 3%, Caja Compensación 4%
- Exoneración SENA+ICBF automática para salarios ≤10 SMLMV (Art. 114-1 ET, Ley 1607/2012)
- FSP Fondo Solidaridad Pensional para IBC ≥4 SMLMV
- Export Excel (.xlsx) y PDF (ReportLab, branding navy/orange)

#### Liquidación definitiva
- Cesantías (base 360 días), intereses 12% anual, prima de servicios, vacaciones
- Indemnización Art. 64 CST según tipo de contrato y causa de terminación
- Export Excel y PDF

#### Empleados
- Directorio en `localStorage` (`taxops_empleados`)
- "Nuevo empleado" con presets SMLMV integrados
- Botones "Mensual" / "Liquidar" → pre-llenan el formulario y cambian de tab
- **Batch import**: drag-and-drop Excel/CSV → `POST /nomina/import-batch`
  - Columnas requeridas: `nombre`, `salario_basico`
  - Columnas opcionales: `dias_trabajados`, `clase_riesgo_arl`
- Tabla de resultados con totales + "Descargar Excel" batch

#### Analítica
- Historial de cálculos (`localStorage`, últimos 20)
- KPIs: total cálculos, neto promedio, mayor neto, carga patronal promedio
- Gráfico de barras: Neto (naranja) vs Carga patronal (azul)

**Parámetros legales CST 2026:**

| Concepto | Valor |
|----------|-------|
| SMLMV | $1,750,905 |
| Auxilio de transporte | $249,095 (aplica ≤2 SMLMV) |
| Salario integral mínimo | $22,761,765 (13× SMLMV) |
| Tope IBC | $43,772,625 (25× SMLMV) |
| Jornada máxima (Ley 2101/2021) | 44 h/sem → 42 h en 2026 |

### 5. Calendario DIAN 2026 (`/calendario`)

- 17 eventos tributarios agrupados por mes
- Alerta visual roja para eventos ≤10 días
- Filtros por tipo: retención, IVA, renta, exógenas, ICA, patrimonio, otro
- Toggle "solo próximos"
- Export ICS → importa directo a Google Calendar / Apple Calendar
- Chatbot contextualizado con normativa DIAN 2026

### 6. Notification Bell (header global)

- Vencimientos DIAN dentro de los próximos 30 días
- Badge naranja con contador de alertas activas
- Urgencia: rojo ≤3 d / ámbar ≤10 d / azul ≤30 d
- Dismiss por evento o "limpiar todo"
- Persistencia: `localStorage` (`taxops_notif_dismissed`)
- Link "Ver calendario completo →"

### 7. Facturas DIAN (`/facturas`)

- Upload de PDF/XML electrónicos (pdfplumber + lxml UBL 2.1)
- Extracción: CUFE, NIT/nombre emisor, fecha, base, IVA, total
- Validación: cuadre (base + IVA = total), CUFE 96 chars, formato NIT
- Detección automática: Nota Crédito/Débito, Mandato/Peaje, Soporte
- Deduplicación por CUFE en PostgreSQL (`ON CONFLICT DO NOTHING`)
- Autorretenedores: 3.287 NITs DIAN — retención $0 para ellos
- Export Excel 3 hojas: BASE_DATOS, VALIDACION, PRORRATEO_IVA
- Chatbot con contexto de las facturas cargadas

### 8. Prorrateo IVA Art. 490 ET

```
% deducible = ingresos_gravados / (ingresos_gravados + ingresos_excluidos)
IVA descontable = IVA_compras × % deducible
```

- Sin ingresos informados → 100% deducible con advertencia
- Mandatos/Peajes → IVA no descontable
- Notas Crédito → valores negativos reducen el total del mes

### 9. Exógenas Formato 1003 (`/exogenas`)

- Generación del reporte de pagos a terceros DIAN
- Agrupación por NIT proveedor
- Export Excel compatible DIAN

### 10. Chatbot Contable (`/chatbot`)

- Groq llama-3.3-70b-versatile (gratuito)
- Contexto: ET 2026, CST, DIAN, normativa colombiana
- Historial por sesión
- `PageChatbot` embebible en cualquier módulo con `systemContext` y `currentData`

### 11. PWA

- `public/manifest.json`: nombre, iconos, start_url (`/dashboard`), shortcuts
- Shortcuts: Nómina (`/nomina`) y Calendario DIAN (`/calendario`)
- Theme color navy `#1A3A5C`
- Installable en Chrome/Edge desktop y Android

---

## Inicio rápido (local)

### Prerrequisitos

- Docker Desktop ≥ 4.x

### 1. Variables de entorno

```bash
cp api/.env.example api/.env
cp taxops-web/.env.local.example taxops-web/.env.local
```

Editar `api/.env`:
```env
DATABASE_URL=postgresql://taxops:taxops_local_2026@db:5432/taxops
SECRET_KEY=cambia_esto_por_minimo_32_caracteres_aleatorios
GROQ_API_KEY=gsk_...
```

Editar `taxops-web/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
INTERNAL_API_URL=http://api:8000
NEXTAUTH_SECRET=otro_secreto_seguro_minimo_32_chars
```

### 2. Build y arrancar

```bash
docker compose build
docker compose up -d
```

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Adminer (BD) | http://localhost:8080 |

### 3. Crear primer usuario

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.co","password":"Admin1234!","nombre":"Admin"}'
```

### 4. Verificar

```bash
# Landing pública (sin auth)
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000     # → 200

# API healthy
curl http://localhost:8000/health                                  # → {"status":"ok"}

# PWA manifest
curl http://localhost:3000/manifest.json | python3 -m json.tool   # → JSON válido
```

---

## Variables de entorno

### API (`api/.env`)

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `DATABASE_URL` | Conexión PostgreSQL | ✅ |
| `SECRET_KEY` | Firma JWT (mín. 32 chars) | ✅ |
| `GROQ_API_KEY` | API key Groq | ✅ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración access token | No (default: 30) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración refresh token | No (default: 7) |

### Frontend (`taxops-web/.env.local`)

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `NEXT_PUBLIC_API_URL` | URL pública de la API | ✅ |
| `INTERNAL_API_URL` | URL interna Docker/Railway | ✅ |
| `NEXTAUTH_SECRET` | Firma de sesión Next.js | ✅ |

---

## API Reference

Documentación interactiva completa: `http://localhost:8000/docs` (Swagger UI)

### Auth

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/token` | Login → access + refresh token |
| POST | `/auth/refresh` | Renovar access token |
| POST | `/auth/register` | Crear usuario |
| GET | `/auth/me` | Perfil del usuario autenticado |

### Nómina

| Método | Endpoint | Body / Params | Descripción |
|--------|----------|---------------|-------------|
| GET | `/nomina/parametros` | — | Parámetros legales 2026 |
| POST | `/nomina/mensual` | `EntradaNomina` JSON | Calcular nómina mensual |
| POST | `/nomina/liquidacion` | `EntradaLiquidacion` JSON | Calcular liquidación |
| POST | `/nomina/export` | `{tipo, ...campos}` | Excel nómina o liquidación |
| POST | `/nomina/export-pdf` | `{tipo, ...campos}` | PDF nómina o liquidación |
| POST | `/nomina/import-batch` | `multipart/form-data file=` | Importar Excel/CSV → JSON |
| POST | `/nomina/export-batch` | `{rows: [...]}` | Excel resultados batch |

**`EntradaNomina` campos principales:**

```json
{
  "salario_basico": 1750905,
  "dias_trabajados": 30,
  "clase_riesgo_arl": 1,
  "tipo_salario": "ordinario",
  "hed": 0, "hen": 0, "rn": 0, "hod": 0, "hedd": 0, "hend": 0, "rnd": 0,
  "bonificaciones_salariales": 0,
  "comisiones": 0,
  "otros_no_salariales": 0,
  "retencion_fuente": 0,
  "otras_deducciones": 0
}
```

### Facturas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/facturas/upload` | Subir PDF/XML DIAN (multipart) |
| GET | `/facturas/` | Listar facturas del tenant |
| DELETE | `/facturas/{id}` | Eliminar factura |
| POST | `/facturas/export` | Excel 3 hojas |

### Chatbot

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/chatbot/mensaje` | Enviar mensaje |
| GET | `/chatbot/historial` | Historial de la sesión |
| DELETE | `/chatbot/historial` | Limpiar historial |

---

## Despliegue en Railway

### Estructura de servicios

```
GitHub repo (main)
├── Servicio: api
│   ├── Dockerfile: api/Dockerfile-api
│   ├── Root directory: /
│   └── Env vars: SECRET_KEY, GROQ_API_KEY
│       DATABASE_URL ← inyectado por el plugin PostgreSQL
│
├── Servicio: web
│   ├── Dockerfile: taxops-web/Dockerfile
│   ├── Root directory: taxops-web/
│   └── Env vars: NEXT_PUBLIC_API_URL (URL pública del servicio api)
│                INTERNAL_API_URL, NEXTAUTH_SECRET
│
└── Plugin: PostgreSQL
    └── DATABASE_URL → inyectado automáticamente al servicio api
```

### Pasos

1. Crear proyecto en [railway.app](https://railway.app)
2. Add plugin → **PostgreSQL**
3. Add service → GitHub → este repo → configurar servicio **api**:
   - Dockerfile path: `api/Dockerfile-api`
   - Variables: `SECRET_KEY`, `GROQ_API_KEY`
4. Add service → GitHub → este repo → configurar servicio **web**:
   - Root directory: `taxops-web`
   - Variables: `NEXT_PUBLIC_API_URL`, `NEXTAUTH_SECRET`
5. Push a `main` → Railway hace rebuild automático

### Health checks Railway

```
GET /health         → {"status":"ok","version":"1.0.0"}   (API)
GET /manifest.json  → PWA manifest válido                  (Web)
```

---

## Estructura del repositorio

```
proyecto-facturas/
├── api/                          # FastAPI backend
│   ├── Dockerfile-api
│   ├── main.py                   # App, CORS, routers, lifespan
│   ├── dependencies.py           # get_current_user, get_db
│   ├── schemas.py                # Pydantic schemas
│   ├── requirements-api.txt
│   ├── .env.example
│   ├── core/
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   └── security.py           # JWT, bcrypt
│   ├── alembic/                  # Migraciones de BD
│   │   ├── env.py                # Lee DATABASE_URL de settings
│   │   └── versions/001_initial_schema.py
│   ├── alembic.ini               # Config Alembic (cd api/ && alembic upgrade head)
│   └── routers/
│       ├── auth.py
│       ├── nomina.py             # 7 endpoints nómina
│       ├── invoices.py
│       ├── exogenas.py
│       ├── chatbot.py
│       └── admin.py
│
├── taxops-web/                   # Next.js 15.3 frontend
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── tailwind.config.ts        # brand-orange #E05519, brand-navy #1A3A5C
│   ├── middleware.ts             # Auth gate
│   ├── public/
│   │   └── manifest.json         # PWA manifest
│   ├── app/
│   │   ├── page.tsx              # Landing pública
│   │   ├── login/page.tsx
│   │   ├── layout.tsx            # Root layout + PWA meta tags
│   │   ├── api/auth/             # login / logout / session routes
│   │   └── (app)/                # Rutas autenticadas
│   │       ├── layout.tsx        # Sidebar + Header
│   │       ├── dashboard/page.tsx
│   │       ├── nomina/page.tsx   # 4 tabs, presets, batch
│   │       ├── calendario/page.tsx
│   │       ├── facturas/page.tsx
│   │       ├── exogenas/page.tsx
│   │       └── chatbot/page.tsx
│   ├── components/
│   │   ├── PageChatbot.tsx       # Chatbot embebible
│   │   └── layout/
│   │       ├── sidebar.tsx       # Nav lateral con CalendarDays
│   │       └── header.tsx        # ThemeToggle + NotificationBell
│   └── lib/
│       ├── api.ts                # useApi: get/post/postForm/patch/del
│       └── auth.tsx              # Auth context
│
├── services/
│   ├── nomina.py                 # Lógica CST 2026 (calcular_nomina, calcular_liquidacion)
│   └── processor.py             # Pipeline facturas
│
├── extractor.py                  # PDF/XML DIAN → dict
├── validator.py                  # CUFE, NIT, cuadre
├── prorateo.py                   # Art. 490 ET
├── autorretenedores.txt          # 3.287 NITs DIAN (feb 2026)
├── docker-compose.yml
├── docs/
│   ├── ARQUITECTURA.md
│   ├── API.md
│   ├── DESPLIEGUE.md
│   ├── TaxOps-Design-Brief.md
│   └── TaxOps-Logo-Horizontal.svg
│
├── Home.py, pages/               # ⚠️ LEGACY — app Streamlit original (no usar en prod)
│                                 #   El stack productivo es FastAPI + Next.js (api/ + taxops-web/)
│
└── tests/
    ├── test_extractor.py         # 44 tests
    ├── test_validator.py         # 19 tests
    ├── test_prorateo.py          # 12 tests
    ├── test_chatbot.py           # 11 tests
    └── test_e2e.py               # 32 tests (requieren PDFs)
```

---

## Roadmap

### ✅ v1.0 MVP — Implementado

- [x] Landing page pública con pricing mensual/anual
- [x] Autenticación JWT (login/logout/refresh/cookies httpOnly)
- [x] Dashboard con KPIs y quick actions
- [x] Nómina mensual CST 2026 (parafiscales, HE, exoneración SENA/ICBF)
- [x] Liquidación definitiva (cesantías, prima, vacaciones, indemnización)
- [x] Presets SMLMV con selector visual
- [x] Export nómina a Excel y PDF (ReportLab)
- [x] Directorio de empleados (localStorage)
- [x] Batch import desde Excel/CSV + export batch Excel
- [x] Calendario DIAN 2026 (17 eventos, filtros, export ICS)
- [x] Notification bell con alertas 30 días (urgencia por color)
- [x] Chatbot IA (Groq llama-3.3-70b) + PageChatbot embebible
- [x] Facturas DIAN PDF/XML (extracción, validación, deduplicación)
- [x] Exógenas Formato 1003
- [x] Prorrateo IVA Art. 490 ET
- [x] PWA manifest (installable)
- [x] Dark mode (ThemeToggle, localStorage persistencia)
- [x] Docker Compose local + Railway producción

### 🚧 v1.1 — Próximo

- [ ] Iconos PWA (`/public/icons/icon-192.png`, `icon-512.png`)
- [ ] Plantilla Excel descargable para batch import nómina
- [ ] Persistencia empleados en BD (actualmente localStorage)
- [ ] Email alerts vencimientos DIAN (Resend.com)
- [ ] Google Calendar OAuth sync

### 🔮 v2.0 — Futuro

- [ ] Multi-empresa / multi-tenant por NIT
- [ ] ZIP batch upload de facturas
- [ ] Integración ERP (SIIGO API / Helisa)
- [ ] PayU Colombia gateway
- [ ] App móvil (React Native / Expo)

---

## Marca

| Token | Valor |
|-------|-------|
| `brand-orange` | `#E05519` |
| `brand-navy` | `#1A3A5C` |
| Fuente | Inter (Google Fonts) |
| Logos | `docs/TaxOps-Logo-Horizontal.svg` |

---

## Tests (pipeline Python)

```bash
# Solo unitarios (sin PDFs)
python3 -m pytest tests/test_extractor.py tests/test_validator.py \
                  tests/test_prorateo.py tests/test_chatbot.py -v

# Con cobertura
python3 -m pytest --cov=. --cov-report=term-missing
```

---

## Licencia

Propietario — ABA Projects. Todos los derechos reservados.
