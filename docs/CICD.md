# TaxOps — CI/CD: Análisis y Guía Completa

> Cubre el pipeline completo: GitHub Actions → Docker → Railway.
> Incluye análisis de ArgoCD (por qué no aplica aquí y qué necesitarías si migras a K8s).

---

## 1. Estado actual: qué hay y qué faltaba

### Antes de este documento
```
git push main
    └── Railway detecta el push
        ├── api: docker build -f api/Dockerfile-api .  → deploy directo
        └── web: docker build taxops-web/Dockerfile    → deploy directo
```
**Problema:** Railway deployaba incluso si había errores de TypeScript, tests fallando o código roto. No había gate de calidad.

### Después (pipeline implementado)
```
git push / PR → main
    └── GitHub Actions CI (ci.yml)
        ├── api-lint    (flake8, PEP8)
        ├── api-test    (pytest, sin Postgres real)
        ├── web-lint    (ESLint + tsc --noEmit)
        └── web-build   (next build completo)
            │
            └── [todo pasa] → deploy.yml dispara Railway CLI
                             ├── API service redeploy
                             └── Web service redeploy
```

---

## 2. Arquitectura CI/CD — Diagrama completo

```
┌─────────────────────────────────────────────────────────────────┐
│  DEV LOCAL                                                       │
│                                                                  │
│  docker-compose up -d                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ db:5432  │  │adminer   │  │api:8000  │  │web:3000      │    │
│  │postgres  │  │:8080     │  │FastAPI   │  │Next.js 15    │    │
│  │16-alpine │  │          │  │Uvicorn   │  │standalone    │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└─────────────────────┬───────────────────────────────────────────┘
                      │ git push / PR
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS                                                  │
│                                                                  │
│  .github/workflows/ci.yml                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ api-lint    │  │ api-test    │  │ web-lint + web-build     │ │
│  │ flake8      │  │ pytest      │  │ ESLint, tsc, next build  │ │
│  │ ~1 min      │  │ ~2 min      │  │ ~3 min                   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────────┘ │
│         └────────────────┴──────────────────────┘               │
│                          │ all-checks-pass                       │
│                          ▼                                       │
│  .github/workflows/deploy.yml                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  railway up --service API_ID                            │    │
│  │  railway up --service WEB_ID                            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Railway CLI trigger
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  RAILWAY (PRODUCCIÓN)                                            │
│                                                                  │
│  Proyecto: taxops                                                │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────┐ │
│  │ Service: api      │  │ Service: web      │  │ PostgreSQL  │ │
│  │ Docker build      │  │ Docker build      │  │ Plugin      │ │
│  │ Dockerfile-api    │  │ taxops-web/       │  │ Managed     │ │
│  │ Root: . (repo)    │  │ Dockerfile        │  │             │ │
│  │                   │  │ Root: taxops-web  │  │             │ │
│  │ Puerto: 8000      │  │ Puerto: 3000      │  │ Puerto:5432 │ │
│  │ api.railway.app   │  │ web.railway.app   │  │ (interno)   │ │
│  └───────────────────┘  └───────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Docker — Estrategia de builds

### 3.1 Dockerfile API (`api/Dockerfile-api`)

```dockerfile
FROM python:3.12-slim
# Build context: RAÍZ del repo (no api/)
# Porque necesita: pipeline/, services/, db/, exogenas/
```

| Capa | Qué hace | Caché |
|------|----------|-------|
| `apt-get` libpq-dev, gcc | Deps para psycopg2 + compilación | Raramente cambia |
| `pip install requirements-api.txt` | Deps Python | Cambia si requirements cambia |
| `COPY pipeline/ services/ db/ exogenas/ api/` | Código fuente | Cambia en cada commit |

**Railway config:**
- **Root Directory**: `/` (raíz del repo)
- **Dockerfile Path**: `api/Dockerfile-api`
- **Build Context**: `.` (toda la raíz)

### 3.2 Dockerfile Web (`taxops-web/Dockerfile`)

Multi-stage build — 3 etapas:

```
Stage 1: deps (node:20-alpine)
  └── npm ci → node_modules

Stage 2: builder (node:20-alpine)
  ├── COPY node_modules
  ├── COPY src
  └── npm run build → .next/standalone

