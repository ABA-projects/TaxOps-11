# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-09 · **Por:** Kiro CLI (claims falsos de la landing corregidos)

---

## Tarea activa

**Ninguna tarea de código a medias.** Los claims falsos de la landing quedaron corregidos y
enviados en **PR #45** (`fix/landing-claims-honestos`, https://github.com/ABA-projects/TaxOps-11/pull/45).
Verificado con `tsc --noEmit`, `next lint` y `next build` en verde.

### Hecho en esta sesión
- Eliminados los testimonios inventados (array `TESTIMONIALS` + su sección de render).
- Quitado "SLA 99.9% uptime" del plan Empresarial.
- Reemplazada la feature "Funciona Sin Internet" → "Deduplicación por CUFE" (real).
- Corregidas las cifras del hero: "+500 facturas / 100% datos en tu servidor" → "3.286 autorretenedores / Art. 490 prorrateo IVA".
- Corregido el badge del hero y reemplazada la sección "OFFLINE BADGE" por "Sin instalar nada" (web app).
- Nueva sección "Construido sobre la norma colombiana" con 4 datos verificables (reemplaza a testimonios).
- Limpiados imports huérfanos (`WifiOff`, `Star`) y tag del chatbot.

## Pendiente relacionado (decisión de producto, NO bloqueante)

- **Rediseño visual dirección C ("Herramienta")** — oscuro, IBM Plex Mono + Inter, log de proceso central.
  Aprobado por Jaime. **BLOQUEADO desde este entorno (verificado 2026-09-09):**
  - El canvas de Claude (`https://claude.ai/code/artifact/66cbf36f-054d-478a-a17c-3bb8bfbd4d4b`) requiere sesión autenticada de Claude — el fetch anónimo no devuelve contenido.
  - `seed-canvas.mjs` no existe en el sistema.
  - `/tmp/taxops-landing/` fue limpiado (confirmado, no existe).
  → **Para desbloquear:** Jaime debe recuperar los fuentes desde su sesión de Claude (abrir el canvas y copiar los archivos) y dejarlos en el repo o en un directorio accesible. Kiro no puede reconstruir un diseño de producto aprobado sin sus fuentes (sería adivinar).
- **Deuda menor:** crear `.dockerignore` (evitar que `COPY agents/` arrastre basura en builds locales).

## Notas de handoff

- Cambios sin commitear en `taxops-web/app/page.tsx`. No se ha hecho commit (esperar decisión de Jaime).
- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
