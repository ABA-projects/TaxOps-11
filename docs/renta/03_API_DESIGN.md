# TaxOps Renta — Diseño de APIs

> Contratos de endpoints. Implementar en `api/routers/renta.py` y `api/routers/renta_documentos.py`.

---

## Schemas Pydantic (resumen)

```python
# schemas_renta.py

class ContribuyenteCreate(BaseModel):
    tipo_doc: Literal["13", "22", "41"] = "13"
    numero_doc: str
    nombre_completo: str
    email: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    año_gravable: int
    responsable_id: str | None = None
    observaciones: str | None = None

class ContribuyenteOut(ContribuyenteCreate):
    id: str
    org_id: str
    estado: str
    completitud: int           # 0-100%
    docs_total: int
    docs_pendientes: int
    created_at: datetime
    updated_at: datetime

class DocumentoOut(BaseModel):
    id: str
    filename: str
    categoria: str
    carpeta_virtual: str
    confianza_clasificacion: float
    datos_extraidos: dict
    estado_ocr: str
    estado_validacion: str
    s3_url: str                # URL prefirmada 1h
    size_bytes: int
    created_at: datetime

class DeclaracionOut(BaseModel):
    id: str
    año_gravable: int
    patrimonio_bruto: float
    patrimonio_liquido: float
    ingresos_laborales: float
    rentas_capital: float
    rentas_no_laborales: float
    dividendos: float
    ganancias_ocasionales: float
    rentas_exentas: float
    deducciones: float
    retenciones: float
    impuesto_cargo: float
    saldo_pagar: float
    saldo_favor: float
    estado: str
    inconsistencias: list[dict]
    detalle_calculo: dict
    updated_at: datetime

class RiesgoOut(BaseModel):
    nivel: Literal["info", "advertencia", "critico"]
    codigo: str
    mensaje: str
    doc_ids: list[str]
```

---

## Endpoints — Contribuyentes

### `GET /renta/contribuyentes`
Lista contribuyentes de la organización.

**Query params:** `año_gravable`, `estado`, `responsable_id`, `q` (búsqueda nombre/doc), `limit=20`, `offset=0`

**Response:**
```json
{
  "contribuyentes": [ContribuyenteOut],
  "total": 45
}
```

---

### `POST /renta/contribuyentes`
Crea un nuevo contribuyente.

**Body:** `ContribuyenteCreate`

**Response:** `ContribuyenteOut`

---

### `GET /renta/contribuyentes/{id}`
Detalle completo con resumen tributario.

**Response:**
```json
{
  "contribuyente": ContribuyenteOut,
  "declaracion": DeclaracionOut | null,
  "carpetas": {
    "00_Identificacion": [DocumentoOut],
    "01_Ingresos": [DocumentoOut],
    ...
  },
  "riesgos": [RiesgoOut]
}
```

---

### `PUT /renta/contribuyentes/{id}`
Actualiza datos del contribuyente.

**Body:** `ContribuyenteCreate` (parcial)

---

### `DELETE /renta/contribuyentes/{id}`
Soft-delete (marca como eliminado, no borra GCS).

---

## Endpoints — Documentos

### `POST /renta/contribuyentes/{id}/documentos`
Upload de uno o múltiples archivos. Inicia procesamiento OCR + clasificación en background.

**Body:** `multipart/form-data` con `files[]`

**Tipos aceptados:** PDF, JPG, PNG, TIFF, XLSX, DOCX, XML, ZIP

**Response:**
```json
{
  "job_id": "uuid",
  "doc_ids": ["uuid1", "uuid2"],
  "total": 3
}
```

**Notas:**
- Archivos se suben directamente a GCS bajo `{org_id}/{contrib_id}/{año}/{uuid}/filename`
- Se encola job de OCR + clasificación por cada archivo
- ZIP se descomprime en memoria y se procesa cada archivo interno

---

### `GET /renta/contribuyentes/{id}/documentos/status/{job_id}`
Estado del job de procesamiento (polling cada 2s desde frontend).

**Response:**
```json
{
  "status": "processing",
  "progreso": 45,
  "completados": 2,
  "total": 5,
  "archivos": [
    {"doc_id": "uuid", "filename": "cert.pdf", "estado": "completado", "categoria": "ingresos"},
    {"doc_id": "uuid", "filename": "extracto.pdf", "estado": "procesando"}
  ]
}
```

---

### `GET /renta/contribuyentes/{id}/documentos`
Lista documentos, opcionalmente filtrados por carpeta.

**Query params:** `carpeta`, `categoria`, `estado_ocr`

---

### `PUT /renta/contribuyentes/{id}/documentos/{doc_id}`
Corregir clasificación manual de un documento.

