# Convenciones y contexto operativo — TaxOps-11

> Memoria compartida. Comandos clave, reglas operativas y convenciones.
> El detalle exhaustivo de comandos vive en `CLAUDE.md` §Commands — aquí solo lo de uso frecuente y las reglas de oro.

---

## Comandos frecuentes

```bash
# API local
cd api && uvicorn main:app --reload --port 8000     # docs: http://localhost:8000/docs
# Frontend
cd taxops-web && npm run dev                          # http://localhost:3000
# Tests
python -m pytest
# Lint (igual que CI)
flake8 api/ pipeline/ services/ --max-line-length=120 --exclude=__pycache__,.mypy_cache
cd taxops-web && npx tsc --noEmit
```

## Reglas de oro (no negociables)

- **Infra por PR, nunca `apply` manual**: cambio en `infra/` → PR (`terraform-plan.yml` comenta el plan) → merge a `main` → aprobación manual (GitHub environment `production`) → `terraform-apply.yml`. Única excepción: bootstrap inicial.
- **Costo: "todo gratis, siempre"** — evaluar cada recurso AWS nuevo por capa gratuita.
- **Tagging automático** heredado de `default_tags` en los providers de Terraform. Excepción: recursos auto-creados (p. ej. CloudWatch Log Groups de Lambdas nuevas) → declararlos explícitos en el mismo PR.
- **Deploy de código y de infra están separados** (`lifecycle.ignore_changes = [image_uri]` evita que se pisen).

## Convenciones

- PRs con conventional commits: `feat:`, `fix:`, `chore:`, `docs:`.
- Lint en verde es requisito de CI (flake8 + ESLint + tsc).
- Nuevo código de lógica → test en el mismo cambio.

## Entornos

- **Local/demo**: sin `DATABASE_URL` → sin auth (Streamlit legacy).
- **SaaS**: con `DATABASE_URL` → auth JWT obligatoria. FastAPI siempre requiere auth.
- Producción: API en Lambda+CloudFront, front en Amplify, DB en Neon.

## Dónde viven los secretos (NUNCA copiarlos al contexto compartido)

- Local: `.envrc` (gitignored) — `AWS_PROFILE`, `GH_CONFIG_DIR`, `TF_VAR_github_access_token`.
- Terraform: `infra/environments/prod/terraform.tfvars.secret` (gitignored).
- Producción: SSM Parameter Store (SecureString).
- App local: `api/.env` (gitignored, ver `api/.env.example`).
