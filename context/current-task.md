# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-16 · **Por:** Claude Code (conector DIAN descartado; ver decisions.md)

---

## Tarea activa

**Ninguna tarea de código en curso.** El conector DIAN quedó **descartado** (2026-09-16, ver
`context/decisions.md`): el cliente entrega el paquete de facturas y TaxOps lo procesa, como hoy.

Lo que sigue en orden:
1. **Validar la Fase 1 (AttachedDocument) con XML reales de la DIAN** — sigue pendiente de que Jaime
   consiga 2–3 archivos. Hasta entonces el parser no se considera productivo.
2. Fase C del frontend solo si al usar #54 en prod aparece algo mal (revisar `/facturas`, `/chatbot`).

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
