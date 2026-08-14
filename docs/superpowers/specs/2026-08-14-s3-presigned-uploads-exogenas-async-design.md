# Upload directo a S3 (presigned URLs) + Exógenas async

**Goal:** Eliminar el límite de 6MB de payload de Lambda Function URL (síncrono) que rompe la carga de lotes grandes en Facturas, Exógenas y Renta, y resolver el riesgo de timeout de 60s de la Lambda API en Exógenas (procesamiento OCR pesado corriendo síncrono dentro del request/response).

**Contexto — cómo se encontró:** Verificado en producción real (2026-08-14): subir 41 certificados en Exógenas falló con "No se pudo conectar con el servidor". Reproducido con `curl` + payload sintético de 7MB → `HTTP 413`. Confirmado que Cloud Run (plataforma anterior, 32MB de límite) nunca expuso este problema — es una brecha real de la migración a Lambda, no una regresión de código. Facturas y Renta comparten el mismo riesgo de payload (ambos leen `UploadFile` completo dentro de la Lambda), simplemente no se habían probado con lotes grandes todavía.

**Scope:** Backend (`api/routers/`, `api/worker_handler.py`, nuevo endpoint compartido de presign), frontend (`taxops-web/app/(app)/{facturas,exogenas}/page.tsx`, helper de upload compartido), Terraform (lifecycle rule nueva en `infra/modules/storage/`). Renta se beneficia del endpoint compartido pero su router (`renta_documentos.py`) ya sube a S3 del lado del backend — este spec solo migra Facturas y Exógenas a subir directo desde el navegador; extender Renta al mismo patrón queda fuera de alcance (no está roto hoy, es deuda a considerar después).

---

## Arquitectura

```
Frontend                    API Lambda                  S3              SQS/Worker/DynamoDB
   │                            │                         │                     │
   │─POST /uploads/presign─────>│                         │                     │
   │  {contexto, archivos[]}    │                         │                     │
   │<──N presigned PUT URLs─────│                         │                     │
   │                            │                         │                     │
   │──────PUT (bytes) directo a S3, uno por archivo───────>│                     │
   │                            │                         │                     │
   │─POST /{modulo}/process─────>│                         │                     │
   │  {s3_keys[]}               │──(Facturas: lee S3,     │                     │
   │                            │   procesa, responde)────>│                     │
   │                            │──(Exógenas: enqueue SQS──────────────────────>│
   │<───resultado (Facturas)────│   {tipo:"exogenas",...})│              worker procesa,
   │<───{job_id} (Exógenas)─────│                         │              actualiza DynamoDB
   │                            │                         │                     │
   │──GET /exogenas/jobs/{id}──>│ (polling cada 3s)       │                     │
   │<──{status,progreso}────────│                         │                     │
```

## Componentes

### 1. `POST /uploads/presign` (nuevo, compartido)

**Request:**
```json
{
  "contexto": "facturas" | "exogenas",
  "archivos": [{"filename": "factura.pdf", "content_type": "application/pdf"}]
}
```

**Response:**
```json
{
  "uploads": [
    {"filename": "factura.pdf", "s3_key": "uploads/facturas/{org_id}/{uuid}/factura.pdf", "url": "https://...", "fields": {"key": "...", "policy": "...", "x-amz-signature": "...", "...": "..."}}
  ]
}
```

- **Corrección tras spec review — hallazgo serio, no cosmético.** La versión original de este spec asumía que un presigned **PUT** URL (`generate_presigned_url("put_object", ...)`) rechaza uploads que excedan un tamaño — falso: un PUT presignado con SigV4 no lleva ninguna restricción de tamaño, S3 acepta cualquier `Content-Length` hasta que expire la URL. Y ni Facturas ni Exógenas tienen hoy ningún chequeo de tamaño server-side (solo Renta, vía `_MAX_MB=20`) — bajo el diseño original, este spec habría dejado a Facturas/Exógenas **sin ningún límite real de tamaño** (solo un chequeo de `File.size` en JS, trivialmente evadible pegándole directo a la URL firmada con curl/Postman), quitando la única protección que hoy da el límite de 6MB de Lambda, sin reemplazarla — una regresión real de costo/DoS en un spec que existe justamente para arreglar un problema de tamaño de uploads.

  **Fix:** se usa `generate_presigned_post` (no `generate_presigned_url`) con una condición `["content-length-range", 0, max_bytes]` en la policy — S3 rechaza el upload en el momento (`400 EntityTooLarge`) si excede el límite, exigido por el servicio mismo, no por confianza en el cliente. Esto cambia el mecanismo de subida de un `PUT` simple a un POST `multipart/form-data` con los campos firmados que devuelve la policy — el progreso de subida (`XMLHttpRequest.upload.onprogress`) se sigue pudiendo trackear igual, no se pierde nada de UX por el cambio.
