# Estado al 2026-09-03 y cómo retomar

## Cadena de fallos encontrados probando end-to-end
Cada corrida destapó la siguiente capa. Ninguno de estos lo detectaron los tests ni tres rondas
de review, porque todos viven en la brecha entre el código y su configuración de despliegue.

| # | Corrida | Error | PR | Estado |
|---|---|---|---|---|
| 1 | post #36 | `No module named 'ddgs'` | #37 | mergeado |
| 2 | post #37 | `413 Request too large` (8097 vs 8000 TPM) | #38 | mergeado |
| 3 | — | el merge del #38 nunca desplegó: `agents/**` faltaba en el filtro de paths | #39 | **abierto** |

El patrón se repite: algo cambia en un lado y su configuración asociada queda desactualizada.
El #36 agregó `COPY agents/` pero no las dependencias (#37) ni el trigger de deploy (#39).

## Dónde quedó
- Deploy manual (`workflow_dispatch`, run 33825558513) **exitoso**: la poda de contexto del #38
  YA está en producción.
- **PR #39 abierto** — agrega `agents/**` al filtro de paths de `deploy-lambda.yml`. Sin esto,
  todo cambio futuro a un agente se mergea sin desplegarse.
- La tercera prueba end-to-end NO se llegó a correr: expiró la sesión SSO de AWS.

## Cómo retomar (en este orden)
1. `aws sso login --profile taxops-admin`
2. Encolar el job de prueba:
   ```bash
   export AWS_PROFILE=taxops-admin
   JOB="test-manual-$(date +%s)"
   aws sqs send-message --region us-east-1 \
     --queue-url https://sqs.us-east-1.amazonaws.com/786567028012/taxops-jobs-prod \
     --message-body "{\"tipo\":\"agente_contable\",\"agente\":\"dian-monitor\",\"job_id\":\"$JOB\",\"overrides\":{}}"
   ```
3. Esperar 2-4 min y leer el resultado:
   ```bash
   aws dynamodb get-item --region us-east-1 --table-name taxops-jobs-prod \
     --key "{\"job_id\":{\"S\":\"$JOB\"}}"
   ```
   - `status=done` -> confirmar la fila: `SELECT tipo, titulo, fecha_generado FROM novedades ORDER BY created_at DESC LIMIT 3;`
   - `status=error` -> el traceback está en `aws logs tail /aws/lambda/taxops-worker-prod --since 15m`
4. Recién ahí, la Prueba B (chatbot): en app.taxopsapp.com, proveedor **Groq u OpenAI**
   (Anthropic y Google no tienen loop de tools), preguntar "¿hay novedades de la DIAN?".
   1ª vez debe encolar; 2ª vez debe responder desde cache sin encolar.

## Deuda técnica pendiente (no bloquea, documentada)
- **CI nunca corre los tests de `agents/`**: `pytest.ini` fija `testpaths = tests`. Son ~25 tests
  que jamás se ejecutaron. Arreglarlo exige refactorizar los 8 archivos de test de los agentes,
  que colisionan por basename repetido (misma clase de problema que resolvió `_load_module`).
- No existe `.dockerignore` en el repo.
