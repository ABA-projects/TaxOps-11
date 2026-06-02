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

**Migración Alembic `005_renta_cedulas.py`** — todas las columnas se agregan como `ALTER TABLE renta_declaraciones ADD COLUMN IF NOT EXISTS` con DEFAULT explícito para no romper filas existentes en producción:

| Campo nuevo | Tipo SQL | DEFAULT | Casilla F210 | Descripción |
|---|---|---|---|---|
| `aportes_pension` | NUMERIC(18,2) | 0 | 33 | INCR — aportes obligatorios pensión |
| `afc_fvp` | NUMERIC(18,2) | 0 | 35 | Aportes AFC / FVP / AVC (renta exenta) |
| `rentas_capital` | NUMERIC(18,2) | 0 | 58 | Rendimientos financieros, arrendamientos |
| `rentas_no_laborales` | NUMERIC(18,2) | 0 | 74 | Todo lo que no es trabajo ni capital |
| `intereses_vivienda` | NUMERIC(18,2) | 0 | 38 | Deducción hipoteca, máx 1.200 UVT |
| `medicina_prepagada` | NUMERIC(18,2) | 0 | 39 | Deducción salud, máx 16 UVT/mes |
| `dependientes` | INTEGER | 0 | 39 | Número de dependientes (72 UVT c/u, máx 4) |
| `dividendos_gravados` | NUMERIC(18,2) | 0 | 107 | Dividendos 2017+ subcédula gravada |
| `ganancia_ocasional` | NUMERIC(18,2) | 0 | 111 | Ingresos ganancias ocasionales |
| `tipo_ganancia` | TEXT | NULL | — | `venta_activo` / `herencia` / `loteria` |
| `pasivos` | NUMERIC(18,2) | 0 | 30 | Deudas — para calcular patrimonio líquido |
| `ajuste_manual` | JSONB | NULL | — | Overrides manuales del usuario por campo |

> **Nota nomenclatura:** Los campos `rentas_capital` y `rentas_no_laborales` usan los nombres ya presentes en el código existente (`tax_engine.py`, `upsert_declaracion()`, `DeclaracionOut`). No se crean columnas con nombres distintos para no romper el código en producción.

**Estado de declaración** — valores válidos para `renta_declaraciones.estado`:

| Estado | Significado | Quién lo asigna |
|---|---|---|
| `borrador` | Calculada por el motor, no revisada | `POST /calcular` (ya existe) |
| `revision` | Usuario la marcó lista para presentar | `PATCH /datos` con `{estado: "revision"}` |
| `presentado` | Declarada ante DIAN (manual por ahora) | `PATCH /datos` con `{estado: "presentado"}` |

El bloqueo "sin ingresos" se evalúa en tiempo real en el frontend (si `ingresos_laborales + rentas_capital + rentas_no_laborales + dividendos_gravados == 0`). No es un estado en DB.

**`ajuste_manual` — keys válidas y comportamiento:**

Solo se aceptan como keys los nombres de columnas numéricas de `renta_declaraciones`:
```
ingresos_laborales, rentas_capital, rentas_no_laborales, dividendos_gravados,
ganancia_ocasional, rentas_exentas, deducciones, retenciones,
patrimonio_bruto, patrimonio_liquido, aportes_pension, afc_fvp,
intereses_vivienda, medicina_prepagada, pasivos
```

Comportamiento:
- Keys no reconocidas → ignoradas silenciosamente (no 422, para no romper versiones anteriores del frontend)
- Valores negativos → aceptados solo en campos que pueden ser negativos (`rentas_no_laborales`); rechazados (se trata como 0) en los demás
- El motor marca los campos aplicados en `detalle_calculo.ajustados_manualmente: ["ingresos_laborales", ...]`

### 2. Motor de cálculo — `services/renta/tax_engine.py`

**Cambio 1 — Límite 40% / 1.340 UVT (Art. 336 ET) aplicado sobre el total consolidado:**

El Art. 336 ET calcula el tope sobre la suma de ingresos netos de toda la cédula general (las tres subcédulas suman antes de aplicar el límite). Implementación:

