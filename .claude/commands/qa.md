Actúa como QA Engineer especializado en validación de extracción de documentos contables.

**Qué probar en este proyecto:**

**1. Extracción (extractor.py)**
- CUFE capturado correctamente (exactamente 96 caracteres hex)
- Folio capturado desde "Número de Factura: FE-001" (no "ELECTRÓNICA" ni texto adyacente)
- NIT emisor desde "Nit del Emisor: 123456" (no NIT del software o del receptor)
- Nombre emisor desde "Razón Social: ..." (no "Nombre Comercial:" ni etiquetas adyacentes)
- NIT receptor desde "Número Documento: 9010..." (receptor puede tener cédula, no siempre NIT)
- Nombre receptor desde "Nombre o Razón Social: ..."
- Fecha desde "Fecha de Emisión:" preferentemente; fallback: primera fecha; fallback: nombre de carpeta
- Subtotal + IVA_19 + IVA_5 ≈ Total (tolerancia $1 COP)
- Nota crédito con valores negativos
- Mandato sin IVA o con IVA marcado como no descontable
- PDF con múltiples páginas: datos en página 1 y CUFE en última página
- PDFs con texto escaneado (OCR): debe fallar limpiamente con _empty_row

**2. Subcarpetas y detección de fecha por carpeta**
- Archivo en `facturas/2026-03/FE-001.pdf` → se procesa correctamente; fecha inferida de carpeta si el documento no tiene fecha propia
- Archivo sin fecha extraíble en carpeta `2026-03/` → fecha = `2026-03-01`
- Archivo sin fecha en carpeta sin fecha → fecha vacía (no falla)
- Mismo nombre de archivo en dos subcarpetas distintas → se procesan ambos (no se deduplica por stem)
- Archivos en raíz de facturas/ siguen procesándose normalmente

**3. Validación (validator.py)**
- CUFE duplicado: debe marcar ERROR en AMBAS filas
- NIT con puntos o guiones: debe detectarse como sospechoso
- Mandato con IVA > 0: ERROR "Mandato/Peaje con IVA"
- Campos vacíos: cufe, folio, fecha, nit_emisor → ERROR individual por campo
- `validacion` y `observacion` presentes en DataFrame interno y hoja VALIDACION; ausentes en BASE_DATOS

**4. Prorrateo (prorateo.py)**
- Sin ingresos: pct_prorateo = 100%, columna advertencia presente
- Con ingresos 50/50: pct_prorateo = 50%
- Mes con solo mandatos: iva_base_prorateo = 0, todo en iva_mandatos
- Nota crédito en mismo mes: reduce iva_total del mes

**5. Excel (excel_writer.py)**
- 3 hojas presentes: BASE_DATOS, VALIDACION, PRORRATEO_IVA
- BASE_DATOS NO tiene columnas validacion ni observacion
- VALIDACION tiene celdas ERROR con fondo rojo, OK con fondo verde
- Columnas de dinero con formato `#,##0.00`
- Fila de encabezado con fondo azul oscuro

**6. Watcher (watcher.py)**
- Al copiar un PDF a `facturas/`, se genera Excel en `output/` sin intervención manual
- Al copiar a subcarpeta `facturas/2026-04/`, también se detecta y procesa
- Si se copian 5 archivos rápido (menos de 10 s), solo genera un Excel (debounce)
- Al presionar Ctrl+C, el watcher termina limpiamente

**Casos de prueba prioritarios:**
- Factura formato "Solución Gratuita DIAN" (el ejemplo del README)
- Factura de Claro/Movistar (telecom: mezcla gravado/excluido)
- Factura de peaje (mandato, sin IVA descontable)
- Nota crédito que anula factura del mismo mes
- PDF con dos NITs en encabezado (emisor vs receptor vs software)
- Lote de 50+ facturas del mismo emisor (deduplicación de CUFE)
- Factura en subcarpeta con nombre de fecha vs en raíz

**Al reportar un bug:**
- Indica el archivo específico y la función
- Muestra el valor extraído vs el valor esperado
- Clasifica: ERROR crítico (dato incorrecto) vs WARNING (dato vacío recuperable)
- Referencia el regex o ruta XML que falló (ver debug-factura.md para diagnóstico)

$ARGUMENTS
