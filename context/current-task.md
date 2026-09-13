# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-13 · **Por:** Claude Code (Fase 1 DIAN/XML — AttachedDocument)

---

## Tarea activa

**Ninguna tarea de código a medias.** La Fase 1 del discovery DIAN/XML quedó **mergeada**
en el **PR #50** (`ac3ec14`).

`extract_xml` ya desenvuelve el contenedor de la DIAN: detecta la raíz, extrae el CDATA de la
factura embebida, la re-parsea y sigue el flujo existente. De paso captura `cude`,
`estado_dian` y `fecha_validacion_dian` del ApplicationResponse (campos **aditivos y
opcionales** — el UBL plano y el excel_writer no se ven afectados).

⚠️ **DEUDA ABIERTA — no considerar productivo todavía:** los fixtures son **sintéticos**,
construidos según `docs/research/dian-xml/FINDINGS.md`. **Falta validar contra 2-3
AttachedDocument REALES de la DIAN** (con y sin ApplicationResponse) antes de dar la Fase 1 por
buena. Además el XPath del CDATA no se pudo contrastar contra el Anexo Técnico 1.9 (no está
disponible localmente): el research dice `cac:Attachment/ext:ExternalReference/cbc:Description`
pero UBL estándar usa `cac:ExternalReference`, así que la búsqueda quedó tolerante a ambas —
apostar a una sola reintroduciría el fallo silencioso.

Verificación: 49 tests en `test_extractor.py` (43 previos + 6 nuevos), suite completa
263 passed / 2 skipped, flake8 limpio.

**Fase 2 (exógenas/renta en XML) sigue diferida** — no se tocó nada de eso.

### Antecedente: EOL de Node 20 (cerrado)
- **PR #48** (app: `.nvmrc`=22 + `engines.node>=22`) — MERGED (`1726294`).
- **PR #49** (infra: `build_spec` Amplify con `nvm use 22`) — MERGED (`206b35c`); **Terraform Apply completó con success** → Node 22 aplicado en el compute SSR de producción.

### Diagnóstico del EOL (verificado, resuelto)
- Nuestras Lambdas son `package_type = "Image"` (Python) → no afectadas.
- El aviso era del compute SSR de Amplify (`WEB_COMPUTE` + `Next.js - SSR`). Node 20 EOL 2026-04-30; corte de deploys 2027-03-03. Migrado a Node 22 (LTS, compatible Next 15.3).

## Pendiente

- **Rediseño visual dirección C — HECHO**, en PR (ver Tarea activa). Los fuentes del canvas ya no
  dependen de una sesión de Claude: están versionados en `docs/design/landing/`.
  **DEUDA nueva:** las fechas del bloque "Calendario DIAN" de la landing están hardcodeadas en
  `page.tsx`. Las anteriores (May-Ago) ya estaban VENCIDAS y se mostraban como próximas; se
  reemplazaron por las reales de `api/data/calendario_2026.json`, pero se van a volver a poner
  viejas solas. Lo correcto es leerlas del JSON en build time.
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
