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
    {"filename": "factura.pdf", "s3_key": "uploads/facturas/{org_id}/{uuid}/factura.pdf", "upload_url": "https://..."}
  ]
}
```

- Valida tipo permitido y no impone límite de tamaño en el presign en sí (S3 rechaza directo si el `PUT` excede lo firmado — la validación real de tamaño se hace del lado del cliente antes de subir, como ya hace Renta con `_MAX_MB`)
- URLs firmadas con expiración de 5 minutos
- `s3_key` incluye `org_id` del usuario autenticado (aislamiento multi-tenant) y un `uuid` para evitar colisiones de nombre
- Vive en un nuevo router `api/routers/uploads.py`, usa boto3 `generate_presigned_url` sobre `taxops-job-artifacts-prod` — sin llamada a AWS, sin costo
- **Corrección tras spec review:** el límite de tamaño (`_MAX_MB`) en Renta se valida hoy del lado del **servidor** (después de `await f.read()`, dentro de la Lambda), no del cliente — la referencia original a "como ya hace Renta con `_MAX_MB`" del lado cliente era incorrecta. Este spec valida tamaño client-side ANTES de subir (chequeo simple de `File.size` en el navegador, nuevo — no existe hoy en ningún módulo) para evitar gastar una subida completa a S3 en un archivo que se va a rechazar; el límite exacto por MB se reutiliza del que ya tiene cada módulo backend como defensa adicional server-side (doble validación, no solo una)

### 2. Frontend — helper de upload compartido

Nuevo `taxops-web/lib/directUpload.ts`: recibe `File[]` + contexto, llama a `/uploads/presign`, hace `PUT` directo a S3 por archivo vía `XMLHttpRequest` (permite progreso real con `upload.onprogress`, `fetch` no lo soporta), devuelve `{filename, s3_key, error?}[]`. Usado por las páginas de Facturas y Exógenas.

### 3. Facturas (`POST /invoices/process`)

- Cambia el body de `files: UploadFile` a `s3_keys: list[str]`
- Descarga cada archivo de S3 dentro de la Lambda. `services/renta/storage.download_from_s3` hace exactamente esto pero vive namespaced bajo `renta/` — se reutiliza tal cual vía import cruzado (aceptado a propósito, no vale la pena mover/renombrar un módulo de 3 funciones por esto), no se relocaliza a un paquete compartido
- **Sin cambio de UX** — sigue respondiendo el resultado completo en la misma llamada (rápido, sin OCR pesado, no hay riesgo real de timeout de 60s)

### 4. Exógenas — migración completa a async

- `POST /exogenas/process`: recibe `s3_keys`, crea job en DynamoDB (`core.job_store.put_job`, mismo store que ya usa Renta), manda un mensaje a la SQS existente (`taxops-jobs-prod`) con `{"tipo": "exogenas", "job_id", "org_id", "s3_keys": [...]}`, responde `{job_id}` de inmediato
- `GET /exogenas/jobs/{job_id}` (nuevo — reemplaza el endpoint SSE real, que es `GET /exogenas/stream/{job_id}`, **corrección tras spec review**: el spec original decía por error `/exogenas/status/{job_id}`, que no existe en el código actual): lee de DynamoDB vía `job_store.get_job`. Cuando `status == "done"`, además descarga el resultado completo desde S3 (ver punto de `df_detalle`/`df_1003` más abajo) y lo devuelve embebido en la misma respuesta — mismo contrato que consumía el frontend desde el payload `"done"` del SSE, solo que ahora llega por polling en vez de streaming
- **Corrección tras spec review — `worker_handler.py` NO despacha por tipo hoy.** `handler()` llama `_process_batch(body)` sin condicional alguno para cada mensaje SQS, y el mensaje que arma `renta_documentos.py` no tiene ninguna clave `"tipo"`. Este spec introduce el dispatch por primera vez: `tipo = body.get("tipo", "renta")` (default `"renta"` preserva compatibilidad con mensajes ya en vuelo/existentes, sin tener que tocar `renta_documentos.py`), luego `if tipo == "renta": _process_renta_batch(body) elif tipo == "exogenas": _process_exogenas_batch(body)`. La lógica de Renta que hoy vive inline en `_process_batch` se renombra a `_process_renta_batch` sin cambiar su comportamiento.
- **Nuevo:** `services/exogenas/job_processor.py` (mirror de `services/renta/job_processor.py` — mismo patrón de boundary ya establecido en el proyecto) contiene `_process_exogenas_batch`: descarga cada `s3_key`, corre la extracción (la misma lógica que hoy vive en `extract_one.py`, invocada directo — ya no hace falta el subprocess aislado porque el worker Lambda ya es su propio proceso, no compite con la API), agrega resultados (`df_1003`, `df_detalle`), sube el resultado combinado como JSON a S3 (`job-artifacts/results/exogenas/{job_id}.json`), y actualiza el job en DynamoDB con `{"status": "done", "result_s3_key": "..."}` — **nunca el resultado completo directo en el item de DynamoDB** (ver siguiente punto)
- Se elimina: el streaming SSE (`StreamingResponse` en `/exogenas/stream/{job_id}`), el subprocess aislado, y el dict `_pending` module-level

### 4.1. Dónde vive `df_detalle`/`df_1003` tras el job — hueco encontrado en spec review

Hoy, `POST /exogenas/export` recibe `df_1003` **y** `df_detalle` directo del frontend, que los tenía en memoria desde el payload `"done"` del SSE — `df_detalle` nunca se persiste en DB (solo `df_1003` vía `insert_exogenas_batch`). Con polling ya no hay ese payload disponible en el mismo request/response.

**Decisión:** el worker sube el resultado combinado (`{"df_1003": [...], "df_detalle": [...]}`) como un único JSON a S3 bajo el mismo prefijo `uploads/` (mismo lifecycle de 3 días — es dato derivado temporal, no el documento fuente). El job en DynamoDB solo guarda la referencia (`result_s3_key`), evitando el límite de 400KB por item de DynamoDB — justo el caso (lotes grandes, 41+ archivos) que motivó este spec. `GET /exogenas/jobs/{job_id}` descarga y embebe ese JSON en la respuesta cuando el job está `done` (mismo patrón "proxy vía API" que ya usa `renta_documentos.preview_documento` para servir contenido de S3 sin exponer URLs firmadas de lectura al frontend). El frontend sigue llamando `/exogenas/export` exactamente igual que hoy, sin cambios en ese endpoint.

### 5. Frontend de Exógenas

- Cambia de consumir `EventSource` (SSE) a: subir vía `directUpload.ts` → llamar `/exogenas/process` con los `s3_keys` → polling cada 3s contra `/exogenas/jobs/{job_id}` — mismo patrón visual/UX que ya usa la página de Renta (barra de progreso, lista de completados/pendientes)

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
    allowed_origins = ["https://app.taxopsapp.com", "https://taxops-app.vercel.app", "http://localhost:3000"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
```

Los mismos 3 orígenes que ya están en `ALLOWED_ORIGINS` de la Lambda (Chunk 6) — mantener sincronizados si alguno cambia (ej. al decomisionar Vercel en el Chunk 8, quitar ese origin de ambos lugares).

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
