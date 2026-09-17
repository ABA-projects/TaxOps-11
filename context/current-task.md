# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-16 · **Por:** Claude Code (OIDC mínimo privilegio aplicado; PR #56 abierto)

---

## Tarea activa

**OIDC de GitHub Actions con mínimo privilegio — aplicado, falta cerrar la verificación.**

- PR #55 mergeado y **aplicado** (gate aprobado). Tres roles: `taxops-github-actions-plan`
  (pull_request, ReadOnly + lock + kms:Decrypt vía SSM), `-terraform` (environment production,
  PowerUser + IAM acotado a `taxops-*`), `-deploy` (main, ECR + UpdateFunctionCode + S3 config/*).
- Variables de GitHub creadas: `AWS_PLAN_ROLE_ARN`, `AWS_DEPLOY_ROLE_ARN`.
- Verificado con el rol de deploy: login + push a ECR. **NO verificado aún**: `lambda:UpdateFunctionCode`
  (la prueba manual chocó con el tag inmutable de ECR, no con permisos) y el rol de plan.
- **PR #56 abierto** (fix: `workflow_dispatch` de deploy-lambda re-usa la imagen si el tag existe).
  Al mergearlo, el push a main ejercita el deploy completo con el rol nuevo → mirar que quede en verde.
  El primer PR que toque `infra/` ejercita el rol de plan.

Si algo falla será un `AccessDenied` explícito en el log; se corrige agregando la acción en
`infra/modules/github-oidc/main.tf` por el pipeline normal. Producción no se afecta.

## Pendiente

- **Rediseño frontend — Fases A y B HECHAS y mergeadas** (PR #53 landing editorial clara,
  PR #54 tokens de la app: verde, neutros de papel, Fraunces/Source Sans 3/JetBrains Mono).
  Calendario de la landing ya se lee del JSON con ISR diario (deuda pagada).
  **Fase C pendiente (solo si hace falta)**: pulido por página tras ver #54 en prod —
  revisar primero `/facturas` y `/chatbot` (más usos de `gray-*`). Deudas menores: renombrar
  `brand.orange`→`brand.green` (nombre engañoso a propósito, ~120 usos); el formulario de
  contacto de la landing es un `mailto:` sin backend; no se verificó en navegador (Chrome falló).
- **Discovery DIAN/XML — CERRADO (2026-09-10).** Veredicto: tratar el XML como fuente primaria está
  bien fundado legalmente (Res. 000165/2023 Art. 66: el XML tiene valor legal, el PDF es opcional).
  **Gap real:** `extract_xml` parsea UBL plano pero NO desenvuelve el `AttachedDocument` (contenedor
  con la factura en CDATA) que la DIAN entrega predominantemente. Síntesis + recomendación:
  `context/memory/discovery-dian-xml.md`; research crudo con fuentes: `docs/research/dian-xml/FINDINGS.md`.
  **Fase 1 HECHA y mergeada** (PR #50, `ac3ec14`). Queda la deuda de validarla contra 2-3
  AttachedDocument REALES — Jaime los consigue el lunes 2026-09-15. Exógenas/renta en XML = Fase 2,
  sigue diferida (el research la marca como dudosa: esos documentos llegan en PDF).

## Notas de handoff

- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
- Los commits van firmados solo por Jaime — sin `Co-Authored-By`.
