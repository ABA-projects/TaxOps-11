# TaxOps — Arquitectura del sistema

## Visión general

TaxOps es una plataforma SaaS de automatización contable para Colombia. La arquitectura separa el frontend (Next.js), el backend (FastAPI) y la base de datos (PostgreSQL) en tres servicios Docker independientes, comunicados por red interna.

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                             │
│  Usuario browser / PWA instalada                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────────────────┐
│                taxops-web  (:3000)                          │
│                Next.js 15.3 · App Router                    │
│                                                             │
│  app/page.tsx              ← landing pública                │
│  app/(app)/dashboard/      ← rutas autenticadas             │
│  app/(app)/nomina/         ← nómina 4 tabs                  │
│  app/(app)/calendario/     ← DIAN 2026                      │
│  app/(app)/facturas/       ← PDF/XML upload                 │
│  app/(app)/exogenas/       ← Formato 1003                   │
│  app/(app)/chatbot/        ← chatbot IA                     │
│                                                             │
│  middleware.ts             ← auth gate (JWT cookie)         │
│  components/layout/header  ← NotificationBell               │
│  lib/api.ts (useApi)       ← HTTP + auth + blob             │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP interno (useApi hook)
                      │ Authorization: Bearer <access_token>
┌─────────────────────▼───────────────────────────────────────┐
│                    api/  (:8000)                            │
│               FastAPI 0.115 + Uvicorn                       │
│                                                             │
│  routers/auth.py           ← /auth/*                        │
│  routers/nomina.py         ← /nomina/* (7 endpoints)        │
│  routers/invoices.py       ← /facturas/*                    │
│  routers/exogenas.py       ← /exogenas/*                    │
│  routers/chatbot.py        ← /chatbot/*                     │
│  routers/admin.py          ← /admin/*                       │
│                                                             │
│  services/nomina.py        ← lógica CST 2026                │
│  services/processor.py     ← pipeline facturas              │
│  extractor.py / validator  ← PDF/XML DIAN                   │
└─────────────────────┬───────────────────────────────────────┘
                      │ SQLAlchemy + psycopg2
┌─────────────────────▼───────────────────────────────────────┐
│                     db  (:5432)                             │
│              PostgreSQL 16                                  │
│  db=taxops · user=taxops                                    │
│  Adminer en :8080 (solo local)                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Capa de autenticación

### Tokens JWT

| Token | TTL | Almacenamiento | Uso |
|-------|-----|----------------|-----|
| `access_token` | 30 min | Cookie httpOnly `taxops_access_token` | Autorizar API calls |
| `refresh_token` | 7 días | Cookie httpOnly `taxops_refresh_token` | Renovar access token |

### Flujo completo

```
1. POST /api/auth/login (Next.js route)
   ↓ body: { email, password }
   ↓ llama POST /auth/token (FastAPI)
   ↓ FastAPI verifica bcrypt → genera JWT
   ← Set-Cookie: taxops_access_token (httpOnly, Secure, SameSite=Lax)
   ← Set-Cookie: taxops_refresh_token (httpOnly, Secure, SameSite=Lax)
   ← redirect /dashboard

2. Requests subsiguientes
   → middleware.ts lee cookie taxops_access_token
   → si válido: pasa al handler
   → si expirado: intenta refresh con taxops_refresh_token
   → si refresh inválido: redirect /login

3. useApi hook (lib/api.ts)
   → lee cookie taxops_access_token del browser
   → añade header Authorization: Bearer <token>
   → maneja errores 401 → logout automático
```

### Middleware Next.js (`middleware.ts`)

```typescript
// Rutas siempre públicas (sin auth)
const PUBLIC_EXACT = ["/"];
const PUBLIC_PATHS = ["/login", "/api/auth", "/_next", "/icons", "/manifest.json"];

// Todo lo demás → verificar cookie → redirect /login si falta
```

---

## Frontend — Next.js 15.3

### App Router estructura

```
app/
├── layout.tsx          ← Root layout: Inter font, dark mode script, PWA meta
├── globals.css         ← Tailwind base + utilidades card, btn-primary, input
├── page.tsx            ← Landing pública ("use client", useState)
├── login/page.tsx      ← Form login con POST /api/auth/login
├── api/
│   └── auth/
│       ├── login/route.ts     ← Proxifica a FastAPI, setea cookies
│       ├── logout/route.ts    ← Borra cookies, redirect /login
│       └── session/route.ts   ← Verifica cookie, retorna user info
└── (app)/              ← Route group autenticado
    ├── layout.tsx      ← Sidebar + Header wrapper
    ├── dashboard/
    ├── nomina/
    ├── calendario/
    ├── facturas/
    ├── exogenas/
    └── chatbot/
```

### Convenciones de componentes

- **`"use client"`** en páginas con estado (useState, useEffect, useRef)
- **Server Components** para páginas estáticas sin interactividad
- **`useApi` hook** para todas las llamadas HTTP al backend
- **`PageChatbot`** componente reutilizable: recibe `moduleName`, `systemContext`, `currentData`

### Tailwind — Tokens de marca

```typescript
// tailwind.config.ts
colors: {
  "brand-orange": "#E05519",
  "brand-navy":   "#1A3A5C",
}
```

Modo oscuro: `darkMode: "class"` — activado vía `ThemeToggle` que escribe en `localStorage("taxops_theme")`.

### `useApi` hook (`lib/api.ts`)

```typescript
const { get, post, postForm, patch, del } = useApi();

// GET JSON
const data = await get<T>("/ruta");

// POST JSON → JSON
const result = await post<T>("/ruta", body);

// POST JSON → Blob (Excel/PDF)
const blob = await post<Blob>("/ruta", body, true);

// POST multipart (file upload)
const result = await postForm<T>("/ruta", formData);
```

El hook lee el token de la cookie httpOnly vía `/api/auth/session` y añade el header `Authorization: Bearer`.

---

## Backend — FastAPI

### Estructura de routers

```
api/
├── main.py              ← FastAPI app, CORS, lifespan, include_router
├── dependencies.py      ← get_current_user (verifica JWT), get_db
├── schemas.py           ← Pydantic models compartidos
├── core/
│   ├── config.py        ← Settings con pydantic-settings (lee .env)
│   └── security.py      ← create_access_token, verify_token, hash_password
└── routers/
    ├── auth.py          ← register, token, refresh, me
    ├── nomina.py        ← parametros, mensual, liquidacion, export, export-pdf,
    │                       import-batch, export-batch
    ├── invoices.py      ← upload, list, get, delete, export
    ├── exogenas.py      ← upload, export
    ├── chatbot.py       ← mensaje, historial, clear
    └── admin.py         ← users, stats (requiere rol admin)
```

### Dependencias clave

```python
# Cada endpoint protegido
async def endpoint(_: dict = Depends(get_current_user)):
    ...

# get_current_user verifica:
# 1. Header Authorization: Bearer <token>
# 2. Decodifica JWT con SECRET_KEY
# 3. Retorna payload: {sub: email, id: user_id, rol: "user"|"admin"}
```

### Nómina — lógica de cálculo (`services/nomina.py`)

El módulo es **UI-agnóstico**: recibe dataclasses Python, devuelve dataclasses. No depende de FastAPI.

```python
# Parámetros CST 2026
SMLMV = 1_750_905
AUX_TRANSPORTE = 249_095
TOPE_AUX = SMLMV * 2        # aplica aux. transporte
SALARIO_INTEGRAL = SMLMV * 13
TOPE_IBC = SMLMV * 25

# ARL por clase (Decreto 1607/2002)
ARL_RATES = {1: 0.00522, 2: 0.01044, 3: 0.02436, 4: 0.04350, 5: 0.06960}

# Exoneración SENA + ICBF (Art. 114-1 ET, Ley 1607/2012)
# Aplica cuando salario_basico <= 10 × SMLMV
TOPE_EXONERACION = SMLMV * 10
```

Funciones principales:
- `calcular_nomina(entrada: EntradaNomina) → ResultadoNomina`
- `calcular_liquidacion(entrada: EntradaLiquidacion) → ResultadoLiquidacion`

### Export PDF (`/nomina/export-pdf`)

Usa **ReportLab** (sin Chromium):
- `SimpleDocTemplate` tamaño A4
- Estilos: navy `#1A3A5C` para headers, naranja `#E05519` para totales
- Para `mensual`: secciones DEVENGADO, DEDUCCIONES, NETO A PAGAR, CARGA PATRONAL, COSTO TOTAL EMPRESA
- Para `liquidacion`: DATOS DEL CONTRATO, PRESTACIONES SOCIALES, TOTAL NETO
- Retorna `StreamingResponse(content=buffer, media_type="application/pdf")`

### Batch import (`/nomina/import-batch`)

```python
# Endpoint recibe multipart/form-data
@router.post("/import-batch")
async def import_batch(file: UploadFile = File(...), _=Depends(get_current_user)):
    content = await file.read()
    # Detecta CSV vs Excel por extensión
    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_excel(io.BytesIO(content))
    # Normaliza columnas, itera filas, llama calcular_nomina()
    # Retorna List[BatchRow]
```

---

## Base de datos — PostgreSQL 16

### Esquema actual

```sql
-- Usuarios del sistema
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    nombre VARCHAR,
    rol VARCHAR DEFAULT 'user',
    tenant_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Facturas DIAN procesadas
CREATE TABLE facturas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cufe VARCHAR(96) UNIQUE NOT NULL,   -- deduplicación
    tenant_id UUID NOT NULL,
    tipo VARCHAR,
    folio VARCHAR,
    fecha DATE,
    nit_emisor VARCHAR,
    nombre_emisor VARCHAR,
    nit_receptor VARCHAR,
    nombre_receptor VARCHAR,
    subtotal NUMERIC(18,2),
    base_iva_19 NUMERIC(18,2),
    iva_19 NUMERIC(18,2),
    base_iva_5 NUMERIC(18,2),
    iva_5 NUMERIC(18,2),
    no_gravado NUMERIC(18,2),
    total NUMERIC(18,2),
    retencion_fuente NUMERIC(18,2),
    validacion VARCHAR,
    observacion TEXT,
    fuente VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Deduplicación por CUFE

```sql
INSERT INTO facturas (...) VALUES (...)
ON CONFLICT (cufe) DO NOTHING;
-- RETURNING id → cuenta insertados vs ya existentes
```

---

## Pipeline de facturas DIAN

```
archivo PDF/XML
       │
       ▼
extractor.py
  ├── PDF: pdfplumber → regex CUFE, NIT, IVA, totales
  └── XML: lxml + UBL 2.1 namespaces → xpath directo
       │
       ▼
validator.py
  ├── Validar CUFE (96 chars hex)
  ├── Validar NIT formato colombiano
  ├── Cuadre contable: base + IVA = total (tolerancia ±1)
  └── Detectar duplicados (CUFE ya en BD)
       │
       ▼
prorateo.py
  ├── Agrupar por mes
  ├── Aplicar % deducible = gravados / (gravados + excluidos)
  └── Excluir mandatos/peajes del IVA descontable
       │
       ▼
PostgreSQL
  └── INSERT facturas ON CONFLICT (cufe) DO NOTHING
       │
       ▼
Export Excel (openpyxl)
  ├── Hoja BASE_DATOS
  ├── Hoja VALIDACION (celdas coloreadas)
  └── Hoja PRORRATEO_IVA
```

---

## PWA

`taxops-web/public/manifest.json`:

```json
{
  "name": "TaxOps · Automatización Contable Colombia",
  "short_name": "TaxOps",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#1A3A5C",
  "theme_color": "#1A3A5C",
  "shortcuts": [
    { "name": "Nómina", "url": "/nomina" },
    { "name": "Calendario DIAN", "url": "/calendario" }
  ]
}
```

Iconos pendientes: `/public/icons/icon-192.png` y `icon-512.png`.

---

## Configuración Docker

### `docker-compose.yml` — servicios

| Servicio | Imagen | Puerto | Health check |
|----------|--------|--------|--------------|
| `db` | postgres:16 | 5432 | `pg_isready` |
| `adminer` | adminer | 8080 | — |
| `api` | `./api/Dockerfile-api` | 8000 | `GET /health` |
| `web` | `./taxops-web/Dockerfile` | 3000 | `GET /` |

`web` espera a que `api` esté healthy antes de arrancar (`depends_on: condition: service_healthy`).

### Build args (web)

```yaml
args:
  NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
```

`NEXT_PUBLIC_API_URL` se bake en el build de Next.js (variable pública). `INTERNAL_API_URL` se pasa como variable de entorno en runtime para Server Components.

---

## Consideraciones de seguridad

| Área | Medida |
|------|--------|
| Contraseñas | bcrypt (factor 12) — nunca en texto plano |
| Tokens JWT | Firmados con `SECRET_KEY` (mín. 32 chars, HS256) |
| Cookies | `httpOnly`, `Secure` en producción, `SameSite=Lax` |
| CORS | Orígenes explícitos (`ALLOWED_ORIGINS` en config) |
| SQL | SQLAlchemy ORM — sin SQL crudo, sin riesgo de injection |
| Uploads | Validación de tipo MIME + extensión, tamaño limitado |
| Secrets | Nunca en código — `.env` en `.gitignore` |
| Adminer | Solo en Docker local, no expuesto en producción |
