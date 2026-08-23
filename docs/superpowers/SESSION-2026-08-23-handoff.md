# Handoff — sesión 2026-08-20/23 (migración AWS + agentes contables)

Este documento existe porque el proyecto se movió de ruta a mitad de sesión:

- **Ruta vieja**: `/Users/jaime.henao/arheanja/personal-projects/ABA-Projects/repo-andres/TaxOps-11` (ya no existe)
- **Ruta nueva**: `/Users/jaime.henao/arheanja/Personal-enterprise/ABA-Projects/repo-andres/TaxOps-11`

El worktree (`.claude/worktrees/s3-presign-uploads-2`) se movió junto con todo lo demás y quedó
con el link interno de git roto (`git worktree list` lo marcaba `prunable`, apuntando a la ruta
vieja) — se reparó con `git worktree repair <ruta-nueva-del-worktree>` desde el repo principal.
Si en algún momento vuelve a aparecer `prunable`, ese es el fix.

## Estado de producción (todo verificado funcionando al 2026-08-23)

- **API**: AWS Lambda + CloudFront (`api.taxopsapp.com`).
- **Frontend**: AWS Amplify (`app.taxopsapp.com`).
- **Vercel**: decommissioned — proyecto borrado del dashboard, sin referencias en código/docs.
- Migración S3 presign + Exógenas async: **completa y verificada con archivos reales** (31 certificados Exógenas procesados OK, 30 facturas procesadas OK tras el fix de timeout de CloudFront).
- Chatbot: funcionando (modelos de Groq actualizados, los viejos `llama-3.x` fueron deprecados por Groq).

## PRs mergeados esta sesión (orden cronológico, todos en `main`)

| PR | Qué |
|---|---|
| #23 | S3 presigned uploads + Exógenas async (el trabajo original de la migración) |
| #25 | Decommission de Vercel (CORS/config) |
| #26 | Fix CloudFront no reenviaba `Authorization` en GET (rompió el polling de Exógenas) |
| #27 | **Hotfix urgente** — el fix del #26 (`Managed-AllViewer`) tumbó TODA la API (login incluido) por reenviar el header `Host`; corregido con `Managed-AllViewerExceptHostHeader` |
| #28 | Limpieza final de Vercel (`vercel.json` + docs) |
| #29 | Fix 504 en `/invoices/process` con lotes grandes — CloudFront cortaba a los 30s, el Lambda tardaba 38s (`origin_read_timeout` 30→60) |
| #30 | Fix chatbot — Groq deprecó `llama-3.3-70b-versatile`/`llama-3.1-8b-instant`, reemplazados por `openai/gpt-oss-120b`/`openai/gpt-oss-20b` |
| #31 | Spec (docs) — integración de agentes contables existentes a TaxOps |

## Lo que sigue — PR abierto ahora mismo

**PR #32** (https://github.com/ABA-projects/TaxOps-11/pull/32): plan de implementación (11 tasks,
TDD) del spec del #31 — `docs/superpowers/plans/2026-08-23-agentes-contables-integracion.md`.
Todavía **no mergeado, sin código escrito**. Cuando se retome:

1. Revisar/mergear el PR #32 (solo docs).
2. Elegir modo de ejecución del plan: **inline** (recomendado — hoy tuvimos fricción real con
   `subagent-driven-development` en este mismo repo: worktrees perdidos, subagentes sin acceso a
   `.envrc`/secrets gitignored para correr `terraform plan` confiable) o subagent-driven si se
   prefiere para partes read-only/paralelas sin tocar infra/DB real.
3. Ejecutar las 11 tasks del plan (migración Alembic, `db_publish.py`, migrar `calendario.py` a
   S3, `publish.py` de cada agente, 2 endpoints nuevos, 2 páginas nuevas, workflow de GH Actions
   con cron).

**Importante — bug real que el plan corrige de paso**: `api/routers/calendario.py` guarda el
Calendario DIAN en un archivo local que no sobrevive cold starts de Lambda (bug latente desde la
migración a AWS, no relacionado a agentes). El Task 3 del plan lo migra a S3.

## Backlog de negocio (fuera de alcance técnico, explícitamente diferido)

Ver memoria persistente `taxops11-business-strategy-deferred` — Jaime quiere convertir TaxOps-11
en empresa con su primo contador (socio). Se acordó tratarlo en una sesión aparte, dedicada, con
el primo presente para las implicaciones legales/tributarias de constituir empresa en Colombia.
Recomendación dada: NotebookLM (o Claude Projects) para documentar el proyecto y compartirlo con
el primo sin que tenga que leer código.

## Backlog técnico (fuera de alcance de este plan, anotado para specs futuros)

1. Agente conversacional que dispare/consulte/reintente procesamiento de Facturas/Exógenas/Renta
   desde el chat (general + los 3 widgets flotantes por módulo).
2. Sistema de notificaciones proactivas (email + calendario).
3. Agente nuevo de descarga de facturas desde el portal DIAN (necesita spike de viabilidad
   primero — autenticación con certificado digital/RUT, incierto técnicamente).
4. `agents/empleo/*` — explícitamente fuera de alcance de TaxOps (dominio no relacionado).

## Notas de entorno (sin cambios por la migración de ruta)

- `GH_CONFIG_DIR="$HOME/.config/gh-taxops"` — config aislado de `gh` para este repo, ya
  autenticado como `jaimehenao8126` (dueño real del repo). Usarlo explícito en cada comando `gh`
  — el shell de herramienta no dispara el hook de direnv automáticamente.
- `.envrc` (en la raíz del repo, gitignored) tiene `AWS_PROFILE`, `GH_CONFIG_DIR`,
  `TF_VAR_github_access_token` — cargar con `set -a; source .envrc; set +a` antes de cualquier
  `terraform plan`/`apply` real.
- `infra/environments/prod/terraform.tfvars.secret` (gitignored) — necesario para
  `terraform plan -var-file=terraform.tfvars.secret`; sin esto, terraform muestra diffs falsos
  (SSM params por defecto a `{}`).
- Regla de oro sin cambios: ningún `terraform apply` manual — todo PR → `terraform-plan.yml`
  comenta el plan → merge → aprobación manual en GitHub (`terraform-apply.yml`) → apply.
