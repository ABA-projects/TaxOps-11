# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-30 · **Por:** Claude Code (puesta al día: 13 días sin actualizar la seña)

---

## Tarea activa

**Ninguna tarea de código en curso.** `main` @ `2186643`, 0 PRs abiertos, producción verde.

> ⚠️ Esta seña estuvo **13 días desactualizada** (16 → 30 sep). En ese hueco entró la migración
> de cuenta AWS (#57), que es el cambio más grande del proyecto desde la migración a AWS. Quien
> trabaje —Claude o Kiro— actualiza este archivo al terminar; si no, el otro agente arranca ciego.

**Lo que pasó mientras tanto (reconstruido de git + GitHub + producción, 2026-09-30):**

- **#56** — fix del re-deploy con tag inmutable de ECR. Mergeado.
- **#57 — migración a cuenta AWS dedicada `taxops` (562548008942)**, saliendo de `786567028012`.
  Plan completo en `PLAN-MIGRACION-CUENTA.md` (raíz del repo, 508 líneas, 8 fases).
  `terraform-apply` en verde. Producción confirmada hoy: `api.taxopsapp.com/health` → 200,
  `app.taxopsapp.com` → 200, DNS del API en el CloudFront nuevo (`dsu87dwerxsuj.cloudfront.net`).
- **#58** — `psycopg` v3 para alembic/SQLAlchemy; arregló el `Deploy to Lambda` que falló en #57.

**OIDC mínimo privilegio — VERIFICACIÓN CERRADA** (quedó pendiente el 16 sep, hoy confirmada):
los tres roles corrieron en verde contra la cuenta nueva — `Terraform Plan` (rol plan, 28 sep),
`Terraform Apply` (rol terraform) y `Deploy to Lambda` sobre `2186643` (rol deploy, cierra
`lambda:UpdateFunctionCode`). Variables de GitHub ya apuntan a `562548008942`.
El módulo sobrevivió la migración sin tocarse porque usa `data.aws_caller_identity`.

**Lo único sin verificar — Fase 8 de la migración:** si la infra vieja en `786567028012` se
destruyó. No pude comprobarlo: las sesiones SSO de los perfiles `taxops` y `taxops-admin` están
vencidas. **Importa por la premisa "todo gratis"**: CloudFront, Lambda, Amplify y buckets vivos
en la cuenta vieja siguen consumiendo capa gratuita o generando cargo. Para comprobarlo:
`aws sso login --profile taxops-admin` y revisar CloudFront/Lambda/Amplify/S3 en esa cuenta.

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
