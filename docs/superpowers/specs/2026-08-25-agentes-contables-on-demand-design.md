# Agentes contables on-demand desde el chatbot — Design

## Contexto

El PR #33 conectó los 4 agentes contables standalone (`agents/contabilidad/*`) a TaxOps vía un
cron semanal de GitHub Actions (`.github/workflows/agentes-contables.yml`). El primer run manual
post-merge falló en los 4 jobs (PR #34 lo corrigió — colisión de rate limit de Groq por correr en
paralelo, y un bloque JSON que el modelo no siempre cierra). Al revisar ese fallo, surgió la
pregunta de fondo: ¿tiene sentido que estos 4 agentes corran *solo* por cron, o deberían poder
invocarse on-demand desde el chatbot?

Esta spec cubre la segunda parte: invocar los 4 agentes desde `services/chatbot.py` como
respuesta a una pregunta del usuario, con una política de cache/staleness para no disparar una
corrida cara (Groq + búsqueda web, 1-4+ minutos) en cada mensaje.

**El cron semanal no se toca en esta spec** — queda comentado (deshabilitado) desde el PR #34,
pendiente de decidir agente por agente si se reactiva, se reemplaza por on-demand, o conviven
ambos modos. Fuera de alcance de esta spec.

## Objetivo

Que el chatbot pueda responder preguntas como *"¿hay novedades de la DIAN esta semana?"*,
*"¿cuándo vence el próximo IVA?"* o *"buscame leads de veterinarias en Bucaramanga"*
consultando primero los datos ya persistidos (rápido, gratis) y disparando una corrida nueva del
agente correspondiente solo cuando ese dato está viejo o no existe.

## Fuera de alcance

- Reactivar o rediseñar el cron semanal (PR #34 ya lo deja comentado y funcional vía
  `workflow_dispatch`).
- Notificaciones in-chat en vivo ("polling" dentro de la conversación mientras el agente corre) —
  el resultado aparece en las páginas ya construidas (`/novedades`, `/admin/leads`,
  `/calendario`) cuando termina. Iteración futura si se necesita.
- Cambios a `agents/empleo/*` o `agents/inmobiliaria/*`.
- Caching de las 7 tools existentes del chatbot (`consultar_iva_mes`, `top_proveedores`, etc.) —
  investigado y descartado: operan sobre el `df` que ya manda el frontend en el body de la
  request (`api/routers/chatbot.py`), no hacen ninguna llamada externa cara. No hay nada que
  cachear ahí.

## Arquitectura

Reutiliza el patrón async ya existente en el repo (SQS + `worker_handler.py` + `job_store` en
DynamoDB) — el mismo mecanismo que usan hoy Exógenas y Renta para trabajos largos disparados
desde una request HTTP. Sin infraestructura nueva de Terraform: misma cola SQS
(`Settings.SQS_QUEUE_URL`), mismo Lambda worker (timeout 840s / 14 min, margen de sobra frente a
los ~4 min que tardó el agente más lento observado), mismo `job_store`.

```
Usuario → chatbot → tool (ej. consultar_novedades_dian)
                        │
                        ├─ lee novedades/leads_comerciales/calendario (Postgres/S3)
                        │
                        ├─ ¿dato fresco? ──sí──→ responde con el dato ya guardado (instantáneo)
                        │
                        └─ no / no existe
                              │
                              ▼
                        sqs.send_message(tipo="agente_contable", agente="dian-monitor", ...)
                              │
                              ▼
                     responde: "arrancó, revisá /novedades en unos minutos"
                              │
                              ▼ (async, minutos después)
                    worker_handler.py → run() del agente → publish.py → Postgres/S3
                              │
                              ▼
                  el usuario ve el resultado en la página correspondiente
```

## Componentes

### 1. Refactor de cada `agent.py` — `run()` importable

Hoy cada `agent.py` es un script CLI: `main()` arma prompt + corre `run_agent()`/`run_llm_only()`
+ escribe reporte + publica, y solo se ejecuta bajo `if __name__ == "__main__"`. Se extrae a:

```python
def run(config: dict, **overrides) -> str:
    """Misma lógica que main(), sin leer config.yaml del disco ni hacer I/O de reporte —
    recibe el config ya cargado (permite que el worker/tests inyecten overrides sin tocar
    archivos)."""
    system_prompt = build_system_prompt(config, **overrides)
    user_prompt = build_user_prompt(config, **overrides)
    return run_agent(system_prompt, user_prompt, AGENT_DIR)  # o run_llm_only, según el agente


def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run(config)
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), ..., report)
    print(f"Reporte escrito en {output_path}")
    from publish import publish
    publish(report)
```

Solo `prospector-clientes-contables` usa `**overrides` de verdad (sector/ciudad puntuales
pedidos por el chatbot, libres — sin restringir a una lista fija). Los otros 3 lo aceptan por
firma consistente pero lo ignoran.

**Archivos**: modifica los 4 `agent.py`. `main()` sigue siendo el entry point de CLI/GitHub
Actions — no cambia su comportamiento actual.

### 2. `worker_handler.py` — nueva rama `tipo == "agente_contable"`

