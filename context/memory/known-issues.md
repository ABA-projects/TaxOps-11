# Problemas conocidos y soluciones — TaxOps-11

> Memoria compartida. Problemas recurrentes, bugs pendientes y cómo se resolvieron los pasados.
> Política: consolidar, no acumular. Si un problema se resuelve, moverlo a "Resueltos" con el fix.

---

## Bugs pendientes — extractor exógenas

Detalle completo en `CLAUDE.md` §"Bugs pendientes — extractor exógenas". Resumen:

1. Imágenes JPEG baja calidad → "No se encontraron montos" (falta preprocesamiento OCR).
2. PDF minimalista no reconocido → sin montos.
3. ICA: fecha parseada como base (`IND FANTASIA ICA`).
4. `LEAM SAS` → retención mal capturada (validar `r/b > 0.001`).
5. `EL BUCANERO RTE IVA` → razón social vacía (SAP bilingüe IVA ≠ layout renta).
6. `COMERTEX` → NIT vs. cédula mal clasificado.

## Problemas de entorno / operación (del handoff)

- **Worktree con link git roto** tras mover la ruta del repo: `git worktree list` marca `prunable`.
  Fix: `git worktree repair <ruta-nueva-del-worktree>` desde el repo principal.
- **`gh` necesita config aislado**: `GH_CONFIG_DIR="$HOME/.config/gh-taxops"`, autenticado como `jaimehenao8126`.
  El shell de herramienta no dispara direnv automáticamente — usar el env var explícito.
- **Terraform necesita secretos locales**: `set -a; source .envrc; set +a` y
  `-var-file=terraform.tfvars.secret`; sin esto Terraform muestra diffs falsos (SSM params → `{}`).

## Claims falsos en la landing — RESUELTO (2026-09-09)

Corregidos en `taxops-web/app/page.tsx` (verificado con tsc/lint/build). Se eliminaron los
testimonios inventados, el "SLA 99.9%", la feature "Funciona Sin Internet" y las cifras
"+500 facturas / 100% datos en tu servidor"; se reemplazaron por capacidades y datos verificables
(3.286 autorretenedores, Art. 490, dedup por CUFE, validación de cuadre). Detalle: `changelog.md`.
Pendiente aparte (no es claim falso): rediseño visual "dirección C" — ver `current-task.md`.

## Deuda técnica menor

- No existe `.dockerignore` — `COPY agents/` podría arrastrar basura en builds locales.
- Lección transversal (se repitió 8 veces en los PRs #36–#44 de agentes): **local no predice
  producción** — aplicó al Dockerfile, dependencias, trigger de deploy, filesystem read-only y al
  `sys.path` de pytest.

## Resueltos (histórico relevante)

- **CloudFront no reenviaba `Authorization` en GET** → rompía polling de Exógenas. Fix vía `Managed-AllViewerExceptHostHeader` (reenviar `Host` tumbaba toda la API). PRs #26/#27.
- **504 en `/invoices/process` con lotes grandes** → CloudFront cortaba a 30s, Lambda tardaba 38s. Fix: `origin_read_timeout` 30→60. PR #29.
- **Groq deprecó `llama-3.x`** → reemplazados por `gpt-oss-120b`/`gpt-oss-20b`. PR #30.
- **Calendario DIAN no sobrevivía cold starts** (archivo local en Lambda) → migrado a S3.
