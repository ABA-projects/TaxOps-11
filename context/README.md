# context/ — Fuente de verdad compartida (Claude Code ↔ Kiro CLI)

Este directorio es el **contexto de ingeniería compartido** de TaxOps-11. Permite que
**Claude Code** y **Kiro CLI** trabajen sobre el mismo proyecto sin perder contexto,
decisiones ni memoria — como dos interfaces sobre un único cerebro del proyecto, no como
dos memorias que compiten.

## Por qué existe

El proyecto se desarrollaba con Claude Code (`CLAUDE.md`, `.claude/commands/`, superpowers).
Se añadió Kiro CLI **sin migrar ni romper nada de Claude**. La coexistencia se logra apoyándose
en un mecanismo nativo de Kiro: el agente por defecto (`kiro_default`) carga automáticamente
`AGENTS.md`, `README.md` y `.kiro/steering/**/*.md`. Aprovechamos eso para apuntar al contexto
compartido, sin duplicar contenido.

## Mapa de la arquitectura

```
                    ┌──────────────────────────────┐
                    │   Fuente de verdad compartida │
                    │            context/           │
                    └───────────────┬───────────────┘
                                    │  leen y escriben ambos
                 ┌──────────────────┴──────────────────┐
                 ▼                                      ▼
        ┌─────────────────┐                    ┌─────────────────┐
        │   Claude Code   │                    │    Kiro CLI     │
        │   lee CLAUDE.md │                    │  lee AGENTS.md  │
        │  .claude/, SP   │                    │ .kiro/steering/ │
        └────────┬────────┘                    └────────┬────────┘
                 └──────────────────┬───────────────────┘
                                    ▼
                              Git / Proyecto
```

## Quién es dueño de qué (regla de fuente única de verdad)

| Archivo/dir | Contiene | Dueño | ¿Kiro lo carga solo? |
|---|---|---|---|
| `CLAUDE.md` | Instrucciones + arquitectura técnica detallada | Claude | No lo edita salvo petición explícita |
| `README.md` | Visión de producto + despliegue | ambos | Sí (auto) |
| `AGENTS.md` | Puente/índice de punteros (sin contenido propio) | ambos | **Sí (auto)** |
| `.kiro/steering/taxops.md` | Reglas de comportamiento de Kiro | Kiro | **Sí (auto)** |
| `context/project-state.md` | Estado por componente | ambos | Vía referencia |
| `context/decisions.md` | ADRs | ambos | Vía referencia |
| `context/current-task.md` | Tarea activa + handoff | ambos | Vía protocolo de arranque |
| `context/changelog.md` | Bitácora incremental | ambos | Vía referencia |
| `context/memory/` | Problemas, convenciones, aprendizajes | ambos | Vía referencia |
| `.claude/commands/`, `docs/superpowers/`, `.superpowers/` | Slash commands, planes, specs, handoffs | Claude | No |

**Principio:** cada dato tiene un único hogar. Si algo ya está en `CLAUDE.md` o `README.md`,
se referencia — no se copia a `context/`.

## Flujo bidireccional

**Claude → contexto → Kiro:** Claude trabaja y actualiza `context/` (o Kiro detecta los commits
de Claude vía `context-sync.sh`). Al abrir Kiro, este lee `current-task.md` y el delta de git.

**Kiro → contexto → Claude:** Kiro trabaja y actualiza `context/`. Claude, al retomar, lee los
mismos archivos. `CLAUDE.md` puede referenciar `context/current-task.md` para cerrar el círculo.

La sincronización es siempre **aditiva y no destructiva**.

## Protocolo de arranque (ambos agentes)

1. Leer `context/current-task.md`.
2. Correr `scripts/context-sync.sh` → ver commits y archivos cambiados desde el último sync.
3. Leer **solo** lo cambiado (incremental > completo). Para detalle técnico, ir a la sección
   puntual de `CLAUDE.md`, no al archivo entero.
4. Construir un contexto de trabajo conciso y arrancar.

Kiro tiene esto formalizado en `.kiro/steering/taxops.md` (se carga en cada sesión).

## Protocolo de cierre (cuando hay cambios relevantes)

Actualizar de forma incremental y aditiva:
- `current-task.md` — nuevo estado y próximos pasos.
- `changelog.md` — una entrada nueva al inicio.
- `project-state.md` — si cambió el estado de un componente.
- `decisions.md` — si hubo una decisión técnica (ADR nuevo al inicio).
- `memory/` — si hay un aprendizaje o problema/solución reutilizable.

Al terminar, opcionalmente `scripts/context-sync.sh --mark` para fijar el punto de sync.

## Detección incremental de cambios

`scripts/context-sync.sh` usa git como mecanismo de detección:
- Sin argumentos: muestra el delta (commits + `--stat`) desde el marcador `context/.last-sync`,
  más el working tree sin commitear.
- `--mark`: además fija el marcador en el `HEAD` actual.

`context/.last-sync` es estado local por máquina (está en `.gitignore`) — cada entorno lleva su
propio punto de sincronización.

## Política de memoria (evitar el basurero de logs)

`memory/` guarda **conocimiento consolidado**, no historial crudo:
- `known-issues.md` — bugs pendientes y problemas resueltos (con su fix).
- `conventions.md` — comandos frecuentes, reglas de oro, entornos.

Reglas: consolidar en vez de acumular; al resolver un problema, moverlo a "Resueltos" con el fix;
no registrar ruido (typos, formateo). El changelog lleva el histórico por sesión; la memoria lleva
lo reutilizable.

## Seguridad

Nunca se copian secretos a `context/`. Viven en `.envrc`, `infra/**/terraform.tfvars.secret`,
`api/.env` (todos gitignored) y en SSM Parameter Store. Se referencian por nombre, nunca por valor.

## Mantenimiento

- Mantén `AGENTS.md` y `.kiro/steering/taxops.md` **delgados** — se cargan en cada turno de Kiro.
- Si `CLAUDE.md` crece con nueva arquitectura, no la copies a `context/`: referénciala.
- Revisa periódicamente que `project-state.md` refleje la realidad (estado por componente).
- Si añades un tipo de contexto nuevo, dale un único hogar y regístralo en la tabla de arriba y en `AGENTS.md`.