```python
elif tipo == "agente_contable":
    _process_agente_contable(body)

def _load_module(path: Path, unique_name: str):
    """Carga un módulo por ruta explícita bajo un nombre único en sys.modules — mismo patrón
    que tests/conftest.py::load_fastapi_app(). Necesario porque los 4 agentes tienen cada uno
    su propio agent.py/publish.py: un import_module("agent") normal cachearía el PRIMER agente
    cargado en sys.modules["agent"] y lo devolvería para los siguientes, aunque sea un Lambda
    tibio reusado procesando dos agentes distintos en invocaciones (o records) separados."""
    spec = importlib.util.spec_from_file_location(unique_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _process_agente_contable(body: dict) -> None:
    agente = body["agente"]  # "dian-monitor" | "monitor-niif" | "vencimientos-tributarios" | "prospector-clientes-contables"
    job_id = body["job_id"]
    overrides = body.get("overrides", {})

    agent_dir = _ROOT / "agents" / "contabilidad" / agente
    agent_module = _load_module(agent_dir / "agent.py", f"agente_contable_{agente}_agent")
    publish_module = _load_module(agent_dir / "publish.py", f"agente_contable_{agente}_publish")

    try:
        config = agent_module.load_config(agent_dir / "config.yaml")
        report = agent_module.run(config, **overrides)
        publish_module.publish(report)
        job_store.put_job(job_id, "done", {"agente": agente})
    except Exception as exc:
        job_store.put_job(job_id, "error", {"agente": agente, "error": str(exc)})
```

**Nota de implementación**: `agent.py` hace `sys.path.insert(0, str(AGENT_DIR.parent.parent))`
al importarse (para resolver `from _shared.agent_core import ...`) — eso sigue funcionando igual
al cargarlo por ruta explícita, no depende de cómo se lo importó.

**Archivos**: modifica `api/worker_handler.py`.

### 3. Nuevas tools del chatbot

`_ejecutar_herramienta()` gana acceso a Postgres/S3 (hoy solo recibe `df`). Cuatro tools nuevas,
una por agente — firma conceptual:

```python
def _tool_consultar_novedades_dian() -> str: ...
def _tool_consultar_novedades_niif() -> str: ...
def _tool_consultar_vencimientos_tributarios() -> str: ...
def _tool_buscar_leads_comerciales(sector: str, ciudad: str) -> str: ...
```

Cada una sigue el mismo esqueleto:
1. Query de lectura (Postgres para novedades/leads, S3 para el calendario) — mismo criterio de
   degradación que `GET /novedades`/`GET /admin/leads` (`db_available()` → responde "no puedo
   consultar ahora" en vez de crashear).
2. Aplica la política de staleness (`_es_reciente()`, función pura, ver más abajo).
3. Fresco → devuelve el resumen ya guardado.
4. Viejo/inexistente → `sqs.send_message(...)`, devuelve mensaje de "arrancó, revisá la página
   correspondiente en unos minutos".

**Política de staleness** (aprobada en brainstorming):

| Agente | Fresco si... |
|---|---|
| dian-monitor / monitor-niif | última fila en `novedades` (por `tipo`) tiene `fecha_generado` ≤ 7 días |
| vencimientos-tributarios | casi nunca se considera "viejo" solo por tiempo (el calendario DIAN es semi-estático) — se dispara solo si el usuario pide explícitamente refrescar, o si no hay ningún evento futuro dentro de los próximos 30 días en el calendario actual |
| prospector-clientes-contables | existe al menos 1 fila en `leads_comerciales` con ese `sector`+`ciudad` exactos (sin importar antigüedad — si el sector/ciudad nunca se buscó, se dispara; si ya se buscó alguna vez, se muestra lo que hay salvo pedido explícito de refrescar) |

```python
def _es_reciente(fecha_generado: date, dias: int = 7) -> bool:
    return (date.today() - fecha_generado).days <= dias
```

**Cola SQS**: se reutiliza `Settings.SQS_QUEUE_URL` (la misma de exogenas/renta) — el worker ya
despacha por `tipo`, cero infra nueva de Terraform.

**Archivos**: modifica `services/chatbot.py` — las 4 tools nuevas importan `db.database.get_db`/
`db_available` y `boto3` directamente (mismo criterio que ya usan los routers `novedades.py`/
`admin.py`/`calendario.py`), no dependen de que se les inyecte nada nuevo desde afuera:
`_ejecutar_herramienta(nombre, args, df)` gana una rama para las 4 tools nuevas que las llama sin
pasarles `df` (no lo necesitan). `api/routers/chatbot.py` no cambia.

## Manejo de errores

- DB/S3 no disponible al leer el cache → la tool responde "no puedo consultar ahora mismo", no
  crashea el turno de chat completo (mismo criterio que endpoints existentes).
- El agente falla en el worker (bug de prompt, rate limit agotado tras los reintentos, etc.) →
  `job_store` queda en `status="error"` — el chat no se entera en el momento (ya respondió
  "revisá en un rato"); mismo patrón de falla silenciosa-pero-visible-en-logs que ya tiene el
  resto de la app para jobs async. No es un caso nuevo a diseñar.
- Sector/ciudad libres en prospector: si no hay resultados verificables, el agente ya reporta eso
  en el propio texto (`publish.py` inserta 0 filas, `n == 0` — no es un error, es "no encontré
  nada", visible en el reporte del agente si se revisa manualmente).

## Testing

Mismo patrón TDD que el PR #33 y #34 — nada nuevo que inventar:

- **`run()` de cada agente**: test que, mockeando `run_agent`/`run_llm_only`, confirma que
  `build_system_prompt`/`build_user_prompt` reciben los overrides correctos y el resultado se
  propaga tal cual.
- **`worker_handler.py`**: agregar el caso `tipo="agente_contable"` a `tests/test_worker_handler.py`
  (mockeando `run()`/`publish()`, verificando `job_store.put_job` con el resultado esperado en
  éxito y en error).
- **Tools nuevas**: test por tool con SQLite de test (como `test_novedades.py`) + moto para SQS,
  cubriendo los 3 caminos (fresco / viejo / inexistente).
- **`_es_reciente()`**: función pura, testeada aislada con fechas fijas.

## Próximos pasos

Esta spec queda lista para pasar por `writing-plans` y generar el plan de implementación
task-by-task (TDD), igual que se hizo con el PR #33.
