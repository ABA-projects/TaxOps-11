# Prueba end-to-end del worker — 2026-09-03

## Qué se probó
Se encoló directamente en SQS (`taxops-jobs-prod`) un mensaje del tipo que produce el chatbot,
saltando la UI, para probar el camino que corrigió el PR #36:

```json
{"tipo":"agente_contable","agente":"dian-monitor","job_id":"test-manual-1788449443","overrides":{}}
```

## Resultado en DynamoDB (`taxops-jobs-prod`)

```json
{"job_id": "test-manual-1788449443",
 "agente":  "dian-monitor",
 "status":  "error",
 "error":   "No module named 'ddgs'"}
```

## Lectura del resultado

**Los fixes del PR #36 funcionan — confirmado por este mismo error:**

1. **C1 (COPY agents/) OK.** El error es "No module named 'ddgs'", no "no such file agent.py".
   Para llegar a importar `ddgs` el runtime tuvo que encontrar y empezar a ejecutar
   `agents/contabilidad/dian-monitor/agent.py`: el código de los agentes SÍ está en la imagen.
2. **C2 (_load_module dentro del try) OK.** El fallo quedó REGISTRADO como `status=error` con su
   causa. Antes del #36 esta excepción escapaba del try, mataba la invocación Lambda entera y el
   job no dejaba rastro: se quedaba "pending" para siempre. Que exista este item es la prueba.
3. **I1 (logging) OK.** El worker no murió; siguió vivo para escribir el registro.

## Bug NUEVO encontrado (no lo detectó ningún review)

`api/Dockerfile-lambda` copia `agents/` pero solo instala `api/requirements-api.txt`, que NO
incluye `ddgs` — la librería de búsqueda web que usan los 4 agentes
(`agents/_shared/agent_core.py::web_search`).

Comparación de dependencias declaradas por los agentes vs. instaladas en la imagen:

| Dependencia | Agentes | requirements-api.txt |
|---|---|---|
| groq | sí | sí |
| python-dotenv | sí | sí |
| PyYAML | sí | sí (agregada en el #36) |
| psycopg2-binary | sí | sí |
| boto3 | sí | sí |
| **ddgs** | **sí** | **NO** ← causa del fallo |

Por qué ningún review lo vio: los reviews verificaron que el `COPY agents/` existiera, pero la
capa de instalación de dependencias es un paso distinto del Dockerfile. Y los tests locales pasan
porque `ddgs` está instalado en el entorno de desarrollo. Solo una corrida real contra la imagen
desplegada podía revelarlo.

## Fix aplicado

1. `api/requirements-api.txt`: se agrega `ddgs>=9.15`.
2. `tests/test_agentes_deps_en_imagen.py` (nuevo): guarda contra el drift. Compara las
   dependencias declaradas en `agents/contabilidad/*/requirements.txt` contra las que instala
   `api/requirements-api.txt` y falla nombrando las que faltan. Verificado que detecta el fallo:
   quitando `ddgs` a mano, el test falla listando los 4 agentes afectados.

Suite: 231 passed / 25 skipped. flake8 limpio.

## Pendiente tras el fix
Repetir esta misma prueba después del deploy para confirmar `status=done` y la fila en `novedades`.
