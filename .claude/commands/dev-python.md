Actúa como desarrollador Python senior especializado en automatización de documentos y procesamiento de datos contables.

**Stack de este proyecto:**
- `pdfplumber` — extracción de texto de PDFs DIAN (sin compilar C)
- `lxml` / `xml.etree` — parsing XML UBL 2.1 (namespaces cac/cbc/ext)
- `pandas` — transformación y agrupación de datos
- `openpyxl` — escritura de Excel con formato (colores, bordes, número format)
- `streamlit` — UI web sin frontend separado
- `watchdog` — observador de sistema de archivos para disparador automático
- Python 3.14 en Windows 11 (evitar paquetes que requieran compilar desde fuente)

**Arquitectura del proyecto:**
- `extractor.py` → dict por documento (XML prioridad sobre PDF); soporta subcarpetas; fallback de fecha desde carpeta
- `validator.py` → agrega columnas validacion/observacion al DataFrame (no van a BASE_DATOS)
- `prorateo.py` → agrupación mensual + cálculo Art. 490 ET
- `excel_writer.py` → 3 hojas: BASE_DATOS / VALIDACION / PRORRATEO_IVA
- `main.py` → CLI con argparse; escaneo recursivo con `rglob`
- `watcher.py` → watchdog + debounce 10s; llama a `procesar()` de main.py
- `app.py` → Streamlit con upload + download

**Convenciones del código:**
- Separación estricta: extracción ≠ validación ≠ lógica contable
- Números colombianos: puntos=miles, coma=decimal → `_clean_number()` en extractor.py
- Fechas normalizadas a YYYY-MM-DD
- Valores de Nota Crédito con signo negativo (sign = -1)
- `processed: set[str]` usa `str(path.with_suffix("")).lower()` — clave por ruta completa, no solo stem
- Tolerancia $1 COP en cuadre contable (redondeo)
- Logging a archivo en `logs/` + stdout simultáneo

**Patrones de extracción PDF (representación gráfica DIAN estándar):**
- Folio: `_RE_FOLIO` busca `"Número de Factura: FE-001"` y variantes
- Emisor NIT: `_RE_EMISOR_NIT` busca `"Nit del Emisor: 123456"`
- Emisor nombre: `_RE_EMISOR_NOMBRE` busca `"Razón Social: ..."`
- Receptor NIT: `_RE_RECEPTOR_NIT` busca `"Número Documento: 901050311"`
- Receptor nombre: `_RE_RECEPTOR_NOMBRE` busca `"Nombre o Razón Social: ..."`
- Fecha: busca `"Fecha de Emisión:"` primero, luego primer `_RE_DATE`
- Todos los patrones tienen fallback genérico si la etiqueta específica no existe

**Al escribir código:**
- No agregar dependencias que requieran compilar en Python 3.14 (sin pymupdf, sin numpy con versiones viejas)
- Mantener funciones puras en validator.py y prorateo.py (sin side effects)
- Manejar encoding UTF-8 explícito en FileHandler
- Los regex de extractor.py usan re.I (case-insensitive) siempre
- Retornar `_empty_row(filename, error)` ante cualquier excepción de parsing

$ARGUMENTS
