# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-10 · **Por:** Kiro CLI (EOL Node 20 → PRs #48/#49)

---

## Tarea activa

**Ninguna tarea de código a medias.** El aviso de Lambda Node.js 20.x EOL quedó abordado en dos PRs
(pendientes de merge):

- **PR #48** (`chore/frontend-node22`) — capa de app: `taxops-web/.nvmrc` = 22 + `engines.node>=22`. Verificado con lint+build en Node 22.
- **PR #49** (`chore/amplify-ssr-node22`) — capa de infra: `build_spec` con `nvm use 22` para el compute SSR. **Va por el flujo Terraform** (plan en el PR → aprobación manual → apply). `terraform fmt` limpio.

### Diagnóstico del EOL (verificado, no asumido)
- Nuestras Lambdas son `package_type = "Image"` (Python) → **no afectadas** (no hay `runtime =` en todo `infra/`).
- El aviso es del **compute SSR de Amplify** (`WEB_COMPUTE` + `Next.js - SSR`), runtime Node gestionado por AWS.
- Node 20 EOL: 2026-04-30 · Amplify corta deploys con Node 20 el **2027-03-03** · Amplify NO migra solo (repost.aws). Soporta 20/22/24 → se eligió 22 (LTS, compatible Next 15.3).

## Pendiente

- **Rediseño visual dirección C ("Herramienta")** — es trabajo de **Claude** (los fuentes se recuperan
  desde su canvas). Kiro no lo toca. Canvas: https://claude.ai/code/artifact/66cbf36f-054d-478a-a17c-3bb8bfbd4d4b
- **Discovery DIAN/XML — CERRADO (2026-09-10).** Veredicto: tratar el XML como fuente primaria está
  bien fundado legalmente (Res. 000165/2023 Art. 66: el XML tiene valor legal, el PDF es opcional).
  **Gap real:** `extract_xml` parsea UBL plano pero NO desenvuelve el `AttachedDocument` (contenedor
  con la factura en CDATA) que la DIAN entrega predominantemente. Síntesis + recomendación:
  `context/memory/discovery-dian-xml.md`; research crudo con fuentes: `docs/research/dian-xml/FINDINGS.md`.
  **Siguiente paso (si se aprueba):** plan de Fase 1 — soportar AttachedDocument en facturas + capturar
  CUDE/estado de validación, con 2–3 XML reales como fixtures. Exógenas/renta en XML = Fase 2, diferida.
- **EOL Node 20** → abordado en PRs #48/#49 (ver arriba). Cerrar cuando se mergeen.

## Notas de handoff

- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
- Los commits van firmados solo por Jaime — sin `Co-Authored-By`.
