# AGENTS.md — TaxOps-11

> **Este archivo es un puente, no una fuente de verdad.** No duplica contenido: apunta a él.
> Lo carga automáticamente Kiro CLI (`kiro_default`). Claude Code sigue usando `CLAUDE.md`.
> Ambas herramientas trabajan sobre el **mismo** proyecto y el **mismo** contexto compartido.

## Cómo está organizado el contexto (fuente única de verdad por tipo)

| Necesitas… | Míralo en | Quién lo mantiene |
|---|---|---|
| Instrucciones + arquitectura técnica detallada (módulos, regex, schema, comandos) | **`CLAUDE.md`** | Claude (Kiro lo lee, no lo edita salvo que se pida) |
| Visión de producto y arquitectura de despliegue | **`README.md`** | ambos |
| Estado del proyecto (qué está hecho/en curso/pendiente/bloqueado) | **`context/project-state.md`** | ambos |
| Decisiones técnicas (ADR) | **`context/decisions.md`** | ambos |
| Tarea activa + handoff vivo | **`context/current-task.md`** | ambos |
| Bitácora incremental de sesiones | **`context/changelog.md`** | ambos |
| Memoria: problemas conocidos, convenciones, aprendizajes | **`context/memory/`** | ambos |
| Reglas de comportamiento de Kiro (arranque/cierre/no-destrucción) | **`.kiro/steering/taxops.md`** | Kiro |
| Planes/specs/handoffs históricos | **`docs/superpowers/`** | Claude |

## Antes de tocar infra o deploy

- **Premisa "todo gratis, siempre"** y las tres salvedades verificadas (la cuenta no tiene free
  tier de 12 meses; el free tier se comparte en toda la Organization; Cost Explorer cobra por
  consulta): ver `.kiro/steering/taxops.md` y `CLAUDE.md` §Migración a AWS.
- **El frontend ya NO se despliega por el webhook de Amplify.** `enable_auto_build` está en
  `false`; el deploy entra por `.github/workflows/deploy-web.yml` (`paths: taxops-web/**`).
  Detalle y rollback en `CLAUDE.md` §Deployment.
- Regla de oro de `infra/`: PR → plan → merge → aprobación manual → apply. Nunca `apply` a mano.

## Regla de coexistencia

- **No dupliques.** Si un dato ya está en `CLAUDE.md` o `README.md`, referéncialo — no lo copies aquí ni en `context/`.
- **`CLAUDE.md` es de Claude y permanece intacto.** Kiro puede leerlo; solo lo modifica si el usuario lo pide explícitamente y de forma aditiva.
- **`context/` es neutral y compartido.** Es donde vive el estado dinámico que ambos agentes actualizan.
- El detalle del sistema, su mantenimiento y el flujo bidireccional está en **`context/README.md`**.

## Al empezar una sesión de Kiro

Sigue el protocolo de arranque definido en `.kiro/steering/taxops.md`:
lee `context/current-task.md`, corre `scripts/context-sync.sh` para ver cambios de git desde el último sync,
y reconstruye el contexto de forma incremental (no releas todo el proyecto).
