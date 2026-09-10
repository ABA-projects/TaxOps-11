# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-10 · **Por:** Claude Code (.dockerignore + corrección de estado)

---

## Tarea activa

**Ninguna tarea de código a medias.** Working tree limpio salvo `context/`.

### Corrección al handoff anterior
La versión previa de este archivo decía que los cambios de la landing estaban *"sin commitear,
esperando decisión de Jaime"*. Eso ya no aplica: **el PR #45 se mergeó** (`b846d08`). Verificado
hoy — los 7 claims falsos ya no existen en `taxops-web/app/page.tsx` (grep = 0).

### Hecho en esta sesión
- **`.dockerignore` creado** en la raíz. Existía el riesgo de que el `COPY agents/` (agregado en
  el #36) arrastrara caches, `.venv` y reportes generados en un build LOCAL desde una copia sucia;
  en CI no se veía porque el checkout está limpio.
- Verificado **construyendo la imagen de verdad**, no solo por lectura:
  - `docker build -f api/Dockerfile-lambda .` → exitoso.
  - Dentro de la imagen: presentes `autorretenedores.txt`, `calendario_2026.json`, `init.sql`,
    los `config.yaml` de los agentes, `agent.py`/`publish.py` y `worker_handler.py`.
  - Ausentes: `tests/`, `taxops-web/`, `infra/`, `.git/`. Cero `__pycache__`.
  - `import worker_handler` dentro del contenedor → OK, con `_process_agente_contable` presente.
- **NO se excluyó `*.yaml`** aunque sería tentador: `worker_handler` lee
  `agents/contabilidad/*/config.yaml` con `yaml.safe_load` en cada corrida. Excluirlo rompería
  todos los agentes en producción, en silencio. Queda advertido en el propio `.dockerignore`.

## Pendiente

- **Rediseño visual dirección C ("Herramienta")** — oscuro, IBM Plex Mono + Inter, log de proceso
  central. Aprobado por Jaime, ya desarrollado completo con copia honesta.
  Canvas: https://claude.ai/code/artifact/66cbf36f-054d-478a-a17c-3bb8bfbd4d4b
  **Nota para Kiro:** los fuentes se perdieron con la limpieza de `/tmp`, pero el canvas se
  publicó desde una sesión de Claude Code, así que **Claude sí puede recuperarlos** (WebFetch al
  artifact + `seed-canvas.mjs --extract`). No es un bloqueo permanente: es trabajo que le toca a
  Claude, no a Kiro. Falta portar ese diseño a `taxops-web/app/page.tsx` (566 líneas).
- **Discovery DIAN/XML** — la DIAN habría dejado de exigir la descarga del PDF; se podría leer el
  XML directo. Toca facturas, exógenas, renta e infra. Sin research todavía.
- **Lambda Node.js 20.x EOL** — aviso de AWS. No es de nuestro Terraform (nuestras Lambdas son
  imágenes Python); casi seguro el SSR de Amplify. Deadline duro: 03/03/2027.

## Notas de handoff

- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
- Los commits van firmados solo por Jaime — sin `Co-Authored-By`.