Stage 3: runner (node:20-alpine, ~120MB final)
  ├── user nextjs (no root)
  ├── COPY .next/standalone → /app
  └── node server.js
```

**Variable crítica en build:**
```
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
```
Esta variable se "hornea" en el bundle en tiempo de build. Si cambias la URL de la API en Railway, debes **rebuild** del servicio web, no solo restart.

**Railway config:**
- **Root Directory**: `taxops-web`
- **Dockerfile Path**: `Dockerfile` (relativo a taxops-web/)
- **Build Args**: `NEXT_PUBLIC_API_URL=https://tu-api.railway.app`

### 3.3 Docker Compose (solo local)

```yaml
# NO se usa en Railway. Railway construye cada servicio por separado.
services:
  db       → postgres:16-alpine (Railway usa su plugin Postgres)
  adminer  → solo local, NO deployar en producción
  api      → build: context=., dockerfile=api/Dockerfile-api
  web      → build: context=taxops-web/, dockerfile=Dockerfile
```

**Comandos frecuentes:**
```bash
# Rebuild completo (cuando cambian dependencias)
docker compose build --no-cache api web

# Rebuild parcial (solo código)
docker compose build api && docker compose up -d api

# Ver logs en tiempo real
docker compose logs -f api web

# Entrar al contenedor de la API
docker compose exec api bash

# Limpiar todo (cuidado: borra datos locales)
docker compose down -v
```

---

## 4. Railway — Configuración completa

### 4.1 Servicios que necesitas crear

En railway.app > New Project > Empty Project, crear 3 servicios:

```
Proyecto: taxops
├── taxops-db       ← Plugin PostgreSQL (no Docker)
├── taxops-api      ← GitHub Repo, Dockerfile
└── taxops-web      ← GitHub Repo, Dockerfile
```

### 4.2 Service: taxops-db (PostgreSQL)

1. `+ New` → **Database** → **PostgreSQL**
2. Railway crea automáticamente `DATABASE_URL` (con formato `postgresql://...`)
3. En el servicio `api`, referencia con: `${{taxops-db.DATABASE_URL}}`

### 4.3 Service: taxops-api

| Setting | Valor |
|---------|-------|
| Source | GitHub repo → `ABA-projects/proyecto-facturas` |
| Branch | `main` |
| Root Directory | `/` ← raíz del repo |
| Build Command | *(vacío, usa Dockerfile)* |
| Dockerfile Path | `api/Dockerfile-api` |
| Start Command | *(vacío, usa CMD del Dockerfile)* |

**Variables de entorno (en Railway dashboard → api → Variables):**

```bash
DATABASE_URL          = ${{taxops-db.DATABASE_URL}}   # Referencia al plugin
SECRET_KEY            = <genera uno con: openssl rand -hex 32>
ALGORITHM             = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS   = 7
ALLOWED_ORIGINS       = https://<tu-dominio-web>.railway.app,https://tudominio.com
GROQ_API_KEY          = gsk_xxxxxxxxxxxxx
TAXOPS_SUPERADMIN_EMAILS = tu@email.com
```

**Puerto:** Railway detecta el `EXPOSE 8000` del Dockerfile automáticamente.

### 4.4 Service: taxops-web

| Setting | Valor |
|---------|-------|
| Source | GitHub repo → `ABA-projects/proyecto-facturas` |
| Branch | `main` |
| Root Directory | `taxops-web` |
| Build Command | *(vacío, usa Dockerfile)* |
| Dockerfile Path | `Dockerfile` |

**Variables de entorno:**

```bash
NEXT_PUBLIC_API_URL = https://<taxops-api>.railway.app
INTERNAL_API_URL    = https://<taxops-api>.railway.app
# (En Railway no hay red interna entre servicios sin Railway networking config)
```

**Puerto:** Railway detecta el `EXPOSE 3000` automáticamente.

> **IMPORTANTE:** `NEXT_PUBLIC_API_URL` es una **Build Arg**, no solo una env var runtime.
> Si la cambias en Railway, debes ir a **Settings → Trigger Redeploy** para que se
> hornee en el nuevo bundle de Next.js.

### 4.5 Por qué no ves los cambios en Railway

Causa más común: Railway redeploya automáticamente al push, pero el **nuevo bundle
del frontend está usando la URL de API incorrecta** (hardcodeada en el build anterior).

