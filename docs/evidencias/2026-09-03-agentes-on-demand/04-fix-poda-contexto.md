# Fix del 413 + brecha de CI encontrada de paso — 2026-09-03

## Fix aplicado (413 "Request too large")

En `agents/_shared/agent_core.py`, por los dos lados que hacían crecer la request:

1. **Snippets truncados** — `web_search()` recortaba nada; ahora corta cada `body` a
   `_MAX_SNIPPET_CHARS` (250 por defecto).
2. **Ventana deslizante** — `_podar_historial()` conserva íntegros solo los últimos
   `_MAX_TOOL_RESULTS_EN_CONTEXTO` (6) resultados de búsqueda; los anteriores se reemplazan por un
   marcador corto. **No se eliminan**: cada `tool_call` del asistente necesita su respuesta
   correspondiente o la API rechaza el historial por inconsistente. Hay un test que fija eso.

Se descartó reintentar: a diferencia del 429 del PR #34, la request siempre pesaría lo mismo.

## Preparado para pasar a un modelo de pago

A pedido del usuario, todo lo relevante quedó configurable por entorno, sin tocar código:

| Env var | Default | Para qué |
|---|---|---|
| `AGENTS_MODEL` | `openai/gpt-oss-120b` | Cambiar de modelo |
| `AGENTS_MAX_SNIPPET_CHARS` | `250` | Recuperar contexto al subir de tier |
| `AGENTS_MAX_TOOL_RESULTS` | `6` | Ídem |

Con más presupuesto de tokens basta subir los dos últimos por env var y se recupera la calidad del
reporte. **Salvedad importante**: si el modelo nuevo NO es de Groq (p. ej. Claude), además hay que
cambiar el cliente — `run_agent()` y `run_llm_only()` hoy instancian `Groq()` directo. Queda
anotado en el propio código.

## Brecha encontrada de paso: CI nunca corrió los tests de los agentes

`pytest.ini` fija `testpaths = tests` y `.github/workflows/ci.yml` corre `pytest tests/`. Por lo
tanto **ningún test bajo `agents/` se ejecutó nunca en CI**: unos ~25 tests escritos a lo largo de
todo este trabajo (`agents/_shared/test_agent_core.py`, `test_db_publish.py`, y los `test_agent.py`
/ `test_publish.py` de los 4 agentes). Los conteos de "tests passing" que se venían reportando NO
los incluían.

Intento de arreglarlo de una: `pytest tests agents` falla en la colección. Los 4 agentes tienen
archivos con el mismo basename (`test_agent.py`, `test_publish.py`) y no son paquetes, así que
pytest colisiona los nombres de módulo. Con `--import-mode=importlib` el error se mueve al
`import publish` de los propios tests — es exactamente la misma clase de colisión que
`_load_module` resolvió en `worker_handler.py`.

Arreglarlo requiere refactorizar los 8 archivos de test de los agentes, así que **queda como
trabajo aparte** para no mezclarlo con este fix. Mitigación inmediata: los tests de la poda se
escribieron en `tests/test_agent_core_poda.py`, donde CI sí los ejecuta.

Suite: 235 passed / 25 skipped (231 + los 4 nuevos).
