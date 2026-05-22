# Documentación de Pruebas — Sistema de Facturas DIAN

**Total:** 107 tests | 82 unitarias (sin PDFs) | 25 end-to-end (con PDFs reales)

---

## Índice

1. [Estructura general](#1-estructura-general)
2. [test_extractor.py — Extracción de datos](#2-test_extractorpy--extracción-de-datos)
3. [test_validator.py — Validación contable](#3-test_validatorpy--validación-contable)
4. [test_prorateo.py — Prorrateo IVA Art. 490 ET](#4-test_prorateopy--prorrateo-iva-art-490-et)
5. [test_e2e.py — Pruebas end-to-end](#5-test_e2epy--pruebas-end-to-end)
6. [Tipos de documento soportados](#6-tipos-de-documento-soportados)
7. [Casos de borde cubiertos](#7-casos-de-borde-cubiertos)
8. [Cómo agregar nuevas pruebas](#8-cómo-agregar-nuevas-pruebas)

---

## 1. Estructura general

```
tests/
├── test_extractor.py    # 44 tests — funciones de extracción PDF/XML
├── test_validator.py    # 19 tests — validaciones DIAN y contables
├── test_prorateo.py     # 12 tests — cálculo prorrateo Art. 490 ET
└── test_e2e.py          # 32 tests — pipeline completo con archivos reales
```

### Principio de diseño

- **Unitarias**: prueban una función sola, con datos sintéticos. No abren PDFs reales.
  Corren siempre, en cualquier máquina, sin archivos de la DIAN.
- **End-to-end**: prueban el pipeline completo con PDFs reales descargados de la DIAN.
  Se saltan automáticamente si los PDFs no están en `facturas/`.

### Por qué importa cada capa

| Capa | Riesgo que mitiga |
|---|---|
| `test_extractor` | Extracción incorrecta de montos → error contable silencioso |
| `test_validator` | CUFE duplicado o descuadre no detectado → doble contabilización |
| `test_prorateo` | Prorrateo mal calculado → IVA descontable incorrecto ante la DIAN |
| `test_e2e` | Regresión al agregar nuevos tipos de factura o cambiar regex |

---

## 2. test_extractor.py — Extracción de datos

Módulo probado: `extractor.py`

---

### TestCleanNumber — Conversión de formatos numéricos (7 tests)

Colombia usa punto como separador de miles y coma como decimal (`1.234.567,89`).
Los PDFs de algunos proveedores exportan en formato americano (`1,234,567.89`).
Un error aquí multiplica o divide montos por 1000.

| Test | Entrada | Salida esperada | Por qué importa |
|---|---|---|---|
| `test_colombiano_miles_punto` | `"1.234.567,89"` | `1234567.89` | Formato estándar DIAN |
| `test_colombiano_sin_centavos` | `"291.400,00"` | `291400.0` | Factura sin centavos |
| `test_americano_miles_coma` | `"1,234,567.89"` | `1234567.89` | PDFs de software extranjero |
| `test_entero_simple` | `"715909"` | `715909.0` | Sin separadores |
| `test_solo_coma_decimal` | `"114,64"` | `114.64` | Valor pequeño con coma |
| `test_vacio` | `""` | `0.0` | Campo no extraído → no crashea |
| `test_con_espacio` | `" 100.000,00 "` | `100000.0` | Espacios en texto del PDF |

---

### TestParseDate — Normalización de fechas (4 tests)

Las fechas deben quedar en formato `YYYY-MM-DD` para el agrupamiento por mes del prorrateo.
Un formato incorrecto rompe el cálculo del Art. 490 ET.

| Test | Entrada | Salida esperada |
|---|---|---|
| `test_iso` | `"2026-02-23"` | `"2026-02-23"` |
| `test_colombiano_barras` | `"23/02/2026"` | `"2026-02-23"` |
| `test_colombiano_guiones` | `"16-02-2026"` | `"2026-02-16"` |
| `test_invalido_pasa_sin_crash` | `"no-es-fecha"` | devuelve string sin excepción |

---

### TestDateFromFolder — Fecha desde nombre de carpeta (4 tests)

Cuando una factura no tiene fecha reconocible en su contenido, el sistema usa el nombre de la carpeta como fallback (`facturas/2026-03/` → `2026-03-01`).

| Test | Carpeta | Resultado |
|---|---|---|
| `test_formato_yyyy_mm` | `2026-03/` | `"2026-03-01"` |
| `test_formato_yyyy_mm_dd` | `2026-03-15/` | `"2026-03-15"` |
| `test_sin_fecha_en_carpeta` | raíz | `""` (vacío, no crash) |
| `test_carpeta_no_fecha` | `facturas-varios/` | `""` |

---

### TestDetectDocType — Tipo de documento (6 tests)

El tipo determina el signo de los valores (NC = negativo), si el IVA es descontable
(Mandato = no descontable), y qué secciones del PDF contienen emisor/receptor.
Un error aquí afecta todo el prorrateo del mes.

| Test | Texto / Nombre archivo | Tipo esperado |
|---|---|---|
| `test_nota_credito_texto` | `"nota credito electronica dian"` | `Nota Crédito` |
| `test_nota_credito_nombre_archivo` | `NC-001.pdf` | `Nota Crédito` |
| `test_mandato` | `"mandato de cobro autopistas"` | `Mandato/Peaje` |
| `test_peaje` | `"peaje ruta del sol"` | `Mandato/Peaje` |
| `test_documento_soporte` | `"documento soporte"` | `Documento Soporte` |
| `test_factura_default` | cualquier otro texto | `Factura Electrónica` |

> **Nota:** `Nota Débito` y `Documento Equivalente` son detectados en el extractor
> pero no tienen tests unitarios de tipo dedicados — se cubren en los E2E con los PDFs reales.

---

### TestCalcRetencion — Retención en la fuente (5 tests)

La retención es `subtotal × 2.5%`. Las empresas autorretenedoras (resolución DIAN)
no se les practica retención. Las Notas Crédito tienen retención = 0 (pertenece
a la factura original).

| Test | Situación | Resultado esperado |
|---|---|---|
| `test_normal_2_5_pct` | NIT 899999143 (no autorretenedor) | `291400 × 2.5% = 7285` |
| `test_retencion_eb_33355` | NIT 901073241 (no autorretenedor) | `601603.36 × 2.5% = 15040.08` |
| `test_autorretenedor_cero` | Cualquier NIT del listado DIAN | `0.0` |
| `test_bavaria_autorretenedor` | NIT 860005224 (BAVARIA S.A.) | `0.0` |
| `test_base_cero` | Subtotal = 0 | `0.0` |

> **Verificación cruzada:** `test_retencion_eb_33355` compara con el campo informativo
> `"Rete fuente 15.040,08"` que aparece en el propio PDF.

---

### TestSplitIvaBases — Separación de bases de IVA (6 tests)

Calcula `base_iva_19`, `base_iva_5` y `no_gravado`. Esencial para el formulario 300 de IVA.

| Test | Escenario | base_19 | no_gravado |
|---|---|---|---|
| `test_todo_no_gravado` | IVA = 0 (tiquetes, seguros, servicios públicos) | 0 | = subtotal |
| `test_todo_gravado_19` | IVA 19% sobre toda la base | ≈ subtotal | 0 |
| `test_mixto_19_y_no_gravado` | 50% gravado, 50% exento | 100.000 | 100.000 |
| `test_iva_5` | Solo IVA 5% (alimentos, medicamentos) | 0 | 0 |
| `test_base_direct_xml` | Base exacta del XML (`TaxableAmount`) | exacta | 0 |
| `test_no_genera_negativos` | Redondeo hace base > subtotal | cap en subtotal | 0 |

---

### TestSearchMoneyNear — Regex de montos en PDF (6 tests)

Extrae valores monetarios de texto plano. El caso más crítico: el regex genérico `IVA`
capturaba números de calle de la dirección del emisor
(`IVA Dirección: CALLE 26` → extraía `26` como IVA).

| Test | Situación | Resultado |
|---|---|---|
| `test_total_bruto_factura` | Línea estándar DIAN | `601603.36` |
| `test_total_con_espacios_unicode` | Espacios U+3164 entre etiqueta y valor | `1191999.83` |
| `test_iva_line_start_evita_calle` | "IVA Dirección: CALLE 26" | `0.0` (no captura la calle) |
| `test_iva_line_start_captura_totales` | "IVA IVA 114.305,64" al inicio de línea | `114305.64` |
| `test_no_match_retorna_cero` | Etiqueta ausente | `0.0` |
| `test_subtotal_antes_de_descuentos_no_se_usa` | Hay `Subtotal` y `Total Bruto Factura` | usa `Total Bruto Factura` |

---

### TestExtractPdf — Extracción completa con mock (5 tests)

Prueba `extract_pdf()` usando texto sintético que simula una factura DIAN real.
No abre archivos PDF — usa `unittest.mock.patch` sobre `pdfplumber.open`.

| Test | Qué valida |
|---|---|
| `test_campos_basicos` | Folio, NITs, fecha, fuente="PDF" extraídos correctamente |
| `test_montos_extraidos` | subtotal, iva_19, total con los valores del texto sintético |
| `test_retencion_calculada` | `950000 × 2.5% = 23750` calculado automáticamente |
| `test_nota_credito_valores_negativos` | subtotal y total negativos cuando tipo = Nota Crédito |
| `test_cufe_capturado` | CUFE de 96 hex chars capturado íntegramente |

---

## 3. test_validator.py — Validación contable

Módulo probado: `validator.py`

---

### TestValidacionOK — Casos que deben pasar (3 tests)

| Test | Escenario |
|---|---|
| `test_factura_correcta` | Todos los campos válidos, cuadre exacto |
| `test_con_iva_cuadrado` | subtotal 601.603 + IVA 114.305 = total 715.909 |
| `test_dentro_tolerancia` | Diferencia de $0.50 COP por redondeo — debe ser OK |

---

### TestCamposVacios — Campos críticos vacíos (4 tests parametrizados)

Los campos `cufe`, `folio`, `fecha`, `nit_emisor` son obligatorios.

```
test_campo_critico_vacio[cufe]
test_campo_critico_vacio[folio]
test_campo_critico_vacio[fecha]
test_campo_critico_vacio[nit_emisor]
```

---

### TestCUFE — Validación del código único (4 tests)

El CUFE/CUDE debe tener exactamente 96 caracteres hexadecimales.
Un CUFE inválido o duplicado puede indicar una factura falsa o un error de descarga.

| Test | Situación | Resultado |
|---|---|---|
| `test_cufe_corto` | Menos de 96 chars | ERROR "CUFE inválido" |
| `test_cufe_con_chars_invalidos` | Contiene 'Z' (no hex) | ERROR |
| `test_cufe_duplicado` | Mismo CUFE en dos filas | ERROR "CUFE DUPLICADO" en ambas |
| `test_cufe_unico_ok` | 96 hex, una sola vez | OK |

> El mismo validador aplica a CUDE (documentos equivalentes y notas). La lógica es idéntica.

---

### TestCuadreContable — Verificación subtotal + IVA = total (2 tests)

```
subtotal + iva_19 + iva_5 = total  (tolerancia ±$1 COP)
```

| Test | Situación | Resultado |
|---|---|---|
| `test_descuadre_mayor_tolerancia` | subtotal 100k + IVA 19k ≠ total 100k | ERROR "Descuadre" |
| `test_total_cero_no_valida_cuadre` | total = 0 (campo no extraído) | no genera ERROR por cuadre |

---

### TestNIT — Formato de identificación tributaria (3 tests)

Un NIT con puntos o guiones indica que el regex extrajo el NIT formateado.

| Test | NIT | Resultado |
|---|---|---|
| `test_nit_con_punto_sospechoso` | `"123.456.789"` | ERROR "NIT sospechoso" |
| `test_nit_con_guion_sospechoso` | `"123456-7"` | ERROR "NIT sospechoso" |
| `test_nit_valido_9_digitos` | `"900100200"` | OK |

---

### TestMandato — IVA en mandatos/peajes (2 tests)

| Test | Situación | Resultado |
|---|---|---|
| `test_mandato_con_iva_es_error` | tipo=Mandato, iva_19=5000 | ERROR "Mandato/Peaje con IVA" |
| `test_mandato_sin_iva_ok` | tipo=Mandato, iva_19=0 | OK |

---

### TestValidateDataFrame — DataFrame completo (3 tests)

| Test | Qué valida |
|---|---|
| `test_agrega_columnas` | Las columnas `validacion` y `observacion` existen en el resultado |
| `test_duplicados_marcados_en_ambas_filas` | CUFE duplicado marca ERROR en las dos filas |
| `test_build_validation_sheet_columnas` | VALIDACION tiene `validacion`/`observacion` pero no `nit_emisor` |

---

## 4. test_prorateo.py — Prorrateo IVA Art. 490 ET

Módulo probado: `prorateo.py`

---

### TestCalcularProrateo — Fórmula principal (4 tests)

```
% prorrateo = ingresos_gravados / (ingresos_gravados + ingresos_excluidos)
IVA descontable = IVA_total × % prorrateo
```

| Test | Gravados | Excluidos | % esperado | IVA descontable |
|---|---|---|---|---|
| `test_100_pct_solo_gravados` | 5.000.000 | 0 | 100% | = IVA total |
| `test_50_50_gravados_excluidos` | 500.000 | 500.000 | 50% | IVA / 2 |
| `test_0_pct_solo_excluidos` | 0 | 1.000.000 | 0% | 0 |
| `test_sin_datos_ingresos_prorrateo_100` | sin datos | sin datos | 100% | = IVA total |

---

### TestMandatosPeajes — Tratamiento especial (2 tests)

| Test | Escenario | IVA descontable | IVA no descontable |
|---|---|---|---|
| `test_mandato_va_a_no_descontable` | Solo mandato IVA 5.000 | 0 | 5.000 |
| `test_mezcla_factura_y_mandato` | Factura IVA 10k + Mandato IVA 5k | 10.000 | 5.000 |

---

### TestNotasCredito — Notas crédito reducen el mes (2 tests)

| Test | Facturas del mes | IVA base neto |
|---|---|---|
| `test_nota_credito_resta_del_mes` | Factura +19k, NC -5k | 14.000 |
| `test_nota_credito_puede_dejar_iva_total_negativo` | Factura +5k, NC -10k | -5.000 (válido) |

---

### TestAgrupacionPorMes (2 tests)

| Test | Situación | Filas resultado |
|---|---|---|
| `test_dos_meses_separados` | Facturas en enero y febrero | 2 filas |
| `test_mismo_mes_acumula` | Dos facturas en febrero | 1 fila, IVA sumado |

---

### TestProrateoSimple — Sin datos de ingresos (2 tests)

| Test | Qué valida |
|---|---|
| `test_tiene_advertencia` | La columna `advertencia` existe y no está vacía |
| `test_pct_es_100` | Sin ingresos, el % queda en 100% (no en 0%) |

---

## 5. test_e2e.py — Pruebas end-to-end

Requieren los PDFs reales en `facturas/`. Se saltan si no están disponibles.

---

### TestExtraccionSTK602558 — SATENA (11 tests)

Factura de tiquetes aéreos. IVA = 0, todo no gravado.

| Test | Valor esperado |
|---|---|
| `test_folio` | `"STK-602558"` |
| `test_nit_emisor` | `"899999143"` |
| `test_nit_receptor` | `"902012620"` |
| `test_fecha` | `"2026-02-23"` |
| `test_subtotal` | `291400.0` |
| `test_iva_cero` | `iva_19 = 0, iva_5 = 0` |
| `test_no_gravado_igual_subtotal` | `291400.0` |
| `test_total` | `291400.0` |
| `test_retencion_2_5_pct` | `7285.0` |
| `test_cufe_96_hex` | 96 chars hex |

---

### TestExtraccionEB33355 — AGROTECNICO J O SAS (9 tests)

Factura con IVA 19% sobre toda la base, con descuento de línea.

| Test | Valor esperado | Verificación cruzada |
|---|---|---|
| `test_folio` | `"EB-33355"` | — |
| `test_nit_emisor` | `"901073241"` | — |
| `test_fecha` | `"2026-02-16"` | — |
| `test_subtotal` | `601603.36` | Total Bruto Factura después del descuento |
| `test_iva_19` | `114305.64` | — |
| `test_base_iva_19_igual_subtotal` | `≈ 601603.36` | Toda la base está gravada |
| `test_no_gravado_cero` | `0.0` | — |
| `test_total` | `715909.0` | 601603.36 + 114305.64 |
| `test_retencion_coincide_con_pdf` | `15040.08` | Coincide con "Rete fuente" del PDF |

---

### TestResolverArchivos — Deduplicación (6 tests)

Prueba `_resolver_archivos()` — escaneo previo al procesamiento paralelo.

| Test | Situación | Resultado |
|---|---|---|
| `test_solo_pdf` | Un PDF | 1 archivo |
| `test_par_pdf_xml_queda_xml` | FE-001.pdf + FE-001.xml | Solo el XML |
| `test_mismo_nombre_subcarpetas_no_se_deduplicar` | 2026-03/FE-001.pdf + 2026-04/FE-001.pdf | 2 archivos |
| `test_ignora_extensiones_no_validas` | PDF + XLSX + TXT | Solo el PDF |
| `test_recursivo_subcarpetas` | PDF raíz + PDF en subcarpeta | 2 archivos |
| `test_carpeta_vacia` | Sin archivos | lista vacía |

---

### TestPipelineCompleto — Excel generado (5 tests)

| Test | Qué valida |
|---|---|
| `test_genera_excel_con_3_hojas` | BASE_DATOS, VALIDACION, PRORRATEO_IVA presentes |
| `test_base_datos_columnas_correctas` | Columnas requeridas presentes; `archivo` y `validacion` ausentes |
| `test_validacion_ok_ambas_facturas` | Las dos facturas de prueba pasan la validación |
| `test_prorrateo_tiene_columnas_requeridas` | mes, iva_total, iva_descontable, etc. |
| `test_dos_facturas_procesadas` | Exactamente 2 filas con folios STK-602558 y EB-33355 |

---

## 6. Tipos de documento soportados

| Tipo | Detección | Sign | Retención | IVA prorrateo |
|---|---|---|---|---|
| Factura Electrónica | por defecto | +1 | 2.5% | base normal |
| Nota Crédito | "nota cr", `NC-*.pdf` | -1 | 0 | resta del mes |
| Nota Débito | "nota déb/deb", `ND-*.pdf` | +1 | 2.5% | suma al mes |
| Mandato/Peaje | "mandato", "peaje" | +1 | 2.5% | no descontable |
| Documento Soporte | "documento soporte" | +1 | 2.5% | base normal |
| Documento Equivalente | "documento equivalente" | +1 | 2.5% | base normal |

### Layouts reconocidos de Documento Equivalente

| Layout | Ejemplo | Sección emisor | Sección receptor |
|---|---|---|---|
| POS | SUPERMERCADO (POSE5217) | `Datos del vendedor` | `Datos del adquiriente` |
| SPD (servicios públicos) | EPM (DEE46098616) | `Datos del emisor` | `Datos del Adquiriente/Consumidor` |

---

## 7. Casos de borde cubiertos

| Caso | Test que lo cubre |
|---|---|
| Número de calle capturado como IVA | `test_iva_line_start_evita_calle` |
| Subtotal "antes de descuentos" (incorrecto) | `test_subtotal_antes_de_descuentos_no_se_usa` |
| Espacios unicode U+3164 entre etiqueta y monto | `test_total_con_espacios_unicode` |
| Nota Crédito con valores negativos | `test_nota_credito_valores_negativos` |
| CUFE duplicado marcado en ambas filas | `test_duplicados_marcados_en_ambas_filas` |
| Nota Crédito mayor que factura → IVA neto negativo | `test_nota_credito_puede_dejar_iva_total_negativo` |
| Mismo nombre de archivo en subcarpetas distintas | `test_mismo_nombre_subcarpetas_no_se_deduplicar` |
| Redondeo hace base IVA > subtotal | `test_no_genera_negativos` |
| Autorretenedor con retención = 0 | `test_autorretenedor_cero`, `test_bavaria_autorretenedor` |
| IVA mixto 5% y 19% en mismo documento | E2E con DOC_EQUIVALENTE POS (POSE5217) |
| Emisor en segunda sección (Doc Equiv POS) | E2E con DOC_EQUIVALENTE POS |
| Total con etiqueta "Total documento" (no "Total factura") | E2E con DOC_SOPORTE |
| Nota Crédito sin retención | `test_nota_credito_valores_negativos` |
| Regex `adquiriente` con doble "ie" | Cubierto en extracción E2E DOC_EQUIVALENTE |

---

## 8. Cómo agregar nuevas pruebas

### Al procesar una factura que falló

```bash
# 1. Ver el texto del PDF
python -c "
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
with pdfplumber.open('facturas/MI_FACTURA.pdf') as p:
    for i, pg in enumerate(p.pages):
        print(f'--- Pagina {i+1} ---')
        print(pg.extract_text())
"

# 2. Probar extracción directa
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from extractor import extract_one
from pathlib import Path
r = extract_one(Path('facturas/MI_FACTURA.pdf'))
for k, v in r.items(): print(f'{k}: {v}')
"
```

### Al agregar un nuevo tipo de documento

1. Añadir la detección en `extractor.py::_detect_doc_type`.
2. Agregar un test en `test_extractor.py::TestDetectDocType`.
3. Agregar caso E2E en `test_e2e.py` con el PDF real.

### Convención de nombres

```
test_<qué_se_prueba>             # caso normal
test_<qué_se_prueba>_<variante>  # variante específica
```