- `max_bytes` por `contexto`: se define un límite explícito nuevo para Facturas y Exógenas (no existía ninguno hoy) — mismo valor que ya usa Renta, **20MB por archivo**, por consistencia entre los 3 módulos salvo que se decida diferenciar más adelante
- Valida tipo permitido según `contexto` (lista específica por módulo — reusar el `_ALLOWED` set que ya existe en `exogenas.py`, y definir uno equivalente para Facturas si no existe todavía)
- Policy con expiración de 5 minutos
- `s3_key` incluye `org_id` del usuario autenticado (aislamiento multi-tenant) y un `uuid` para evitar colisiones de nombre
- Vive en un nuevo router `api/routers/uploads.py`, usa boto3 `generate_presigned_post` sobre `taxops-job-artifacts-prod` — sin llamada a AWS al generar la policy, sin costo

### 2. Frontend — helper de upload compartido

Nuevo `taxops-web/lib/directUpload.ts`: recibe `File[]` + contexto, llama a `/uploads/presign`, sube cada archivo a S3 vía `XMLHttpRequest` con un POST `multipart/form-data` (campos `fields` de la policy + el archivo — no un `PUT` simple, ver corrección en §1) — sigue permitiendo progreso real con `upload.onprogress` (`fetch` no lo soporta), devuelve `{filename, s3_key, error?}[]`. Usado por las páginas de Facturas y Exógenas.

### 3. Facturas (`POST /invoices/process`)

- Cambia el body de `files: UploadFile` a `s3_keys: list[str]` — el request deja de ser `multipart/form-data` y pasa a JSON puro; `ingresos_json` (hoy un `Form(...)` junto a `files`) se mueve a un campo normal del mismo body JSON (`ingresos: list[...]`, ya no un string a parsear con `json.loads`, el parseo lo hace FastAPI/Pydantic directo)
- Descarga cada archivo de S3 dentro de la Lambda. **Corrección tras spec review:** `services/renta/storage.download_from_s3` NO sirve tal cual — está hardcodeado a `Bucket=settings.S3_BUCKET_RENTA_DOCS` (`taxops-renta-docs-prod`), sin parámetro de bucket, y el presign (§1) siempre firma contra `taxops-job-artifacts-prod` (bucket distinto). Reusarlo sin modificar apuntaría al bucket equivocado y fallaría en cada request. En vez de forzar una abstracción compartida para una operación de 3 líneas, Facturas hace su propio `boto3.client("s3").get_object(Bucket=settings.S3_BUCKET_JOB_ARTIFACTS, Key=s3_key)` inline — no se toca `services/renta/storage.py` (cero riesgo de regresión en Renta, que ya funciona)
- **Sin cambio de UX** — sigue respondiendo el resultado completo en la misma llamada (rápido, sin OCR pesado, no hay riesgo real de timeout de 60s)

### 4. Exógenas — migración completa a async

