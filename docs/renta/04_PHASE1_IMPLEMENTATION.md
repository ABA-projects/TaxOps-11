# TaxOps Renta — Plan de Implementación Fase 1 (MVP)

> Guía paso a paso para la primera fase. Stack: FastAPI + Next.js 15 + PostgreSQL + GCS + Groq.
> Sin cambios de infra. Deploy a Cloud Run existente.

---

## Semana 1 — Backend: DB + CRUD contribuyentes

### Día 1-2: Migración DB + Schemas

**Tareas:**
1. Agregar tablas a `db/init.sql`:
   - `contribuyentes`
   - `renta_documentos`
   - `renta_declaraciones`
   - `reglas_tributarias` + datos semilla 2025
   - `renta_jobs`
   - Extensión `vector` + tabla `renta_embeddings` (opcional semana 3)

2. Crear `api/schemas_renta.py` con:
   - `ContribuyenteCreate`, `ContribuyenteOut`
   - `DocumentoOut`
   - `DeclaracionOut`
   - `RiesgoOut`

3. Correr migración en Neon: `python manage.py init-db` (o agregar script `migrate-renta`)

**Archivos a crear/modificar:**
```
db/init.sql                    → agregar nuevas tablas al final
api/schemas_renta.py           → nuevo archivo
```

---

### Día 3-4: CRUD API contribuyentes

**Tareas:**
1. Crear `api/routers/renta.py`:
   - `GET /renta/contribuyentes`
   - `POST /renta/contribuyentes`
   - `GET /renta/contribuyentes/{id}`
   - `PUT /renta/contribuyentes/{id}`
   - `DELETE /renta/contribuyentes/{id}`
   - `GET /renta/contribuyentes/{id}/info`

2. Registrar router en `api/main.py`:
   ```python
   from routers.renta import router as renta_router
   app.include_router(renta_router, prefix="/renta", tags=["Renta"])
   ```

3. Agregar función helper `db/database.py`:
   - `get_contribuyentes(org_id, filtros)`
   - `get_contribuyente(id, org_id)`
   - `insert_contribuyente(data, org_id)`

**Archivos:**
```
api/routers/renta.py           → nuevo
api/main.py                    → registrar router
db/database.py                 → helpers nuevos
```

---

### Día 5: Test API + ajustes

- Probar todos los endpoints en `/docs`
- Ajustar validaciones Pydantic
- Verificar que org_id se filtra correctamente (multi-tenant)

---

## Semana 2 — Backend: Upload + OCR + Clasificación

### Día 1-2: Storage GCS + Upload endpoint

**Tareas:**
1. Instalar `google-cloud-storage` en `api/requirements.txt`

2. Crear `api/services/renta/storage.py`:
   ```python
   def upload_to_gcs(file_bytes, org_id, contrib_id, año, filename) -> str:
       """Sube a GCS, retorna gs://taxops-docs/.../filename"""

   def get_signed_url(gcs_key: str, expiry_hours=1) -> str:
       """URL prefirmada para preview"""
   ```

3. Crear `api/routers/renta_documentos.py`:
   - `POST /renta/contribuyentes/{id}/documentos` — upload + enqueue
   - `GET /renta/contribuyentes/{id}/documentos/status/{job_id}`
   - `GET /renta/contribuyentes/{id}/documentos`
   - `GET /renta/contribuyentes/{id}/documentos/{doc_id}/preview`
   - `DELETE /renta/contribuyentes/{id}/documentos/{doc_id}`

**Archivos:**
```
api/services/renta/storage.py           → nuevo
api/routers/renta_documentos.py         → nuevo
api/requirements.txt                    → google-cloud-storage
```

---

### Día 3-4: OCRAgent + ClassifierAgent

**Tareas:**
1. Crear `api/services/renta/ocr_agent.py`:
   ```python
   def extract_text(gcs_key: str, mime_type: str) -> str:
       """
       Prioridad:
       1. pdfplumber (PDF digital)
       2. Groq llama-3.2-vision (imagen/PDF escaneado)
       3. pytesseract timeout=60s (fallback)
       """
   ```

2. Crear `api/services/renta/classifier_agent.py`:
   ```python
   def classify_document(text: str, filename: str) -> dict:
       """
       Llama Groq llama-3.3-70b para:
       - Determinar categoria (identificacion/ingresos/bancos/...)
       - Extraer campos clave según categoría
       - Calcular confianza (0-1)
       Retorna: {categoria, carpeta_virtual, confianza, datos_extraidos}
       """

   PROMPT_CLASIFICACION = '''
   Eres experto en documentos tributarios colombianos.
   Analiza este documento y determina:
   1. Su categoría (identificacion|ingresos|bancos|patrimonio|bienes|salud|pensiones|tributario|otros)
   2. Los campos clave según la categoría
   3. Tu nivel de confianza (0-1)

   Categorías y campos a extraer:
   - ingresos: {empleador, nit_empleador, salario_mensual, total_ingresos_año, total_retencion, año}
   - bancos: {entidad, nit_entidad, saldo_dic31, promedio_año, año}
   - patrimonio: {tipo, entidad, valor, fecha}
   - pensiones: {fondo, nit_fondo, saldo, aportes_año}
   ...

   Responde SOLO JSON: {"categoria": "...", "confianza": 0.95, "datos_extraidos": {...}}
   '''
   ```

