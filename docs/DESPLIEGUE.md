# TaxOps — Guía de Despliegue

## Entornos

| Entorno | URL | Stack |
|---------|-----|-------|
| Local | http://localhost:3000 | Docker Compose |
| Producción | Railway | Docker (api + web + postgres) |

---

## 1. Despliegue local (Docker Compose)

### Prerrequisitos

- Docker Desktop ≥ 4.x (incluye Docker Compose v2)
- Git

### Paso 1 — Clonar el repositorio

```bash
git clone <repo-url>
cd proyecto-facturas
```

### Paso 2 — Configurar variables de entorno

```bash
cp api/.env.example api/.env
cp taxops-web/.env.local.example taxops-web/.env.local
```

**Editar `api/.env`:**

```env
# Base de datos (usa el servicio db del docker-compose)
DATABASE_URL=postgresql://taxops:taxops_local_2026@db:5432/taxops

# JWT — generar con: openssl rand -hex 32
SECRET_KEY=tu_secreto_minimo_32_caracteres_aqui

# IA — obtener en console.groq.com (gratis)
GROQ_API_KEY=gsk_tu_clave_groq_aqui

# Opcionales
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Editar `taxops-web/.env.local`:**

```env
# URL de la API (pública para el browser)
NEXT_PUBLIC_API_URL=http://localhost:8000

# URL interna Docker (para Server Components y Next.js API routes)
INTERNAL_API_URL=http://api:8000

# Firma de sesión Next.js — generar con: openssl rand -hex 32
NEXTAUTH_SECRET=otro_secreto_seguro_aqui
```

### Paso 3 — Build y arrancar

```bash
# Primera vez (descarga imágenes base, instala deps): ~3-5 min
docker compose build

# Arrancar todos los servicios en background
docker compose up -d
```

### Paso 4 — Verificar

```bash
# Ver estado de los contenedores
docker compose ps

# Logs de la API
docker compose logs api --tail 20

# Logs del frontend
docker compose logs web --tail 20

# Health checks
curl http://localhost:8000/health          # → {"status":"ok"}
curl -o /dev/null -w "%{http_code}" http://localhost:3000  # → 200
```

### Paso 5 — Crear primer usuario

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@empresa.co",
    "password": "Admin1234!",
    "nombre": "Administrador"
  }'
```

Acceder en: **http://localhost:3000**

### Servicios disponibles

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Frontend | http://localhost:3000 | App Next.js |
| API | http://localhost:8000 | FastAPI |
| Swagger UI | http://localhost:8000/docs | Documentación interactiva |
| ReDoc | http://localhost:8000/redoc | Documentación alternativa |
| Adminer | http://localhost:8080 | Interfaz web PostgreSQL |

**Adminer:**
- Sistema: PostgreSQL
- Servidor: `db`
- Usuario: `taxops`
- Contraseña: `taxops_local_2026`
- BD: `taxops`

### Comandos útiles

```bash
# Parar sin borrar datos
docker compose stop

# Parar y borrar contenedores (datos PostgreSQL persisten en volumen)
docker compose down

# Parar y borrar TODO incluyendo datos
docker compose down -v

# Rebuild de un servicio específico
docker compose build api
docker compose up -d api

# Ver logs en vivo
docker compose logs -f api web
```

---

## 2. Despliegue en Railway

Railway despliega cada commit a `main` automáticamente.

### Arquitectura en Railway

```
Railway Project: taxops
├── Service: postgres     ← Plugin de Railway
├── Service: api          ← Dockerfile api/Dockerfile-api
└── Service: web          ← Dockerfile taxops-web/Dockerfile
```

### Paso 1 — Crear proyecto