- `POST /exogenas/process`: recibe `s3_keys`, crea job en DynamoDB (`core.job_store.put_job`, mismo store que ya usa Renta), manda un mensaje a la SQS existente (`taxops-jobs-prod`) con `{"tipo": "exogenas", "job_id", "org_id", "s3_keys": [...]}`, responde `{job_id}` de inmediato
- `GET /exogenas/jobs/{job_id}` (nuevo — reemplaza el endpoint SSE real, que es `GET /exogenas/stream/{job_id}`, **corrección tras spec review**: el spec original decía por error `/exogenas/status/{job_id}`, que no existe en el código actual): lee de DynamoDB vía `job_store.get_job`. Cuando `status == "done"`, además descarga el resultado completo desde S3 (ver punto de `df_detalle`/`df_1003` más abajo) y lo devuelve embebido en la misma respuesta — mismo contrato que consumía el frontend desde el payload `"done"` del SSE, solo que ahora llega por polling en vez de streaming
- **Corrección tras spec review — `worker_handler.py` NO despacha por tipo hoy.** `handler()` llama `_process_batch(body)` sin condicional alguno para cada mensaje SQS, y el mensaje que arma `renta_documentos.py` no tiene ninguna clave `"tipo"`. Este spec introduce el dispatch por primera vez: `tipo = body.get("tipo", "renta")` (default `"renta"` preserva compatibilidad con mensajes ya en vuelo/existentes, sin tener que tocar `renta_documentos.py`), luego `if tipo == "renta": _process_renta_batch(body) elif tipo == "exogenas": _process_exogenas_batch(body)`. La lógica de Renta que hoy vive inline en `_process_batch` se renombra a `_process_renta_batch` sin cambiar su comportamiento.
- **Nuevo:** `services/exogenas/job_processor.py` (mirror de `services/renta/job_processor.py` — mismo patrón de boundary ya establecido en el proyecto, con una diferencia real de firma — ver corrección abajo) contiene `_process_exogenas_batch`:
  1. Descarga cada `s3_key` (bytes)
  2. **Corrección tras spec review — `extract_many` necesita un path de archivo, no bytes.** A diferencia de Renta (`services/renta/ocr_agent.extract_text(file_bytes, filename, mime_type)`, que sí trabaja directo sobre bytes), la firma real de la función reutilizable de Exógenas es `exogenas.extractor.extract_many(path: str | Path)` — espera un path en filesystem. Un mirror literal del patrón de Renta (bytes → función de extracción directo) rompería de inmediato. Se escribe cada archivo descargado a un tmp file en `/tmp` (mismo patrón que ya usa hoy el endpoint SSE que se elimina: `tempfile.mkdtemp()` + `dest.open("wb")`), se llama `extract_many(path)` sobre ese path, y se limpia el tmpdir al terminar (o en `finally` si falla)
  3. La lógica reutilizable en sí es `exogenas.extractor.extract_many` — **corrección tras spec review**: `extract_one.py` es solo el wrapper CLI de subprocess que se elimina, no la lógica de extracción; ya no hace falta el subprocess aislado porque el worker Lambda ya es su propio proceso, no compite con la API
  4. Agrega resultados (`df_1003`, `df_detalle`), sube el resultado combinado como JSON a S3 bajo `uploads/results/exogenas/{job_id}.json` (**corrección tras spec review**: debe vivir bajo el prefijo `uploads/` para heredar el lifecycle de 3 días de §6 — una ruta bajo `job-artifacts/results/...` sin ese prefijo no calzaría con esa regla y quedaría bajo el lifecycle de 30 días por error)
  5. Actualiza el job en DynamoDB con `{"status": "done", "result_s3_key": "..."}` — **nunca el resultado completo directo en el item de DynamoDB** (ver siguiente punto)
- Se elimina: el streaming SSE (`StreamingResponse` en `/exogenas/stream/{job_id}`), el subprocess aislado, y el dict `_pending` module-level
- **Trade-off aceptado, no gratis:** el subprocess aislado que se elimina existía para que un archivo colgado en OCR no tumbara el proceso completo. Sin él, la única red de seguridad que queda es el `timeout` interno de `pytesseract` en cada llamada a `image_to_string` (ya presente en `exogenas/extractor.py`) — más angosta que el aislamiento a nivel de proceso que había antes. Se acepta el trade-off porque el worker Lambda en sí ya es su propio proceso aislado (un batch colgado no afecta a la API), pero vale la pena tenerlo explícito en vez de asumirlo

### 4.1. Dónde vive `df_detalle`/`df_1003` tras el job — hueco encontrado en spec review

