# Renta Personas Naturales — Semanas 4 y 5

**Fecha:** 2026-06-02  
**Módulo:** `taxops-web/app/(app)/renta` + `services/renta/` + `api/routers/renta.py`  
**Estado base:** Semanas 1-3 completadas y desplegadas en Cloud Run / Vercel.

---

## Contexto

El módulo de renta actual (Semanas 1-3) permite:
- CRUD de contribuyentes
- Upload de documentos + OCR + clasificación automática
- Motor Art. 241 ET con tabla progresiva UVT (cédula general simplificada)
- Panel de liquidación en el frontend

Lo que falta para que el módulo sea usable en producción:
1. **Semana 4:** Entrada manual de datos tributarios, editor post-cálculo, cédulas separadas (dividendos + ganancias ocasionales), validaciones bloqueantes y suaves.
2. **Semana 5:** Generación del borrador PDF Formulario 210 DIAN.

---

## Semana 4 — Datos, Cédulas y Validaciones

### 1. Arquitectura de datos

**Migración Alembic `005_renta_cedulas.py`** — nuevas columnas en `renta_declaraciones`:

| Campo | Tipo | Casilla F210 | Descripción |
|---|---|---|---|
| `ingresos_capital` | numeric | 58 | Rendimientos financieros, arrendamientos |
| `ingresos_no_laborales` | numeric | 74 | Todo lo que no es trabajo ni capital |
| `aportes_pension` | numeric | 33 | INCR — aportes obligatorios pensión |
| `afc_fvp` | numeric | 35 | Aportes AFC / FVP / AVC (renta exenta) |
| `intereses_vivienda` | numeric | 38 | Deducción hipoteca, máx 1.200 UVT |
| `medicina_prepagada` | numeric | 39 | Deducción salud, máx 16 UVT/mes |
| `dependientes` | integer | 39 | Número de dependientes (72 UVT c/u, máx 4) |
| `dividendos_gravados` | numeric | 107 | Dividendos 2017+ subcédula gravada |
| `ganancia_ocasional` | numeric | 111 | Ingresos ganancias ocasionales |
| `tipo_ganancia` | text | — | `venta_activo` / `herencia` / `loteria` |
| `pasivos` | numeric | 30 | Deudas — para calcular patrimonio líquido |
| `ajuste_manual` | jsonb | — | Overrides manuales del usuario por campo |

El campo `ajuste_manual` almacena overrides sin columnas adicionales. Ejemplo:
```json
{"ingresos_laborales": 45000000, "retenciones": 3200000}
```

### 2. Motor de cálculo — `services/renta/tax_engine.py`

**Cambio 1 — Límite 40% / 1.340 UVT (Art. 336 ET):**
El motor actual aplica el 25% laboral pero no verifica el tope global de rentas exentas + deducciones imputables. Se agrega:
```
tope_limitadas = min(ingresos_netos_cedula_general × 0.40, 1340 × uvt)
exentas_y_deduc_limitadas = min(exentas_brutas + deducciones_brutas, tope_limitadas)
```

**Cambio 2 — Cédula de dividendos (Art. 242 ET):**
```
Si dividendos_gravados ≤ 300 UVT → impuesto_dividendos = 0
Si dividendos_gravados > 300 UVT → impuesto_dividendos = (dividendos_gravados - 300×uvt) × 15%
```

**Cambio 3 — Ganancias ocasionales (Art. 299-316 ET):**
```
tarifa = 20% si tipo_ganancia == "loteria" else 10%
impuesto_ocasional = max(0, ganancia_ocasional - exentas_ocasionales) × tarifa
```

**Impuesto total:**
```
impuesto_cargo = impuesto_cedula_general + impuesto_dividendos + impuesto_ocasional
saldo_pagar    = max(0, impuesto_cargo - retenciones)
saldo_favor    = max(0, retenciones - impuesto_cargo)
```

**Overrides:** antes de consolidar, el motor aplica `ajuste_manual` sobre cualquier campo. Los campos overrideados se marcan en `detalle_calculo.ajustados_manualmente`.

### 3. API — `api/routers/renta.py`

Endpoint nuevo:
```
PATCH /renta/contribuyentes/{id}/declaracion/datos
Body: {ingresos_laborales, ingresos_capital, ingresos_no_laborales,
       aportes_pension, afc_fvp, retenciones, intereses_vivienda,
       medicina_prepagada, dependientes, dividendos_gravados,
       ganancia_ocasional, tipo_ganancia, pasivos, ajuste_manual?}
Response: DeclaracionOut
```
Hace upsert de los datos sin recalcular el impuesto. Separado de `POST /calcular` para que el usuario pueda guardar borradores de datos.

`upsert_declaracion()` en `db/database_renta.py` se extiende para incluir los campos nuevos.

### 4. Frontend — `taxops-web/app/(app)/renta/page.tsx`

**Zona A — Formulario de datos tributarios** (panel colapsable antes del botón "Calcular"):

Pestañas:
- **Cédula General:** ingresos laborales, capital, no laborales; aportes pensión; AFC/FVP; retenciones; intereses vivienda; medicina prepagada; dependientes (número).
- **Dividendos:** monto dividendos gravados 2017+.
- **Ganancias Ocasionales:** tipo + valor bruto + costos asociados.
- **Patrimonio:** activos (inmuebles, vehículos, cuentas) + pasivos (deudas).