```
ingresos_netos_cedula_general = (
    ingresos_laborales - aportes_pension
  + rentas_capital
  + rentas_no_laborales
)
tope_limitadas = min(ingresos_netos_cedula_general × 0.40, 1340 × uvt)
exentas_y_deduc_a_aplicar = min(exentas_brutas + deducciones_brutas, tope_limitadas)
renta_gravable = max(0, ingresos_netos_cedula_general - exentas_y_deduc_a_aplicar)
```

> El Formulario 210 distribuye el tope subcédula a subcédula solo para fines de presentación (casillas 41, 53, 69, 86), pero el cálculo del límite usa el total consolidado. Nuestra implementación es correcta para el cálculo del impuesto; el PDF (Semana 5) mostrará la distribución proporcional.

**Cambio 2 — Cédula de dividendos (Art. 242 ET):**
```
Si dividendos_gravados ≤ 300 × uvt → impuesto_dividendos = 0
Si dividendos_gravados > 300 × uvt → impuesto_dividendos = (dividendos_gravados - 300 × uvt) × 0.15
```

**Cambio 3 — Ganancias ocasionales (Art. 299-316 ET):**
```
tarifa = 0.20 si tipo_ganancia == "loteria" else 0.10
impuesto_ocasional = max(0, ganancia_ocasional) × tarifa
```
(No se aplica deducción de costos en esta versión — simplificación válida para personas naturales sin actividad económica)

**Impuesto total:**
```
impuesto_cargo = impuesto_cedula_general + impuesto_dividendos + impuesto_ocasional
saldo_pagar    = max(0, impuesto_cargo - retenciones)
saldo_favor    = max(0, retenciones - impuesto_cargo)
```

**Overrides:** si `ajuste_manual` no es null, el motor aplica los overrides válidos sobre los valores consolidados antes de calcular el impuesto. Los campos overrideados se registran en `detalle_calculo.ajustados_manualmente`.

**Patrimonio líquido:**
```
patrimonio_liquido = max(0, patrimonio_bruto - pasivos)
```

### 3. API — `api/routers/renta.py`

**Endpoint nuevo — guardar datos tributarios:**
```
PATCH /renta/contribuyentes/{id}/declaracion/datos
Guard: get_current_user + verificar contribuyente.org_id == user.org_id (→ 404 si no coincide)
Body (todos opcionales):
  ingresos_laborales, rentas_capital, rentas_no_laborales,
  aportes_pension, afc_fvp, retenciones, intereses_vivienda,
  medicina_prepagada, dependientes, dividendos_gravados,
  ganancia_ocasional, tipo_ganancia, pasivos, ajuste_manual, estado
Response: DeclaracionOut
```
Hace upsert sin recalcular impuesto. El estado puede avanzar de `borrador` a `revision` desde aquí.

**`upsert_declaracion()`** en `db/database_renta.py` se extiende para incluir todos los campos nuevos de la migración 005.

### 4. Frontend — `taxops-web/app/(app)/renta/page.tsx`

**Zona A — Formulario de datos tributarios** (panel colapsable con pestañas, antes del panel de liquidación):

- **Pestaña Cédula General:** ingresos laborales, rentas de capital, rentas no laborales, aportes pensión (INCR), AFC/FVP/AVC, retenciones del año, intereses crédito vivienda, medicina prepagada, número de dependientes.
- **Pestaña Dividendos:** monto dividendos gravados 2017+.
- **Pestaña Ganancias Ocasionales:** tipo (venta activo / herencia / lotería) + valor bruto.
- **Pestaña Patrimonio:** activos totales (inmuebles, vehículos, cuentas) + pasivos (deudas).

Botones: **"Guardar datos"** (`PATCH /declaracion/datos`) y **"Calcular"** (ya existente).

**Zona B — Editor post-cálculo** en el panel de liquidación:

- Cada fila de la tabla tiene ícono ✏️ al hacer hover.
- Al hacer clic → campo se convierte en `<input>` numérico.
- Campos overrideados muestran chip naranja `manual`.
- Aparece botón **"Recalcular con ajustes"** cuando hay algún override activo. Al presionar, envía `ajuste_manual` junto al `POST /calcular`.

**Zona C — Panel de validaciones** (debajo de liquidación):

```
🔴 BLOQUEOS — impiden "Marcar lista para presentar"
   · Todos los ingresos en cero (sin datos en ninguna cédula)

⚠️  ADVERTENCIAS — informativas
   · Rentas exentas + deducciones > 40% ingresos netos (Art. 336 ET)
   · Retenciones > impuesto a cargo → probable saldo a favor alto
   · Documentos con confianza OCR < 50%
   · Patrimonio bruto $0 con ingresos > 0
```

Botón **"Marcar lista para presentar"** → solo habilitado si no hay bloqueos rojos. Llama a `PATCH /declaracion/datos` con `{estado: "revision"}`.

---

## Semana 5 — PDF Formulario 210

### 1. Librería: WeasyPrint (HTML → PDF)

El PDF de DIAN disponible es el instructivo (texto plano), no un formulario editable. ReportLab permanece en el proyecto para otros usos. WeasyPrint se agrega exclusivamente para el Formulario 210: genera un HTML que replica el layout del formulario y lo convierte a PDF. Es la opción más mantenible para actualizaciones año a año.

### 2. `services/renta/pdf_formulario210.py`

```python
def generar_pdf(declaracion: dict, contribuyente: dict) -> bytes:
    html = _render_html(declaracion, contribuyente)
    return HTML(string=html).write_pdf()
```

El HTML tiene secciones con casillas numeradas y sello de agua "BORRADOR" en diagonal.

**Mapeo campos internos → casillas F210:**

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

### 3. API — endpoint nuevo

```
GET /renta/contribuyentes/{id}/declaracion/pdf
Guard: get_current_user + verificar contribuyente.org_id == user.org_id (→ 404 si no coincide)
→ StreamingResponse(media_type="application/pdf")
→ Content-Disposition: attachment; filename="Formulario210_{año}_{numero_doc}.pdf"
→ 404 si no existe declaración calculada para el contribuyente
```

### 4. Frontend

Botón nuevo en el panel de liquidación (junto a "Recalcular"):
```
[ ↓ Formulario 210 ]
```
- Deshabilitado hasta que exista una declaración calculada (`decl != null`).
- Al hacer clic → `window.open(/api-proxy/renta/contribuyentes/{id}/declaracion/pdf)`.

---

## Dependencias entre semanas

Semana 5 depende de Semana 4: el PDF necesita los campos nuevos (`pasivos`, `dividendos_gravados`, `aportes_pension`, `rentas_capital`, `rentas_no_laborales`) que agrega la migración `005`.

## Dependencias de infraestructura

**`api/requirements-api.txt`:** agregar `weasyprint`

**`api/Dockerfile-api`:** agregar dependencias del sistema necesarias para WeasyPrint en Debian slim (soporte de fuentes para tildes, ñ y símbolos de moneda):
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
```

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `db/migrations/005_renta_cedulas.py` | ALTER TABLE ADD COLUMN IF NOT EXISTS con DEFAULT para cada campo |
| `db/database_renta.py` | Extender `upsert_declaracion()` con campos nuevos |
| `api/schemas_renta.py` | Campos nuevos en `DeclaracionOut` + schema `DatosTributariosIn` para PATCH |
| `api/routers/renta.py` | `PATCH /datos` + `GET /pdf` con guard org_id |
| `services/renta/tax_engine.py` | Límite 40%/1.340 UVT, cédula dividendos, ganancias ocasionales, overrides, patrimonio líquido |
| `services/renta/pdf_formulario210.py` | Nuevo — generador HTML→PDF con WeasyPrint |
| `taxops-web/app/(app)/renta/page.tsx` | Zonas A, B y C + botón Formulario 210 |
| `api/requirements-api.txt` | Agregar `weasyprint` |
| `api/Dockerfile-api` | Deps sistema WeasyPrint + fonts-liberation |
