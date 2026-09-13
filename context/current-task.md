# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-13 · **Por:** Kiro CLI (EOL Node 20 CERRADO; #48/#49 mergeados)

---

## Tarea activa

**Ninguna tarea de código a medias.** El EOL de Node 20 quedó **cerrado end-to-end**:
- **PR #48** (app: `.nvmrc`=22 + `engines.node>=22`) — MERGED (`1726294`).
- **PR #49** (infra: `build_spec` Amplify con `nvm use 22`) — MERGED (`206b35c`); **Terraform Apply completó con success** → Node 22 aplicado en el compute SSR de producción.

### Diagnóstico del EOL (verificado, resuelto)
- Nuestras Lambdas son `package_type = "Image"` (Python) → no afectadas.
- El aviso era del compute SSR de Amplify (`WEB_COMPUTE` + `Next.js - SSR`). Node 20 EOL 2026-04-30; corte de deploys 2027-03-03. Migrado a Node 22 (LTS, compatible Next 15.3).

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

## Notas de handoff

- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
- Los commits van firmados solo por Jaime — sin `Co-Authored-By`.
