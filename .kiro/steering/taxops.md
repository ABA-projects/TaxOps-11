---
inclusion: always
description: "Reglas de comportamiento de Kiro en TaxOps-11: coexistencia con Claude Code, protocolo de arranque/cierre y no-destrucción. El contexto compartido vive en context/; el detalle técnico en CLAUDE.md."
---

# Kiro en TaxOps-11 — coexistencia con Claude Code

Este repo se desarrolla con **Claude Code** y **Kiro CLI** sobre el mismo proyecto.
Comparten una fuente de verdad en `context/`. No compiten memorias.

## Premisa de costo (no negociable)

**Todo gratis, siempre.** Antes de proponer o crear cualquier recurso AWS, di su costo; si no está
en capa gratuita **perpetua**, dilo antes de hacerlo. Dos datos verificados el 2026-09-30 que
cambian el cálculo:

- La cuenta `562548008942` **no tiene capa gratuita de 12 meses** — es miembro de una AWS
  Organization y el free tier se cuenta desde la cuenta de gestión, cuyo reloj ya venció.
- El free tier **se agrega por consolidated billing en toda la Organization**: lo que consuman las
  otras cuentas descuenta del mismo 1M de requests de Lambda y 1 TB de CloudFront.
- Cost Explorer cobra **US$0,01 por consulta**: una sola mensual agrupada por servicio, no iterar.

## Fuente de verdad (no dupliques)

- **`CLAUDE.md`** — instrucciones y arquitectura técnica detallada. Es de Claude. Léelo cuando necesites detalle de módulos/regex/schema. **No lo edites** salvo que el usuario lo pida explícitamente y de forma aditiva.
- **`README.md`** — visión de producto y despliegue.
- **`context/`** — estado, decisiones, tarea activa, changelog y memoria. **Neutral y compartido.** Aquí escribes.
- **`AGENTS.md`** — índice de punteros (no contenido).

Si un dato ya existe en `CLAUDE.md` o `README.md`, **referéncialo**, no lo copies.

## Protocolo de ARRANQUE (al iniciar sesión)

1. Lee `context/current-task.md` (qué se estaba haciendo y qué sigue).
2. Corre `scripts/context-sync.sh` para ver qué cambió en git desde el último sync.
3. Lee solo lo que el script marque como cambiado — **incremental, no releas todo el proyecto**.
4. Si necesitas detalle técnico de un módulo, consulta la sección específica de `CLAUDE.md`, no el archivo entero.
5. Reconstruye un contexto de trabajo conciso: proyecto, estado, tarea, últimos cambios, decisiones, problemas conocidos, siguiente acción.

## Protocolo de CIERRE (cuando la sesión produce cambios relevantes)

> ⚠️ **Esto se incumplió y costó tiempo real.** Entre el 2026-09-16 y el 2026-09-30 entraron tres
> PRs —incluida la migración a la cuenta AWS dedicada (#57), el cambio de infra más grande del
> proyecto— **sin actualizar `context/`**. El otro agente arrancó ciego y tuvo que reconstruir el
> estado desde git, GitHub y producción. **Un PR mergeado sin actualizar `context/current-task.md`
> no está terminado.** Si el cambio toca infra, deploy o costos, va también a `decisions.md`.

Actualiza de forma **incremental y aditiva**:
- `context/current-task.md` — nuevo estado y próximos pasos.
- `context/changelog.md` — una entrada nueva al inicio (qué/por qué/archivos/decisiones/problemas/estado/próximos pasos).
- `context/project-state.md` — si cambió el estado de algún componente.
- `context/decisions.md` — si tomaste una decisión técnica relevante (ADR nuevo al inicio).
- `context/memory/` — si aprendiste algo reutilizable o resolviste un problema.

No registres ruido (typos, formateo). Consolida, no acumules.

## Regla de NO-DESTRUCCIÓN (prioridad absoluta)

- **Nunca** borres ni sobrescribas destructivamente `CLAUDE.md`, `.claude/`, `docs/superpowers/`, `.superpowers/` ni memoria existente.
- Antes de modificar un archivo existente: léelo, entiéndelo, cambia de forma aditiva.
- Git es la red de seguridad: `git status`/`git diff` antes de cambios grandes. Nunca `git reset --hard`, `git clean -fd`, `push --force` sin que el usuario lo pida explícitamente.
- Cambios en `infra/` van por PR → plan → merge → aprobación manual → apply. Ningún `terraform apply` manual.

## Seguridad

- Nunca copies secretos al contexto compartido. Viven en `.envrc`, `infra/**/terraform.tfvars.secret`, `api/.env` (todos gitignored) y SSM. Referéncialos por nombre, nunca por valor.