**Checklist cuando no ves cambios:**

```
1. Railway dashboard → servicio → Deployments
   ¿El último deploy tiene EXIT CODE 0? → Si no, es un error de build

2. ¿El build de Next.js terminó con éxito?
   Logs del deploy → busca "✓ Compiled successfully"

3. ¿NEXT_PUBLIC_API_URL apunta a la API correcta?
   En Variables → verifica que sea https://... (no http://localhost:8000)

4. ¿La API está healthy?
   Abre https://<taxops-api>.railway.app/health → debe devolver {"status":"ok"}

5. Hard refresh no es suficiente para Next.js standalone:
   Necesitas redeploy completo, no solo cache del navegador.

6. ¿Hiciste cambios en variables de entorno?
   Railway hace redeploy automático al guardar variables → espera ~2 min
```

### 4.6 Dominios y networking

```
Dominio público:
├── web → taxops-web-production.up.railway.app (generado)
│         o tu dominio personalizado: app.taxops.co
└── api → taxops-api-production.up.railway.app (generado)
          o: api.taxops.co

Comunicación interna (opcional Railway Networking):
  web → api via: https://taxops-api.railway.internal
  Requiere: activar Private Networking en el proyecto
```

---

## 5. GitHub Actions — Workflows implementados

### 5.1 `ci.yml` — Integración continua

```
Trigger: push a main, PR hacia main

Jobs (paralelos):
├── api-lint    → flake8 (PEP8, ~1 min)
├── api-test    → pytest sin Postgres (~2 min)
│                 (test_e2e.py excluido, requiere Postgres)
├── web-lint    → ESLint + tsc --noEmit (~1 min)
└── web-build   → next build completo (~3 min)
    │
    └── all-checks-pass (gate final)
```

**Tiempos estimados:** ~4 min total (paralelo)

### 5.2 `deploy.yml` — Deploy a Railway

```
Trigger: workflow_run[CI] = completed + success + branch main

Requiere GitHub Secrets:
├── RAILWAY_TOKEN              → railway.app → Account → Tokens
├── RAILWAY_SERVICE_API_ID     → ID del servicio API en Railway
└── RAILWAY_SERVICE_WEB_ID     → ID del servicio Web en Railway
```

**Para obtener los IDs del servicio:**
```bash
# Opción 1: Railway CLI
npm install -g @railway/cli
railway login
railway link   # en la carpeta del proyecto
railway status # muestra IDs

# Opción 2: Dashboard
# railway.app → proyecto → servicio → Settings → "Copy Service ID"
```

### 5.3 Configurar Branch Protection en GitHub

1. GitHub → Repo → Settings → Branches → Add rule
2. Branch name pattern: `main`
3. Activar:
   - [x] **Require status checks to pass before merging**
   - [x] Status check: `All checks passed` (el job `all-checks-pass` de ci.yml)
   - [x] **Require branches to be up to date before merging**
   - [x] **Do not allow bypassing the above settings**

---

## 6. ArgoCD — ¿Aplica para TaxOps?

### 6.1 Qué es ArgoCD

ArgoCD es un operador GitOps para **Kubernetes**. Sincroniza el estado declarado en Git
(manifests YAML de K8s) con el cluster. No tiene sentido con Railway porque:

| Característica | Railway | ArgoCD/K8s |
|----------------|---------|------------|
| Infraestructura | PaaS gestionado | Kubernetes propio |
| Deploy | Push a Git → auto | Sync de manifests |
| Escalado | Slider en dashboard | HPA / VPA |
| BD | Plugin gestionado | StatefulSet / RDS |
| Coste base | $5/mes | Cluster K8s (>$50/mes) |
| Complejidad | Baja | Alta |

**Conclusión:** Para el MVP de TaxOps, Railway + GitHub Actions es la stack correcta.
ArgoCD tiene sentido cuando migres a K8s (ej: EKS, GKE) con >5 servicios o necesites
multi-tenant isolation a nivel de namespace.

### 6.2 Cómo sería si migraras a K8s + ArgoCD

Si en el futuro pasas a Kubernetes, la estructura GitOps sería:

```
repo: taxops-gitops/                    (repo separado, solo manifests)
├── apps/
│   ├── api/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   └── web/
│       ├── deployment.yaml
│       └── service.yaml
├── overlays/
│   ├── staging/
│   │   └── kustomization.yaml          (imagen: taxops-api:sha-abc123)
│   └── production/
│       └── kustomization.yaml          (imagen: taxops-api:v1.2.0)
└── argocd/
    ├── app-api.yaml                    (Application CRD)
    └── app-web.yaml

Pipeline K8s:
  git push → GitHub Actions → docker build → push ECR/GHCR
           → PR en taxops-gitops/ actualiza imagen tag
           → ArgoCD detecta diff → sync al cluster
           → Pods rolling update sin downtime
```

El CI/CD de Railway que tienes implementado es equivalente funcionalmente,
pero sin la complejidad de K8s manifests + RBAC + namespaces.

---

## 7. Variables de entorno — Referencia completa

### API (FastAPI)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://taxops:pass@host:5432/taxops` |
| `SECRET_KEY` | JWT signing key (mín. 32 chars) | `openssl rand -hex 32` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración refresh token | `7` |
| `ALLOWED_ORIGINS` | CORS origins (CSV) | `https://app.taxops.co,http://localhost:3000` |
| `GROQ_API_KEY` | Groq LLM API key | `gsk_xxx` |
| `TAXOPS_SUPERADMIN_EMAILS` | Emails con acceso admin | `admin@taxops.co` |

### Web (Next.js)

| Variable | Descripción | Cuándo aplica |
|----------|-------------|---------------|
| `NEXT_PUBLIC_API_URL` | URL pública de la API | **Build time** — requiere rebuild |
| `INTERNAL_API_URL` | URL interna (sin CORS) | Runtime (server components) |

> `NEXT_PUBLIC_*` se embebe en el bundle JavaScript en tiempo de `next build`.
> Las demás variables solo existen en el servidor Node.js de Next.js.

---

## 8. Troubleshooting frecuente

### "Deploy success pero no veo cambios"

```bash
# 1. Verifica que Railway usó el commit correcto
#    Dashboard → Deployments → ver SHA del commit

# 2. La web sigue apuntando a localhost:8000?
#    → NEXT_PUBLIC_API_URL no está configurada en Railway
#    → Configura la variable y Trigger Redeploy

# 3. API devuelve 502?
#    → La API no está healthy. Ver logs del servicio api
#    → Verificar que DATABASE_URL existe y Postgres está up
```

### "El CI falla en api-test pero funciona local"

```bash
# En CI usamos DATABASE_URL=sqlite:///./test.db
# Asegúrate que tus tests no usen PostgreSQL-specific SQL
# (ej: RETURNING, ON CONFLICT, etc. no funcionan en SQLite)

# Para tests que necesiten Postgres real, márcalos:
@pytest.mark.skipif(
    "sqlite" in os.getenv("DATABASE_URL", ""),
    reason="Requires PostgreSQL"
)
```

### "web-build falla en CI pero funciona local"

```bash
# Next.js puede fallar con NEXT_PUBLIC_API_URL vacío en modo strict
# El CI define: NEXT_PUBLIC_API_URL=http://localhost:8000
# Si tu código asume que la URL siempre existe, añade fallback:
# process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
```

### "Railway no dispara deploy al hacer push"

```bash
# Verificar: railway.app → proyecto → servicio → Settings
# → "Source" está conectado al repo correcto?
# → Branch: main?
# → Auto-deploy: On?

# Si prefieres control manual:
# Desactiva Auto-deploy y deja que deploy.yml lo gestione via Railway CLI
```

---

## 9. Roadmap CI/CD

| Fase | Mejora | Cuándo |
|------|--------|--------|
| v1.0 ✅ | CI básico (lint, test, build) | Implementado |
| v1.0 ✅ | Deploy automático a Railway | Implementado |
| v1.1 | E2E tests con Playwright (flujo login → nómina) | Siguiente sprint |
| v1.1 | Staging environment en Railway (branch `develop`) | Siguiente sprint |
| v1.2 | Cache de Docker layers en GitHub Actions | Cuando builds >5 min |
| v1.2 | Notificaciones Slack/Discord en deploys | Cuando hay equipo |
| v2.0 | Migración a K8s + ArgoCD | Cuando >3 tenants activos |
| v2.0 | Blue/Green deploy con Railway volumes | Cuando se necesite 0-downtime garantizado |