Hoy, `POST /exogenas/export` recibe `df_1003` **y** `df_detalle` directo del frontend, que los tenía en memoria desde el payload `"done"` del SSE — `df_detalle` nunca se persiste en DB (solo `df_1003` vía `insert_exogenas_batch`). Con polling ya no hay ese payload disponible en el mismo request/response.

**Decisión:** el worker sube el resultado combinado (`{"df_1003": [...], "df_detalle": [...]}`) como un único JSON a S3 bajo `uploads/results/exogenas/{job_id}.json` (mismo prefijo `uploads/` → mismo lifecycle de 3 días — es dato derivado temporal, no el documento fuente). El job en DynamoDB solo guarda la referencia (`result_s3_key`), evitando el límite de 400KB por item de DynamoDB — justo el caso (lotes grandes, 41+ archivos) que motivó este spec. `GET /exogenas/jobs/{job_id}` descarga y embebe ese JSON en la respuesta cuando el job está `done` (mismo patrón "proxy vía API" que ya usa `renta_documentos.preview_documento` para servir contenido de S3 sin exponer URLs firmadas de lectura al frontend). El frontend sigue llamando `/exogenas/export` exactamente igual que hoy, sin cambios en ese endpoint.

### 5. Frontend de Exógenas

- Cambia de consumir `EventSource` (SSE) a: subir vía `directUpload.ts` → llamar `/exogenas/process` con los `s3_keys` → polling cada 3s contra `/exogenas/jobs/{job_id}` — mismo patrón visual/UX que ya usa la página de Renta (barra de progreso, lista de completados/pendientes)

### 5.1. Config/env var faltante — encontrado en spec review

Ni `api/core/config.py` (`Settings` solo tiene `S3_BUCKET_RENTA_DOCS`) ni `local.lambda_env` en `infra/modules/lambda-api/main.tf` (compartido entre API y worker, confirmado en `worker.tf`) exponen el nombre del bucket `job-artifacts` como env var — aunque el rol IAM ya tiene permiso sobre ambos buckets (`s3_bucket_arns`). El endpoint de presign (§1), Facturas (§3) y el nuevo `job_processor.py` de Exógenas (§4) necesitan este nombre.

**Se agrega:**
- `Settings.S3_BUCKET_JOB_ARTIFACTS: str` en `api/core/config.py`, mismo patrón que `S3_BUCKET_RENTA_DOCS`
- `S3_BUCKET_JOB_ARTIFACTS = var.s3_bucket_job_artifacts` en `local.lambda_env` (`infra/modules/lambda-api/main.tf`), nueva variable del módulo, wireada desde `module.storage.job_artifacts_bucket` en el root — mismo patrón que ya existe para `s3_bucket_renta_docs`

### 6. Terraform — lifecycle rule + CORS (nuevo, encontrado en spec review)

En `infra/modules/storage/main.tf`, nueva regla en `aws_s3_bucket_lifecycle_configuration.job_artifacts` (además de la que ya existe para `expire-old-exports`, 30 días, `filter {}` bucket-wide):

```hcl
rule {
  id     = "expire-temp-uploads"
  status = "Enabled"
  filter { prefix = "uploads/" }
  expiration { days = 3 }
}
```

La regla existente (`expire-old-exports`, 30 días, sin filtro de prefijo) también matchea objetos bajo `uploads/` — cuando dos reglas de expiración se solapan, S3 aplica la más corta, así que el resultado neto es el deseado (3 días para `uploads/`). Verificar este comportamiento durante la implementación (aplicar y confirmar con un objeto de prueba), no asumirlo ciegamente.

Storage class: **Standard** (no IA/One Zone-IA — para objetos que se borran en días, esos tiers salen más caros por el cargo mínimo de 30 días de storage).

**CORS — bloqueante, faltaba en la versión original del spec.** El `PUT` directo desde el navegador a S3 no funciona sin una configuración CORS en el bucket (el preflight `OPTIONS` falla si no está). Nuevo recurso:

```hcl
resource "aws_s3_bucket_cors_configuration" "job_artifacts" {
  bucket = aws_s3_bucket.job_artifacts.id

  cors_rule {
    allowed_methods = ["PUT"]
    allowed_origins = ["https://app.taxopsapp.com", "http://localhost:3000"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
```

