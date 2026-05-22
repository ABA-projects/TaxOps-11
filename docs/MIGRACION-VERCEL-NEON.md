# Migración: Railway → Vercel + Neon + Railway

Guía para mover el stack de TaxOps a una arquitectura híbrida gratuita/económica:

| Capa | Antes | Después |
|------|-------|---------|
| Frontend (Next.js) | Railway Web | **Vercel** (gratis) |
| Backend (FastAPI) | Railway API | **Railway** (o Render como fallback) |
| Base de datos | Railway PostgreSQL | **Neon** (ya configurado) |

---

## 1. Base de datos — Neon

Ya tienes Neon configurado. Solo necesitas la `DATABASE_URL` en formato:

```
postgresql://user:password@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
```

Pégala como `DATABASE_URL` en las env vars del API (Railway o Render).

---

## 2. Backend FastAPI — Railway

El API de Railway sigue igual. Solo cambia la variable `DATABASE_URL` para apuntar a Neon en lugar del PostgreSQL interno de Railway.

### Env vars requeridas en Railway (servicio API)

```
DATABASE_URL=postgresql://...neon.tech/...?sslmode=require
SECRET_KEY=<tu secret key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
FRONTEND_URL=https://tu-app.vercel.app
GOOGLE_CLIENT_ID=<tu client id>
GOOGLE_CLIENT_SECRET=<tu client secret>
TAXOPS_SUPERADMIN_EMAILS=jaimehenao8126@outlook.com,felipe.arbe08@gmail.com
```

### Fallback: Render

Si el trial de Railway expira definitivamente:

1. Crear cuenta en [render.com](https://render.com)
2. New → Web Service → conectar repo
3. Root directory: `api/`
4. Runtime: Python 3.11
5. Build command: `pip install -r requirements.txt`
6. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Pegar las mismas env vars

**Nota:** Render free duerme el servicio tras 15 min de inactividad. El primer request tarda ~30s en despertar.

---

## 3. Frontend Next.js — Vercel

### Pasos

1. Entrar a [vercel.com](https://vercel.com) → Add New Project
2. Importar el repositorio `proyecto-facturas`
3. Configurar:
   - **Framework Preset**: Next.js
   - **Root Directory**: `taxops-web`
   - **Build Command**: `npm run build` (default)
   - **Output Directory**: `.next` (default)

### Env vars requeridas en Vercel

```
NEXT_PUBLIC_API_URL=https://proyecto-facturas-production.up.railway.app
NEXTAUTH_SECRET=<mismo valor que SECRET_KEY del API>
```

> `INTERNAL_API_URL` no aplica en Vercel (es para red interna de Railway).
> El `next.config.ts` ya tiene el fallback a `NEXT_PUBLIC_API_URL` automáticamente.

### Dominio personalizado

En Vercel → Settings → Domains → agregar dominio propio si tienes uno.

---

## 4. Google OAuth — actualizar URLs

Cuando el frontend cambie de Railway a Vercel, actualizar en Google Cloud Console:

- **Authorized JavaScript origins**: agregar `https://tu-app.vercel.app`
- **Authorized redirect URIs**: agregar `https://proyecto-facturas-production.up.railway.app/auth/google/callback`

El callback siempre va al API (Railway), no al frontend.

---

## 5. Variables de entorno — resumen completo

### Vercel (Next.js)

| Variable | Valor |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | URL pública del API en Railway/Render |

### Railway / Render (FastAPI)

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Connection string de Neon |
| `SECRET_KEY` | Clave secreta para JWT |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `FRONTEND_URL` | URL del frontend en Vercel |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `TAXOPS_SUPERADMIN_EMAILS` | Emails separados por coma |

---

## 6. Checklist de migración

- [ ] Exportar datos de Railway PostgreSQL (si hay datos de producción)
- [ ] Importar datos a Neon
- [ ] Actualizar `DATABASE_URL` en Railway API → apuntar a Neon
- [ ] Verificar que el API responde en Railway
- [ ] Crear proyecto en Vercel con root `taxops-web/`
- [ ] Configurar `NEXT_PUBLIC_API_URL` en Vercel
- [ ] Actualizar `FRONTEND_URL` en Railway API → URL de Vercel
- [ ] Actualizar Google OAuth redirect URIs
- [ ] Probar login, Google OAuth, y panel de admin
- [ ] Apagar servicio Web de Railway (ya no se necesita)
