# Segunda corrida end-to-end (post PR #37) — 2026-09-03

## Resultado
`job_id: test-manual-1788463399`, agente `dian-monitor`:

```
status: error
error:  Error code: 413 - Request too large for model `openai/gpt-oss-120b` ...
        on tokens per minute (TPM): Limit 8000, Requested 8097
```

## Avance confirmado
El error cambió de `No module named 'ddgs'` a un 413 de Groq. Eso prueba que el PR #37 funcionó:
`ddgs` ya está en la imagen, el agente importó, ejecutó el loop de búsqueda web y llegó a
construir una request grande. Ya no falla por empaquetado.

## Causa raíz del 413
NO es el mismo problema que arregló el PR #34. Aquel era un **429** (rate limit alcanzado por
concurrencia entre los 4 jobs del cron), y se resolvió serializando + retry con backoff.

Este es un **413 Request too large**: una sola request supera el tope. Reintentar no sirve —
la request siempre será igual de grande.

El mecanismo, en `agents/_shared/agent_core.py`:
- `web_search()` (línea 115) devuelve 5 resultados, cada uno con el `body` completo del snippet.
- `run_agent()` (línea 193) acumula CADA resultado en `messages` y nunca poda el historial.
- Con `max_iterations=15`, la conversación crece de forma monotónica hasta pasar el tope.

El tier gratuito de Groq permite **8000 TPM**. La request pesó 8097 tokens: se pasó por poco,
lo que explica que algunas corridas del cron sí hayan terminado (p. ej. vencimientos-tributarios
completó 8 iteraciones el 2026-08-25) y otras no. Es un fallo de borde, no determinista.