1. Ir a [railway.app](https://railway.app) → "New Project"
2. "Deploy from GitHub repo" → autorizar Railway → seleccionar este repo

### Paso 2 — Agregar PostgreSQL

En el proyecto Railway:
1. "+ New" → "Database" → "Add PostgreSQL"
2. Railway crea el plugin y genera `DATABASE_URL` automáticamente

### Paso 3 — Configurar servicio API

En el proyecto, el servicio creado desde el repo:

1. Settings → Build:
   - **Dockerfile Path**: `api/Dockerfile-api`
   - **Build Context**: `/` (raíz del repo)

2. Variables → Add:

| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | Hacer clic en "Link Variable" → Plugin PostgreSQL → `DATABASE_URL` |
| `SECRET_KEY` | Resultado de `openssl rand -hex 32` |
| `GROQ_API_KEY` | Tu API key de [console.groq.com](https://console.groq.com) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` |

3. Settings → Networking:
   - "Generate Domain" → Railway da URL pública ej. `api-taxops.railway.app`

4. Settings → Deploy:
   - Health Check Path: `/health`
   - Restart Policy: On Failure

### Paso 4 — Configurar servicio Web

Crear segundo servicio desde el mismo repo:

1. "+ New" → "GitHub Repo" → mismo repo

2. Settings → Build:
   - **Root Directory**: `taxops-web`
   - **Dockerfile Path**: `Dockerfile` (relativo al root directory)

3. Variables → Add:

| Variable | Valor |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | URL pública del servicio api (ej. `https://api-taxops.railway.app`) |
| `INTERNAL_API_URL` | URL privada Railway del servicio api (ej. `http://api.railway.internal:8000`) |
| `NEXTAUTH_SECRET` | Resultado de `openssl rand -hex 32` |

4. Settings → Networking:
   - "Generate Domain" → ej. `taxops.railway.app`

5. Settings → Deploy:
   - Health Check Path: `/`

### Paso 5 — Primer deploy

```bash
git push origin main
```

Railway detecta el push y hace build de ambos servicios en paralelo. El servicio `web` espera a que `api` esté healthy.

### Paso 6 — Crear usuario en producción

```bash
curl -X POST https://api-taxops.railway.app/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@empresa.co",
    "password": "Admin1234!",
    "nombre": "Administrador"
  }'
```

### Verificar producción

```bash
# API health
curl https://api-taxops.railway.app/health

# Landing page
curl -o /dev/null -w "%{http_code}" https://taxops.railway.app

# PWA manifest
curl https://taxops.railway.app/manifest.json
```

---

## 3. Configuración de dominio personalizado

### Railway

1. Service → Settings → Networking → "Custom Domain"
2. Ingresar dominio (ej. `app.taxops.co` para web, `api.taxops.co` para api)
3. Railway muestra los registros DNS a configurar:
   - CNAME apuntando a `*.railway.app`
4. Configurar en tu proveedor DNS (ej. Cloudflare, GoDaddy)
5. Railway provisiona TLS automáticamente (Let's Encrypt)

### Actualizar variables después del dominio

En el servicio `web`:
```
NEXT_PUBLIC_API_URL=https://api.taxops.co
```

Rebuild del servicio web (la variable se bakea en el build de Next.js).

---

## 4. Variables de entorno — referencia completa

### API

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | ✅ | — | Clave firma JWT (mín. 32 chars) |
| `GROQ_API_KEY` | ✅ | — | API key de console.groq.com |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | TTL access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | TTL refresh token |
| `ALLOWED_ORIGINS` | No | `*` | Orígenes CORS permitidos (separados por coma) |
| `ENVIRONMENT` | No | `development` | `production` activa Secure cookies |

### Frontend (Next.js)

| Variable | Requerida | Build-time | Descripción |
|----------|-----------|------------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | ✅ Sí (baked) | URL pública de la API para el browser |
| `INTERNAL_API_URL` | ✅ | No (runtime) | URL interna para Server Components |
| `NEXTAUTH_SECRET` | ✅ | No (runtime) | Firma de cookies de sesión |

> **Importante:** `NEXT_PUBLIC_*` variables se baked en el build. Cambiarlas requiere rebuild del contenedor web.

---

## 5. Troubleshooting

### Error: "Cannot connect to database"

```bash
# Verificar que la BD está corriendo
docker compose ps db

# Ver logs de PostgreSQL
docker compose logs db --tail 20

# Probar conexión directa
docker compose exec db psql -U taxops -c "SELECT 1;"
```

### Error: "401 Unauthorized" en todos los endpoints

El `SECRET_KEY` de la API no coincide con el usado para firmar los tokens. Asegurarse de que `api/.env` y el servicio Railway tienen el mismo valor.

### El frontend muestra "Failed to fetch"

`NEXT_PUBLIC_API_URL` apunta a la URL incorrecta. Verificar:
```bash
# Local
echo $NEXT_PUBLIC_API_URL   # debe ser http://localhost:8000

# En el browser, abrir DevTools → Network → ver URL de las peticiones
```

### Railway: build falla en el servicio web

Verificar que el **Root Directory** está configurado como `taxops-web` y el Dockerfile path como `Dockerfile` (no `taxops-web/Dockerfile`).

### PDF export devuelve 500

ReportLab no está instalado. Verificar `api/requirements-api.txt`:
```
reportlab>=4.2
```
Rebuild del servicio api:
```bash
docker compose build api && docker compose up -d api
```

### Batch import devuelve "415 Unsupported Media Type"

El frontend debe usar `postForm()` (multipart), no `post()` (JSON). Verificar en `taxops-web/app/(app)/nomina/page.tsx` que `handleBatchFile` usa `postForm`.

### PWA no se instala

Verificar que:
1. El sitio corre sobre HTTPS (requerido para PWA en producción)
2. `/manifest.json` devuelve JSON válido
3. Los iconos `/icons/icon-192.png` y `/icons/icon-512.png` existen en `public/icons/`

---

## 6. Actualizar en producción

### Railway (automático)

```bash
git add .
git commit -m "fix: descripción del cambio"
git push origin main
# Railway detecta el push → rebuild automático → zero-downtime deploy
```

### Local (manual)

```bash
# Solo frontend cambió
docker compose build web && docker compose up -d web

# Solo API cambió
docker compose build api && docker compose up -d api

# Ambos cambiaron
docker compose build web api && docker compose up -d
```

---

## 7. Backups PostgreSQL

### Dump manual

```bash
# Local
docker compose exec db pg_dump -U taxops taxops > backup_$(date +%Y%m%d).sql

# Restaurar
docker compose exec -T db psql -U taxops taxops < backup_20260510.sql
```

### Railway

Railway incluye backups automáticos del plugin PostgreSQL según el plan. También puedes usar el CLI de Railway:

```bash
railway connect postgres
# → abre psql conectado a la BD de Railway
```