**Corrección tras spec review — NO copiar `ALLOWED_ORIGINS` de la Lambda tal cual.** El valor real de `ALLOWED_ORIGINS` hoy (`infra/environments/prod/main.tf`, `local.allowed_origins`) es `"https://taxops-app.vercel.app,https://main.d2mechz6r82w9f.amplifyapp.com,http://localhost:3000"` — todavía apunta al dominio *default* de Amplify, no a `app.taxopsapp.com` (quedó así desde antes de que existiera el dominio propio del frontend, Chunk 6 tardío). Ese es un gap preexistente, independiente de este spec.

Lo que sí importa acá: el CORS de S3 lo evalúa el **navegador real del usuario**, que carga `app.taxopsapp.com` (el dominio real, confirmado funcionando en producción) — no tiene sentido copiar un valor que ya está desactualizado. Se usa el dominio real directamente.

**Relacionado, no bloqueante pero barato de arreglar en el mismo PR:** ya que se está tocando esta parte de la infra, actualizar también `local.allowed_origins` en `infra/environments/prod/main.tf` para reemplazar el dominio default de Amplify por `app.taxopsapp.com` — un cambio de una línea, cierra el gap preexistente de paso.

## Manejo de errores

- **Falla un `PUT` a S3** (red, etc.): se marca ese archivo específico como fallido en el frontend; el usuario puede reintentar solo ese archivo antes de llamar a `/process`. No se bloquea el resto del lote.
- **Falla `/uploads/presign` para algún archivo** (tipo no permitido): esa entrada se excluye de la respuesta con un motivo; el resto de archivos válidos sigue.
- **Facturas — falla la descarga de S3 al procesar:** intención es preservar el comportamiento actual del módulo (error reportado por archivo, no aborta el lote completo). **Pregunta abierta, no confirmada todavía** — verificar contra `services/processor.py` durante la implementación antes de asumir que ya funciona así; si no es el caso, ajustar en el mismo PR en vez de heredar el comportamiento incorrecto.
- **Exógenas — falla un documento en el worker:** mismo manejo que ya tiene Renta (el job registra el error de ese documento específico, el worker sigue con el resto, no se cae la invocación completa).

## Testing

- `tests/test_uploads_presign.py` (nuevo) — moto-mocked S3, cubre contexto válido/inválido, tipo de archivo rechazado
- `tests/test_worker_handler.py` — extender cubriendo el dispatch nuevo (`tipo` ausente → default `"renta"`, `tipo == "exogenas"` → `_process_exogenas_batch`), moto-mocked SQS/S3/DynamoDB
- `tests/test_exogenas_job_processor.py` (nuevo, mirror de como sea que se llame el equivalente de Renta) — cubre `services/exogenas/job_processor.py`: descarga de S3, extracción, subida del resultado combinado, actualización del job en DynamoDB con `result_s3_key`
- `tests/test_invoices.py` (o el archivo que ya cubra `invoices.py`) — actualizar para el nuevo flujo `s3_keys` en vez de `UploadFile`
- Suite de extracción de exógenas (`exogenas/extractor.py`, 12+ layouts) — **sin cambios**, la lógica de extracción no se toca, solo cómo se invoca
- Frontend (`directUpload.ts`, CORS): fuera de alcance de tests automatizados — se verifica manualmente contra el bucket real durante la implementación (mismo criterio que ya se usó para verificar Chunk 5/6 en producción)

## No incluido (fuera de alcance de este spec)

- Migrar Renta al mismo patrón de upload directo (ya usa S3 del lado del backend, no está roto — deuda a evaluar después si algún día se prueba con lotes grandes)
- Cambiar el límite de tamaño por archivo (`_MAX_MB`) — se mantienen los límites que ya existen por módulo
- Cualquier cambio a la lógica de extracción/OCR en sí (`exogenas/extractor.py`, `pipeline/`, `services/renta/`)
- CloudFront/Lambda Function URL en modo streaming (`InvokeMode=RESPONSE_STREAM`) — se descarta como alternativa, polling es más simple y ya probado con Renta
