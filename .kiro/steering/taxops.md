---
inclusion: always
description: "Reglas de comportamiento de Kiro en TaxOps-11: coexistencia con Claude Code, protocolo de arranque/cierre y no-destrucción. El contexto compartido vive en context/; el detalle técnico en CLAUDE.md."
---

# Kiro en TaxOps-11 — coexistencia con Claude Code

Este repo se desarrolla con **Claude Code** y **Kiro CLI** sobre el mismo proyecto.
Comparten una fuente de verdad en `context/`. No compiten memorias.

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