3. Crear `api/services/renta/job_processor.py`:
   ```python
   def process_documento_job(job_id: str, doc_id: str) -> None:
       """
       1. Descargar de GCS
       2. OCRAgent → texto
       3. ClassifierAgent → categoria + campos
       4. UPDATE renta_documentos
       5. UPDATE renta_jobs progreso
       """
   ```

**Archivos:**
```
api/services/renta/ocr_agent.py         → nuevo
api/services/renta/classifier_agent.py  → nuevo
api/services/renta/job_processor.py     → nuevo
```

---

### Día 5: Jobs executor (mismo patrón que exógenas)

Reutilizar el patrón `ThreadPoolExecutor` de `api/routers/exogenas.py`:

```python
# renta_documentos.py
_executor = ThreadPoolExecutor(max_workers=1)  # 1 job a la vez (OOM prevention)
_jobs: dict[str, dict] = {}

@router.post("/contribuyentes/{id}/documentos")
async def upload_documentos(id: str, files: list[UploadFile], user=Depends(get_current_user)):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "progreso": 0, "completados": 0, "total": len(files)}
    _executor.submit(_run_upload_job, job_id, id, files, user["org_id"])
    return {"job_id": job_id, "total": len(files)}
```

---

## Semana 3 — Frontend: UI de casos

### Día 1-2: Lista de contribuyentes

**Página:** `taxops-web/app/renta/page.tsx`

Componentes:
- `ContribuyenteTable` — tabla con filtros (año, estado, responsable)
- `ContribuyenteCard` — estado + completitud %
- `NuevoContribuyenteModal` — formulario creación

---

### Día 3-4: Vista de caso (página principal)

**Página:** `taxops-web/app/renta/[id]/page.tsx`

Layout:
```
┌─ Header: nombre + estado + barra de acciones ──────────────────┐
├─ Sidebar (20%): árbol de carpetas virtuales                     │
├─ Main (80%): lista de documentos de la carpeta seleccionada     │
└─ Footer: resumen tributario (ingresos, impuesto, saldo)         │
```

Componentes:
- `ActionBar` — Editar | Subir | Excel | F210 | Actualizar | Info
- `FolderTree` — carpetas con badge de conteo y estado
- `DocumentList` — cards con preview thumbnail + estado OCR
- `UploadDropzone` — drag & drop con progress bar polling

---

### Día 5: Preview de documentos + polling OCR

- `DocumentPreview` — iframe PDF / `<img>` para imágenes
- SSE polling `/documentos/status/{job_id}` cada 2s
- Badge de categoría con color por tipo
- Alerta cuando confianza < 85% (pedir revisión manual)

---

## Semana 4 — Motor de Declaración (básico)

### Día 1-2: TaxRulesAgent + Motor de cálculo

**Archivo:** `api/services/renta/tax_engine.py`

```python
def calcular_declaracion(contribuyente_id: str, año: int, db) -> dict:
    """
    1. Cargar reglas del año desde reglas_tributarias
    2. Leer datos_extraidos de todos los documentos del contribuyente
    3. Consolidar por categoria:
       - ingresos: suma total_ingresos_año de docs categoria=ingresos
       - retenciones: suma total_retencion de todos los docs
       - patrimonio_bruto: suma valor de docs categoria=patrimonio+bienes
       - deducciones: suma de salud + pensiones (límites según reglas)
    4. Calcular impuesto según tabla Art 241
    5. Retornar dict con todos los campos de renta_declaraciones
    """
```

---

### Día 3-4: RiskAgent básico

**Archivo:** `api/services/renta/risk_agent.py`

Checks básicos MVP:
- Suma ingresos documentos vs dato empleador (si hay exógenas)
- Documentos en error OCR (advertencia)
- Carpetas sin documentos para año declarado (info)
- Retenciones > impuesto a cargo (saldo favor — revisar)

---

### Día 5: Endpoint `/declaracion/calcular` + UI resumen

- Botón "Calcular" en frontend dispara el motor
- Panel lateral muestra: ingresos, deducciones, impuesto, saldo
- Colores: verde=favor, rojo=pagar

---

## Semana 5-6 — Form210 + Excel + Pulido

- `Form210Agent`: mapear campos calculados al formulario 210 DIAN
- Export Excel con 6 hojas (ver API design)
- UI polish: states de carga, error handling, responsive
- Deploy final a Cloud Run + smoke testing

---

## Checklist de variables de entorno nuevas

```bash
# GCS (si no está ya)
GCP_BUCKET_NAME=taxops-docs
GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json  # O usar Workload Identity en Cloud Run

# Ya existentes (no cambiar)
GROQ_API_KEY=...
DATABASE_URL=...
SECRET_KEY=...
```

En Cloud Run, agregar al `--set-env-vars` del workflow:
```
GCP_BUCKET_NAME=taxops-docs
```

---

## Dependencias nuevas a agregar

```txt
# api/requirements.txt
google-cloud-storage>=2.16
reportlab>=4.2          # generación PDF Formulario 210
pypdf>=4.0              # manipulación PDF
openpyxl>=3.1           # ya existe — verificar versión
pgvector>=0.3           # cliente pgvector para embeddings (semana 3+)
```

---

## Prioridades absolutas para el primer día

1. ✅ Crear tablas en DB (`db/init.sql`)
2. ✅ `POST /renta/contribuyentes` + `GET /renta/contribuyentes`
3. ✅ `GET /renta/contribuyentes/{id}` con carpetas vacías
4. ✅ Página `/renta` en Next.js con tabla + modal crear
5. ✅ Deploy y verificar en producción

Todo lo demás puede esperar. El CRUD de contribuyentes es el núcleo sobre el que se construye todo.
