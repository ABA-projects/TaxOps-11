Modo diagnóstico para facturas que no se extraen correctamente.

Dado un archivo PDF o XML problemático, sigue este proceso:

**Paso 1 — Identificar qué falló:**
- ¿El archivo se procesó? (buscar en logs/ la línea con el nombre del archivo)
- ¿Retornó _empty_row? (fuente empieza con "ERROR:")
- ¿Qué campos están vacíos: cufe, folio, fecha, nit_emisor, nombre_emisor, nit_receptor?

**Paso 2 — Analizar el texto extraído del PDF:**
```python
import pdfplumber
with pdfplumber.open("facturas/archivo.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"=== Página {i+1} ===")
        print(page.extract_text())
```

**Paso 3 — Verificar qué capturan los regex actuales:**
```python
import re, extractor as ex
with pdfplumber.open("facturas/archivo.pdf") as pdf:
    text = "\n".join(p.extract_text() or "" for p in pdf.pages)

# Folio
print("FOLIO:", ex._RE_FOLIO.search(text))

# Emisor
print("EMISOR NIT   :", ex._RE_EMISOR_NIT.search(text))
print("EMISOR NOMBRE:", ex._RE_EMISOR_NOMBRE.search(text))

# Receptor
print("RECEPTOR NIT   :", ex._RE_RECEPTOR_NIT.search(text))
print("RECEPTOR NOMBRE:", ex._RE_RECEPTOR_NOMBRE.search(text))

# Fecha
m = re.search(r"fecha\s+de\s+emisi[oó]n\s*[:\s]+(\S+)", text, re.I)
print("FECHA EMISIÓN:", m)

# CUFE / CUDE
print("CUFE:", ex._RE_CUFE.search(text))
print("CUDE:", ex._RE_CUDE.search(text))

# Montos
print("SUBTOTAL:", ex._search_money_near(text, "subtotal"))
print("IVA 19% :", ex._search_money_near(text, "IVA 19%"))
print("TOTAL   :", ex._search_money_near(text, "total factura"))

# NITs genéricos (fallback)
print("NITs genéricos:", [m.group(1) for m in ex._RE_NIT_GENERICO.finditer(text)])
```

**Paso 4 — Causas comunes y fix:**

| Síntoma | Causa probable | Fix |
|---|---|---|
| folio vacío | Emisor usa "No. FE:" en vez de "Número de Factura:" | Agregar variante a `_RE_FOLIO` |
| nit_emisor vacío | Usa "NIT Emisor:" o "Número NIT:" | Agregar variante a `_RE_EMISOR_NIT` |
| nombre_emisor incorrecto | "Razón Social:" aparece también en receptor | Refinar regex con contexto de sección |
| nit_receptor vacío | Receptor es persona natural (cédula, no NIT) | Ampliar `_RE_RECEPTOR_NIT` para cédulas |
| fecha vacía | No hay "Fecha de Emisión:" → la toma de nombre de carpeta | Verificar que el archivo esté en subcarpeta fechada |
| CUFE no capturado | Tiene 94 chars (CUFE corto) o está en página 2 | Ampliar regex o unir páginas diferente |

**Paso 5 — Emisores con formatos especiales conocidos:**
- Claro/Movistar: CUFE en página 2, totales en tabla al final
- EPM: múltiples conceptos, IVA parcial por servicio
- Peajes Concesión: sin CUFE (mandato), NIT del mandante como receptor
- Solución Gratuita DIAN: formato de la factura de ejemplo en README

**Paso 6 — Si es XML, verificar namespaces:**
```python
import xml.etree.ElementTree as ET
tree = ET.parse("facturas/archivo.xml")
root = tree.getroot()
print(root.tag)  # Debe contener Invoice o CreditNote
# Si el namespace es diferente al estándar UBL, ajustar NS en extractor.py
```

**Reportar el fix:**
- Indicar qué regex se ajustó y por qué
- Documentar el emisor y el patrón especial en un comentario en extractor.py
- Agregar el caso al listado de QA en qa.md

$ARGUMENTS
