# Discovery: Migración TaxOps-11 a AWS

**Fecha:** 2026-08-05
**Objetivo:** Mover el stack productivo de TaxOps-11 a AWS, maximizando la capa gratuita el primer año, con Terraform como IaC, y dejando una ruta de escalamiento cuando el producto empiece a facturar.

## 0. Aviso: la documentación de despliegue en `docs/` está desactualizada

Este repo tiene tres narrativas de despliegue distintas y solo una es real hoy:

| Fuente | Dice | ¿Vigente? |
|---|---|---|
| `README.md`, `taxops-web/.env.local` | Cloud Run + Vercel | ✅ **Sí — confirmado por la URL real en `.env.local`** |
| `CLAUDE.md`, `taxops-web/.env.local.example` | Render (API) + Railway (redeploy) | ❌ Vestigio de una iteración anterior |
| `docs/AWS_HOSTING_GUIDE.md` | Lightsail/EC2 manual para la app Streamlit legacy | ❌ Predata la arquitectura FastAPI/Next.js actual |
| `.github/workflows/ci.yml` / `deploy.yml` | Sugieren gate de Railway | ❌ Son `workflow_dispatch` manual, no corren automáticamente |

El único pipeline automático real es `.github/workflows/deploy-cloud-run.yml` (`on: push: branches: [main]`).

**Este documento describe el estado real (Cloud Run + Vercel), no lo que dicen los docs viejos.**

## 1. Arquitectura actual

| Capa | Tecnología | Dónde corre |
|---|---|---|
| API | FastAPI 0.115 · Python 3.12 · Uvicorn | Cloud Run (`us-central1`), `--memory 2Gi --cpu 1 --max-instances 1`, scale-to-zero |
| Frontend | Next.js 15.3 (App Router) · React 19 · Tailwind | Vercel |
| Base de datos | PostgreSQL 16 en **Neon** (serverless, externo a GCP) | Neon (SaaS) |
| Storage de documentos (Renta) | Google Cloud Storage, bucket `GCS_BUCKET` (default `taxops-docs`) | GCP |
| IA / Chatbot | Groq API, modelo `llama-3.3-70b-versatile` | SaaS externo |
| Auth | JWT (access 30min / refresh 7d) + Google OAuth | En la propia API |
| CI/CD | GitHub Actions → build Docker (`api/Dockerfile-api`) → Artifact Registry → `gcloud run deploy` | GitHub Actions |

App legacy Streamlit (`Home.py`, `app.py`, root `Dockerfile`) sigue en el repo pero **no es parte del stack productivo** — no se migra.

## 2. Jobs en background — el hallazgo más importante

**Corrección (2026-08-08, verificado leyendo el código real, no solo el discovery original):** el bug de estado en memoria vive en `api/routers/renta_documentos.py` (dict `_jobs`) + `services/renta/job_processor.py` (dict `in_memory_jobs`), ambos con `ThreadPoolExecutor` y un endpoint de status polleado cada 2s por el frontend. `api/routers/exogenas.py` tiene un dict `_pending` distinto — es un stream SSE (`GET /exogenas/stream/{job_id}`) consumido sincrónicamente dentro de la misma request, no un job persistente pollable; no aplica el mismo arreglo. Ya corregido en `job_store.py` (Chunk 2, Task 2.3).

**Esto ya es fràgil hoy**, no solo un problema de migración: si Cloud Run recicla la instancia (`--max-instances 1` la protege parcialmente, pero un cold restart igual borra el estado), el usuario pierde el job. No sobrevive a redeploys ni a más de 1 instancia.

→ La migración es la oportunidad de arreglarlo de raíz con primitivas administradas (ver plan de migración, Chunk 2).

## 3. Base de datos y schema

- Alembic (`api/alembic/versions/`) corre `upgrade head` **en un thread de background al arrancar la API** (`api/main.py:31-56`) — no bloqueante, pero puede haber condiciones de carrera si dos instancias arrancan a la vez.
- `db/init.sql` define **16 tablas** (multi-tenant, `org_id`, PKs UUID, soft-delete): `organizations, users, clients, invoices, processing_sessions, autorretenedores, ingresos_prorateo, exogenas_results, groups, user_groups, audit_logs, contribuyentes, renta_documentos, renta_declaraciones, reglas_tributarias, renta_jobs`.
- Parece duplicar/predatar las migraciones Alembic — revisar cuál es la fuente de verdad antes de tocar el schema.

## 4. Secretos y variables de entorno

| Categoría | Variables |
|---|---|
| DB | `DATABASE_URL` (Neon) |
| IA | `GROQ_API_KEY` (activa); `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY` definidas en código pero sin usar hoy |
| Auth | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `TAXOPS_SUPERADMIN_EMAILS`, `BOOTSTRAP_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| Storage | `GCS_BUCKET` (a reemplazar por bucket S3) |
| Frontend | `NEXT_PUBLIC_API_URL`, `INTERNAL_API_URL` |
| CORS | `ALLOWED_ORIGINS` |

No hay integración de email ni de pagos todavía (roadmap del README las marca como pendientes).

## 5. Tráfico y escala actual

`docs/GCP_MONITORING.md`: uso estimado "laboral (9am-6pm), ~50 usuarios/día", costo actual **< $1/mes** en GCP. Es un piloto de bajo tráfico, no un sistema con carga real todavía — esto es clave para las decisiones de arquitectura (ver plan).

## 6. Restricciones técnicas para la migración

1. **Estado de jobs en memoria + `/tmp` efímero** → incompatible con Lambda o cualquier setup multi-instancia sin cola/estado externo (SQS + DynamoDB resuelve esto).
2. **Imagen con dependencias de sistema pesadas**: Tesseract OCR, WeasyPrint, Cairo, Pango (`api/Dockerfile-api`) → necesita imagen de contenedor custom (Lambda container image lo soporta, hasta 10GB).
3. **Jobs largos**: hasta 90s/archivo, timeout total 600s en Cloud Run → cabe dentro del límite de 15 min de Lambda, pero hay que dimensionar memoria/timeout con margen.
4. **Migraciones Alembic al arrancar** → hay que desacoplarlas del arranque del compute en el nuevo diseño (correrlas como paso de deploy, no en background thread).
5. **Storage acoplado a GCS** (`services/renta/storage.py` llama al SDK de GCS directo, sin capa de abstracción) → cambio de código puntual y acotado para usar S3 (boto3).
6. **CI/CD específico de Cloud Run** (`--set-env-vars` con delimitador custom `^|^`, healthcheck `/health`) → se reescribe para AWS, no es un bloqueo de código.

## 7. Qué NO se migra / se deja igual (decisión de alcance)

| Componente | Decisión | Por qué |
|---|---|---|
| Base de datos (Neon) | **Se queda en Neon** | Evita VPC + NAT Gateway (~$32/mes) o exponer la DB públicamente — ver `MIGRACION-AWS-CASE-STUDY.md` para el detalle de costo |
| Groq API | Se queda externo | Es SaaS, no depende de la nube donde corra el compute |
| App Streamlit legacy | No se migra | No es el stack productivo actual |