**Body:**
```json
{
  "categoria": "ingresos",
  "carpeta_virtual": "01_Ingresos",
  "datos_extraidos": {}
}
```

---

### `DELETE /renta/contribuyentes/{id}/documentos/{doc_id}`
Elimina documento de DB y GCS.

---

### `GET /renta/contribuyentes/{id}/documentos/{doc_id}/preview`
Devuelve URL prefirmada de GCS con TTL 1h para preview en frontend.

**Response:** `{"url": "https://storage.googleapis.com/..."}`

---

## Endpoints — Declaración

### `GET /renta/contribuyentes/{id}/declaracion`
Retorna la declaración actual (cálculo más reciente).

**Response:** `DeclaracionOut`

---

### `POST /renta/contribuyentes/{id}/declaracion/calcular`
Dispara el motor de cálculo completo. Job asíncrono.

**Response:** `{"job_id": "uuid"}`

El frontend hace polling en `/declaracion/calcular/status/{job_id}`.

---

### `PUT /renta/contribuyentes/{id}/declaracion`
Ajuste manual de valores por el contador.

**Body:** campos parciales de `DeclaracionOut`

---

### `GET /renta/contribuyentes/{id}/declaracion/formulario210`
Genera y retorna el PDF del Formulario 210 (borrador).

**Response:** `application/pdf` con `Content-Disposition: attachment`

---

### `GET /renta/contribuyentes/{id}/declaracion/excel`
Genera y retorna el workbook Excel consolidado.

**Hojas:**
1. `Resumen` — KPIs principales
2. `Ingresos` — detalle por fuente
3. `Patrimonio` — activos y pasivos
4. `Deducciones` — desglose
5. `Retenciones` — por retenedor
6. `Formulario_210` — mapeado al formulario

**Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

---

### `POST /renta/contribuyentes/{id}/reprocesar`
Re-ejecuta OCR + clasificación + cálculo sobre todos los documentos.

**Response:** `{"job_id": "uuid"}`

---

## Endpoints — Riesgos e Información

### `GET /renta/contribuyentes/{id}/riesgos`
Análisis de riesgos y alertas.

**Response:**
```json
{
  "score_riesgo": 42,           // 0-100
  "nivel": "advertencia",
  "completitud": 68,            // % documentos requeridos
  "docs_faltantes": ["Certificado EPS", "Extracto bancario diciembre"],
  "riesgos": [RiesgoOut],
  "alertas_vencimiento": [{"fecha": "2025-10-24", "descripcion": "Vencimiento declaración"}]
}
```

---

### `GET /renta/contribuyentes/{id}/info`
Panel de información rápida del caso.

**Response:**
```json
{
  "estado": "en_proceso",
  "completitud": 68,
  "docs_total": 12,
  "docs_completados": 8,
  "docs_error": 1,
  "ultima_actividad": "2025-05-30T14:22:00Z",
  "responsable": {"nombre": "Ana López", "email": "ana@firma.com"}
}
```

---

## Endpoints — Chatbot RAG

### `POST /renta/chat`
Chatbot tributario con contexto documental del contribuyente.

**Body:**
```json
{
  "mensaje": "¿Cuánto fue la retención de Bancolombia?",
  "contribuyente_id": "uuid",
  "historial": [{"rol": "user", "contenido": "..."}]
}
```

**Response:**
```json
{
  "respuesta": "Según el certificado bancario de Bancolombia...",
  "fuentes": [
    {"doc_id": "uuid", "filename": "extracto_banc.pdf", "fragmento": "..."}
  ]
}
```

---

## Endpoints — Reglas tributarias

### `GET /renta/reglas/{año}`
Ver parámetros tributarios del año.

Guard: `require_admin`

### `PUT /renta/reglas/{año}`
Actualizar reglas del año (nuevo año gravable).

Guard: `require_superadmin`

---

## Estructura de archivos backend

```
api/routers/
├── renta.py              # CRUD contribuyentes + declaración
├── renta_documentos.py   # Upload, OCR jobs, preview
└── renta_chat.py         # Chatbot RAG

api/services/
├── renta/
│   ├── ocr_agent.py          # Pipeline OCR multi-formato
│   ├── classifier_agent.py   # Clasificación documental LLM
│   ├── tax_engine.py         # Motor cálculo declaración
│   ├── tax_rules_agent.py    # Carga reglas desde DB
│   ├── risk_agent.py         # Detección inconsistencias
│   ├── form210_agent.py      # Generación Formulario 210
│   ├── excel_export.py       # Export workbook
│   └── rag_chat.py           # RAG sobre documentos
```
