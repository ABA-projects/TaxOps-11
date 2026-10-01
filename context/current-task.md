# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-10-01 · **Por:** Claude Code (costo de Amplify optimizado; nada en vuelo)

---

## Tarea activa

**Ninguna tarea en curso.** `main` @ `008ca4e`, 0 PRs abiertos, producción verde.

Cerrado el 2026-09-30/10-01:
- **Puesta al día** tras 13 días sin actualizar esta seña (entró la migración de cuenta AWS #57).
- **Fase 8 de la migración VERIFICADA**: `786567028012` quedó limpia de TaxOps (todos los
  servicios, 6 regiones). Lo que queda allá es de otros proyectos.
- **Costo de Amplify: de ~US$0,95 a ~US$0,25/mes** (#59 + #60). El webhook reconstruía Next.js
  en cada push a `main` sin filtrar por ruta — era el 80 % del costo. Ahora `enable_auto_build`
  está en `false` y despliega `.github/workflows/deploy-web.yml` con `paths: taxops-web/**`.
  **Probado con evidencia**: el commit `008ca4e` (solo docs) no disparó build.
- **Decidido y registrado** (`decisions.md`): el frontend NO se migra a Cloudflare/Netlify/Vercel.
- OIDC mínimo privilegio: verificación cerrada, los 3 roles en verde contra la cuenta nueva.

## Pendiente

- **Auditoría de free tier a nivel AWS Organization (riesgo de costo abierto).** La capa gratuita
  se agrega por consolidated billing, no por cuenta: lo que consuman `investment-self`, `dianbot`
  y las demás descuenta del mismo 1M de requests de Lambda y 1 TB de CloudFront. "Todo gratis" en
  TaxOps depende de los otros proyectos. Nunca se ha medido.
- **Validar Fase 1 (AttachedDocument) con 2-3 XML reales de la DIAN** — depende de que Jaime los
  consiga. Hasta entonces el parser no se considera productivo (fixtures sintéticos).

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
