# Changelog de contexto — TaxOps-11

> Registro **incremental** de cambios relevantes por sesión (Claude o Kiro).
> No es el changelog de releases del producto — es la bitácora de trabajo entre agentes.
> Entradas nuevas al inicio. No registrar ruido (formateo, typos menores).

Formato por entrada:
```
## YYYY-MM-DD — <agente> — <título corto>
- Qué cambió · Por qué · Archivos/componentes · Decisiones · Problemas · Estado · Próximos pasos
```

---

## 2026-09-09 — Kiro CLI — Corregidos los claims falsos de la landing → PR #45
- **PR:** https://github.com/ABA-projects/TaxOps-11/pull/45 (rama `fix/landing-claims-honestos`, commit `46d0bad`).
- **Qué cambió:** `taxops-web/app/page.tsx` — eliminados testimonios inventados (array + render), quitado "SLA 99.9%", reemplazada feature "Funciona Sin Internet" por "Deduplicación por CUFE", corregidas cifras del hero (+500/100% → 3.286 autorretenedores/Art. 490), badge del hero y sección OFFLINE→"Sin instalar nada", nueva sección "Construido sobre la norma colombiana" con datos verificables. Limpiados imports huérfanos.
- **Por qué:** los claims eran falsos (SaaS en AWS, no offline; cifras y testimonios inventados) — riesgo legal/reputacional señalado por Jaime.
- **Verificación:** `tsc --noEmit` OK, `next lint` sin warnings, `next build` exit 0.
- **Decisiones:** se corrigieron los claims manteniendo el diseño actual; el rediseño visual "dirección C" queda como tarea aparte (fuentes a recuperar del canvas de Claude).
- **Estado:** landing sin claims falsos, compila.
- **Próximos pasos:** decidir commit; opcionalmente abordar rediseño dirección C y `.dockerignore`.

## 2026-09-09 — Kiro CLI — Integración de memoria de Claude (estado 2026-09-05)
- **Qué cambió:** se sincronizó el contexto compartido con la memoria de Claude `taxops11-estado-2026-09-05`, verificada contra git.
- **Por qué:** Claude avanzó el proyecto desde el setup de coexistencia; había que reflejarlo sin duplicar la nota.
- **Hallazgos verificados:** `main` avanzó a `fc0401e` (PRs #43, #44 mergeados desde `f397206`); agentes on-demand terminados y verificados en prod (#36–#44); claims falsos de la landing confirmados vivos por grep (`page.tsx` 45, 138, 165-167).
- **Archivos:** `context/current-task.md` (tarea activa = landing), `context/project-state.md` (agentes ✅, rama actual), `context/memory/known-issues.md` (tabla de claims + deuda `.dockerignore`).
- **Decisiones:** ninguna nueva (se referenció la memoria de Claude, no se copió entera).
- **Estado:** contexto compartido al día con lo último de Claude.
- **Próximos pasos:** ejecutar la corrección de la landing (empezar por testimonios líneas 165-167).

## 2026-09-09 — Kiro CLI — Setup del sistema de coexistencia Claude + Kiro
- **Qué cambió:** se creó la fuente de verdad compartida `context/`, el puente `AGENTS.md`, las reglas de Kiro en `.kiro/steering/` y el script `scripts/context-sync.sh`.
- **Por qué:** poder trabajar con Claude Code y Kiro CLI sobre el mismo proyecto sin perder contexto ni romper la configuración de Claude.
- **Archivos/componentes:** `context/*`, `AGENTS.md`, `.kiro/steering/taxops.md`, `scripts/context-sync.sh`, `context/README.md`.
- **Decisiones:** ver ADR-000 en `decisions.md`.
- **Problemas:** ninguno.
- **Estado:** setup completo; `CLAUDE.md` intacto.
- **Próximos pasos:** al abrir Kiro, correr `scripts/context-sync.sh`; retomar backlog cuando aplique.
