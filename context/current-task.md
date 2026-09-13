# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-12 · **Por:** Claude Code (cron #51 y landing #52 mergeados)

---

## Tarea activa

**Ninguna tarea de código a medias.** Todo mergeado, nada en vuelo.

Cerrado hoy:
- **PR #51** — cron semanal reactivado, pero SOLO para `dian-monitor` y `monitor-niif`. Los otros
  dos (`vencimientos-tributarios`, `prospector-clientes-contables`) se saltan en el cron con un
  `if` explícito sobre `github.event_name`: el calendario DIAN se publica una vez al año y el
  prospector necesita sector/ciudad del usuario. Siguen disponibles vía `workflow_dispatch` y
  desde el chatbot.
- **PR #52** — landing portada a la dirección C (oscura, IBM Plex Mono, log de proceso). Se
  preservó el contenido honesto del #45 (verificado: 0 claims falsos reintroducidos) y los
  fuentes del canvas quedaron versionados en `docs/design/landing/`.

## Pendiente

- **Rediseño visual dirección C — HECHO y mergeado** (PR #52). Los fuentes del canvas ya no
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
  **Fase 1 HECHA y mergeada** (PR #50, `ac3ec14`). Queda la deuda de validarla contra 2-3
  AttachedDocument REALES — Jaime los consigue el lunes 2026-09-15. Exógenas/renta en XML = Fase 2,
  sigue diferida (el research la marca como dudosa: esos documentos llegan en PDF).

## Notas de handoff

- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
- Los commits van firmados solo por Jaime — sin `Co-Authored-By`.