Botones: **"Guardar datos"** (`PATCH /declaracion/datos`) y **"Calcular"** (ya existente).

**Zona B — Editor post-cálculo** en el panel de liquidación:

- Cada fila de la tabla de cédula tiene ícono ✏️ al hacer hover.
- Al hacer clic → campo se convierte en `<input>` numérico.
- Campos overrideados muestran chip naranja `manual`.
- Aparece botón **"Recalcular con ajustes"** cuando hay algún override activo.

**Zona C — Panel de validaciones** (debajo de liquidación):

```
🔴 BLOQUEOS — impiden marcar "Lista para presentar"
   · Sin ingresos declarados en ninguna cédula
   · Declaración en estado borrador_vacio

⚠️  ADVERTENCIAS — informativas
   · Deducciones + rentas exentas > 40% ingresos netos (Art. 336 ET)
   · Retenciones > impuesto a cargo → verificar saldo a favor
   · Documentos con confianza OCR < 50%
   · Patrimonio bruto $0 con ingresos > 0
```

Botón **"Marcar lista para presentar"** → solo habilitado si no hay bloqueos rojos. Llama a `PATCH /declaracion/datos` con `{estado: "revision"}`.

---

## Semana 5 — PDF Formulario 210

### 1. Librería: WeasyPrint (HTML → PDF)

Justificación: el PDF de DIAN compartido es el instructivo (texto plano), no un formulario editable. Generar desde HTML es la opción más mantenible: fácil de ajustar año a año, soporta estilos CSS, no requiere coordenadas absolutas como reportlab.

### 2. `services/renta/pdf_formulario210.py`

Función principal:
```python
def generar_pdf(declaracion: dict, contribuyente: dict) -> bytes:
    html = _render_html(declaracion, contribuyente)
    return HTML(string=html).write_pdf()
```

El HTML replica el layout del Formulario 210 con secciones y casillas numeradas.

**Mapeo campos → casillas F210:**

| Campo interno | Casilla | Sección |
|---|---|---|
| `patrimonio_bruto` | 29 | Patrimonio |
| `pasivos` | 30 | Patrimonio |
| `patrimonio_liquido` | 31 | Patrimonio |
| `ingresos_laborales` | 32 | Cédula general — Trabajo |
| `aportes_pension` | 33 | Cédula general — Trabajo |
| `afc_fvp` | 35 | Cédula general — Trabajo |
| `rentas_exentas` (25% num.10) | 36 | Cédula general — Trabajo |
| `intereses_vivienda` | 38 | Cédula general — Trabajo |
| `deducciones` (salud+dep) | 39 | Cédula general — Trabajo |
| `rentas_capital` | 58 | Cédula general — Capital |
| `rentas_no_laborales` | 74 | Cédula general — No laboral |
| `dividendos_gravados` | 107 | Cédula dividendos |
| `ganancia_ocasional` | 111 | Ganancias ocasionales |
| `impuesto_cargo` | 116 | Liquidación |
| `retenciones` | 132 | Liquidación |
| `saldo_favor` | 137 | Liquidación |
| `saldo_pagar` | 138 | Liquidación |

El PDF incluye **sello de agua diagonal "BORRADOR"** para dejar claro que es liquidación preliminar, no declaración presentada ante DIAN.

### 3. API — endpoint nuevo

```
GET /renta/contribuyentes/{id}/declaracion/pdf
→ StreamingResponse(media_type="application/pdf")
→ Content-Disposition: attachment; filename="Formulario210_{año}_{numero_doc}.pdf"
```

- Devuelve 404 si no existe declaración calculada.
- Requiere autenticación (`get_current_user`).

### 4. Frontend

Botón nuevo en el panel de liquidación (junto a "Recalcular"):

```
[ ↓ Formulario 210 ]
```

- Deshabilitado hasta que exista una declaración calculada.
- Al hacer clic → descarga directa del PDF.
- Misma implementación que el preview de documentos (window.open con token).

---

## Dependencias entre semanas

Semana 5 depende de Semana 4: el PDF necesita los campos nuevos (`pasivos`, `dividendos_gravados`, `aportes_pension`, etc.) que agrega la migración `005`.

## Dependencias de infraestructura

- `weasyprint` → agregar a `api/requirements-api.txt`
- `apt-get install libpango-1.0-0 libpangoft2-1.0-0` → agregar al `Dockerfile-api` (dependencias del sistema de WeasyPrint)

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `db/migrations/005_renta_cedulas.py` | Nueva migración Alembic |
| `db/database_renta.py` | Extender `upsert_declaracion()` |
| `api/schemas_renta.py` | Nuevos campos en `DeclaracionOut` y schema de entrada |
| `api/routers/renta.py` | `PATCH /datos` + `GET /pdf` |
| `services/renta/tax_engine.py` | Límite 40%, cédula dividendos, ganancias ocasionales, overrides |
| `services/renta/pdf_formulario210.py` | Nuevo — generador HTML→PDF |
| `taxops-web/app/(app)/renta/page.tsx` | Zonas A, B y C + botón PDF |
| `api/requirements-api.txt` | `weasyprint` |
| `api/Dockerfile-api` | Dependencias sistema WeasyPrint |
