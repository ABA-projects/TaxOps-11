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

### 2. Frontend — helper de upload compartido

Nuevo `taxops-web/lib/directUpload.ts`: recibe `File[]` + contexto, llama a `/uploads/presign`, hace `PUT` directo a S3 por archivo vía `XMLHttpRequest` (permite progreso real con `upload.onprogress`, `fetch` no lo soporta), devuelve `{filename, s3_key, error?}[]`. Usado por las páginas de Facturas y Exógenas.

### 3. Facturas (`POST /invoices/process`)

- Cambia el body de `files: UploadFile` a `s3_keys: list[str]`
- Descarga cada archivo de S3 dentro de la Lambda (reutiliza el patrón de `services/renta/storage.download_from_s3`), procesa igual que hoy
- **Sin cambio de UX** — sigue respondiendo el resultado completo en la misma llamada (rápido, sin OCR pesado, no hay riesgo real de timeout de 60s)

### 4. Exógenas — migración completa a async

- `POST /exogenas/process`: recibe `s3_keys`, crea job en DynamoDB (`core.job_store.put_job`, mismo store que ya usa Renta), manda un mensaje a la SQS existente (`taxops-jobs-prod`) con `{"tipo": "exogenas", "job_id", "org_id", "s3_keys": [...]}`, responde `{job_id}` de inmediato
- `GET /exogenas/jobs/{job_id}` (nuevo — reemplaza `/exogenas/status/{job_id}` basado en SSE): lee de DynamoDB vía `job_store.get_job`, mismo shape de respuesta que el endpoint equivalente de Renta
- `api/worker_handler.py`: el handler ya despacha por tipo de mensaje (hoy solo maneja jobs de Renta) — se agrega una rama `elif body["tipo"] == "exogenas"` que llama la lógica de extracción existente (la misma que hoy corre en `extract_one.py` vía subprocess), actualizando progreso en DynamoDB con `job_store.put_job`/`update_job` en vez del dict `_pending` en memoria
- Se elimina: el streaming SSE (`StreamingResponse`), el subprocess aislado (`extract_one.py` deja de invocarse vía `subprocess`, la extracción corre directo dentro del worker Lambda — ya está aislado por ser su propio proceso Lambda, no compite con la API), y el dict `_pending` module-level

### 5. Frontend de Exógenas

- Cambia de consumir `EventSource` (SSE) a: subir vía `directUpload.ts` → llamar `/exogenas/process` con los `s3_keys` → polling cada 3s contra `/exogenas/jobs/{job_id}` — mismo patrón visual/UX que ya usa la página de Renta (barra de progreso, lista de completados/pendientes)

### 6. Terraform — lifecycle rule nueva

En `infra/modules/storage/main.tf`, nueva regla en `aws_s3_bucket_lifecycle_configuration.job_artifacts` (además de la que ya existe para `expire-old-exports`, 30 días):

```hcl
rule {
  id     = "expire-temp-uploads"
  status = "Enabled"
  filter { prefix = "uploads/" }
  expiration { days = 3 }
}
```

Storage class: **Standard** (no IA/One Zone-IA — para objetos que se borran en días, esos tiers salen más caros por el cargo mínimo de 30 días de storage).

## Manejo de errores

- **Falla un `PUT` a S3** (red, etc.): se marca ese archivo específico como fallido en el frontend; el usuario puede reintentar solo ese archivo antes de llamar a `/process`. No se bloquea el resto del lote.
- **Falla `/uploads/presign` para algún archivo** (tipo no permitido): esa entrada se excluye de la respuesta con un motivo; el resto de archivos válidos sigue.
- **Facturas — falla la descarga de S3 al procesar:** se preserva el comportamiento actual del módulo (error reportado por archivo, no aborta el lote completo — a verificar contra `services/processor.py` durante la implementación, sin cambiarlo si ya es correcto).
- **Exógenas — falla un documento en el worker:** mismo manejo que ya tiene Renta (el job registra el error de ese documento específico, el worker sigue con el resto, no se cae la invocación completa).

## Testing

- `tests/test_uploads_presign.py` (nuevo) — moto-mocked S3, cubre contexto válido/inválido, tipo de archivo rechazado
- `tests/test_worker_handler.py` — extender con el branch `tipo == "exogenas"` (moto-mocked SQS/S3/DynamoDB)
- `tests/test_invoices.py` (o el archivo que ya cubra `invoices.py`) — actualizar para el nuevo flujo `s3_keys` en vez de `UploadFile`
- Suite de extracción de exógenas (`exogenas/extractor.py`, 12+ layouts) — **sin cambios**, la lógica de extracción no se toca, solo cómo se invoca

## No incluido (fuera de alcance de este spec)

- Migrar Renta al mismo patrón de upload directo (ya usa S3 del lado del backend, no está roto — deuda a evaluar después si algún día se prueba con lotes grandes)
- Cambiar el límite de tamaño por archivo (`_MAX_MB`) — se mantienen los límites que ya existen por módulo
- Cualquier cambio a la lógica de extracción/OCR en sí (`exogenas/extractor.py`, `pipeline/`, `services/renta/`)
- CloudFront/Lambda Function URL en modo streaming (`InvokeMode=RESPONSE_STREAM`) — se descarta como alternativa, polling es más simple y ya probado con Renta
