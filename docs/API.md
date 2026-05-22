# TaxOps — API Reference

Base URL local: `http://localhost:8000`  
Documentación interactiva: `http://localhost:8000/docs` (Swagger UI)

Todos los endpoints excepto `/health`, `/auth/token` y `/auth/register` requieren:
```
Authorization: Bearer <access_token>
```

---

## Health

### `GET /health`

Verificación de estado del servicio.

**Response `200`:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Auth — `/auth`

### `POST /auth/register`

Crear nuevo usuario.

**Body:**
```json
{
  "email": "contador@empresa.co",
  "password": "MiClave123!",
  "nombre": "Ana García"
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "email": "contador@empresa.co",
  "nombre": "Ana García",
  "rol": "user"
}
```

**Errores:**
- `400` — Email ya registrado
- `422` — Validación fallida (password < 8 chars, email inválido)

---

### `POST /auth/token`

Login — obtener access + refresh token.

**Body (form-data o JSON):**
```json
{
  "username": "contador@empresa.co",
  "password": "MiClave123!"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errores:**
- `401` — Credenciales inválidas

---

### `POST /auth/refresh`

Renovar access token usando refresh token.

**Body:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errores:**
- `401` — Refresh token inválido o expirado

---

### `GET /auth/me`

Perfil del usuario autenticado.

**Response `200`:**
```json
{
  "id": "uuid",
  "email": "contador@empresa.co",
  "nombre": "Ana García",
  "rol": "user",
  "tenant_id": "uuid-empresa"
}
```

---

## Nómina — `/nomina`

### `GET /nomina/parametros`

Parámetros legales CST 2026.

**Response `200`:**
```json
{
  "smlmv": 1750905,
  "aux_transporte": 249095,
  "tope_aux_transporte": 3501810,
  "salario_integral_minimo": 22761765,
  "arl_clases": {
    "1": "Clase I – Riesgo mínimo",
    "2": "Clase II – Riesgo bajo",
    "3": "Clase III – Riesgo medio",
    "4": "Clase IV – Riesgo alto",
    "5": "Clase V – Riesgo máximo"
  },
  "arl_rates": {
    "1": 0.00522,
    "2": 0.01044,
    "3": 0.02436,
    "4": 0.04350,
    "5": 0.06960
  },
  "ano": 2026
}
```

---

### `POST /nomina/mensual`

Calcular nómina mensual completa.

**Body:**
```json
{
  "salario_basico": 1750905,
  "dias_trabajados": 30,
  "clase_riesgo_arl": 1,
  "tipo_salario": "ordinario",
  "hed": 0,
  "hen": 0,
  "rn": 0,
  "hod": 0,
  "hedd": 0,
  "hend": 0,
  "rnd": 0,
  "bonificaciones_salariales": 0,
  "comisiones": 0,
  "otros_no_salariales": 0,
  "retencion_fuente": 0,
  "otras_deducciones": 0
}
```

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `salario_basico` | float | — | Salario mensual base (requerido) |
| `dias_trabajados` | int | 30 | Días del período (1–31) |
| `clase_riesgo_arl` | int | 1 | Clase ARL (1–5) |
| `tipo_salario` | str | `"ordinario"` | `"ordinario"` o `"integral"` |
| `hed`–`rnd` | float | 0 | Horas extras/recargos (número de horas) |
| `bonificaciones_salariales` | float | 0 | Bonificaciones que forman IBC |
| `comisiones` | float | 0 | Comisiones que forman IBC |
| `otros_no_salariales` | float | 0 | Pagos no salariales (no afectan IBC) |
| `retencion_fuente` | float | 0 | Retención en la fuente informada |
| `otras_deducciones` | float | 0 | Préstamos, embargos, etc. |

**Response `200`:**
```json
{
  "devengado": {
    "salario_proporcional": 1750905,
    "auxilio_transporte": 249095,
    "aplica_aux_transporte": true,
    "horas_extras": {
      "hed": 0, "hen": 0, "rn": 0, "hod": 0,
      "hedd": 0, "hend": 0, "rnd": 0, "subtotal": 0
    },
    "bonificaciones": 0,
    "comisiones": 0,
    "otros_no_salariales": 0,
    "total_devengado": 2000000
  },
  "deducciones": {
    "ibc": 1750905,
    "salud_empleado": 70036,
    "pension_empleado": 70036,
    "fsp": 0,
    "retencion_fuente": 0,
    "otras": 0,
    "total_deducciones": 140072
  },
  "carga_patronal": {
    "pension": 210109,
    "salud_empleador": 148827,
    "arl": 9140,
    "sena": 0,
    "icbf": 0,
    "caja_compensacion": 70036,
    "exonerado_sena_icbf": true,
    "total": 438112,
    "costo_total_empresa": 2438112
  },
  "neto_pagar": 1859928
}
```

**Notas de cálculo:**
- `auxilio_transporte` se suma al devengado si `salario_basico ≤ 2 × SMLMV` (tipo ordinario)
- `ibc` = salario + HE + bonificaciones + comisiones (sin aux. transporte ni no salariales)
- `ibc` se topa a `25 × SMLMV = $43,772,625`
- Exoneración SENA + ICBF si `salario_basico ≤ 10 × SMLMV` (Art. 114-1 ET)
- `fsp` aplica si `ibc ≥ 4 × SMLMV`
- Salario integral: no aplica aux. transporte, HE, ni exoneración

**Tipos de horas extras (recargo sobre valor hora ordinaria):**

| Campo | Tipo | Recargo |
|-------|------|---------|
| `hed` | Extra Diurna | +25% |
| `hen` | Extra Nocturna | +75% |
| `rn` | Recargo Nocturno | +35% |
| `hod` | Dominical / Festivo | +75% |
| `hedd` | Extra Diurna Dominical | +100% |
| `hend` | Extra Nocturna Dominical | +150% |
| `rnd` | Recargo Nocturno Dominical | +110% |

---

### `POST /nomina/liquidacion`

Calcular liquidación definitiva.

**Body:**
```json
{
  "salario_basico": 1750905,
  "fecha_ingreso": "2024-01-15",
  "fecha_retiro": "2026-05-10",
  "tipo_contrato": "indefinido",
  "causa_terminacion": "renuncia",
  "tipo_salario": "ordinario",
  "promedio_he_recargos": 0,
  "promedio_bonif_salariales": 0,
  "dias_vacaciones_disfrutadas": 15,
  "anticipo_cesantias": 0,
  "otras_deducciones": 0
}
```

| Campo | Valores | Descripción |
|-------|---------|-------------|
| `tipo_contrato` | `indefinido`, `termino_fijo`, `obra_labor` | Tipo de contrato laboral |
| `causa_terminacion` | `renuncia`, `sin_justa_causa_empleador`, `justa_causa`, `mutuo_acuerdo`, `vencimiento` | Determina indemnización Art. 64 CST |

**Response `200`:**
```json
{
  "tiempo": {
    "fecha_ingreso": "2024-01-15",
    "fecha_retiro": "2026-05-10",
    "dias_trabajados": 845
  },
  "bases": {
    "salario_base_prestacional": 1750905,
    "salario_base_vacaciones": 1750905,
    "aplica_aux_transporte": true
  },
  "prestaciones": {
    "cesantias": 4119715,
    "intereses_cesantias": 494366,
    "prima_servicios": 2059858,
    "vacaciones": 970503,
    "salario_pendiente": 291817
  },
  "indemnizacion": {
    "valor": 0,
    "detalle": "Renuncia voluntaria: sin indemnización"
  },
  "dias_auditoria": {
    "cesantias": 845,
    "prima": 845,
    "vacaciones_causadas": 42,
    "vacaciones_a_pagar": 27
  },
  "totales": {
    "subtotal_devengado": 7936259,
    "deducciones": 0,
    "total_neto": 7936259
  }
}
```

**Fórmulas de prestaciones (base 360):**
- Cesantías: `salario_base × días / 360`
- Intereses: `cesantías × 0.12 × días / 360`
- Prima: `salario_base × días_sem / 360` (dos semestres en el año)
- Vacaciones: `salario_base_vac × días_pendientes / 720`

---

### `POST /nomina/export`

Descargar Excel de nómina mensual o liquidación.

**Body:**
```json
{
  "tipo": "mensual",
  "salario_basico": 1750905,
  ...mismos campos que /nomina/mensual o /nomina/liquidacion...
}
```

**Response `200`:**
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename=taxops_nomina_mensual_2026-05-10.xlsx`

El Excel incluye:
- Header azul navy (`#1A3A5C`) con "TaxOps — Nómina Mensual / Liquidación"
- Secciones con bordes y sombreado
- Totales en naranja (`#E05519`)
- Fila resumen: Neto a Pagar / Total Neto

---

### `POST /nomina/export-pdf`

Descargar PDF de nómina mensual o liquidación (generado con ReportLab, sin Chromium).

**Body:** Mismo que `/nomina/export`

**Response `200`:**
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename=taxops_nomina_mensual_2026-05-10.pdf`

---

### `POST /nomina/import-batch`

Importar lista de empleados desde Excel (.xlsx/.xls) o CSV.

**Request:** `multipart/form-data`
```
file: <archivo.xlsx o archivo.csv>
```

**Columnas del archivo:**

| Columna | Requerida | Tipo | Default |
|---------|-----------|------|---------|
| `nombre` | ✅ | texto | — |
| `salario_basico` | ✅ | número | — |
| `dias_trabajados` | No | entero | 30 |
| `clase_riesgo_arl` | No | entero 1–5 | 1 |
| `tipo_salario` | No | texto | `ordinario` |

**Response `200`:**
```json
[
  {
    "nombre": "Juan Pérez",
    "salario": 1750905,
    "neto": 1859928,
    "carga": 438112,
    "costo": 2438112
  },
  {
    "nombre": "María López",
    "salario": 3500000,
    "neto": 3115000,
    "carga": 756000,
    "costo": 4256000
  }
]
```

Si una fila tiene error (ej. salario inválido), el campo `error` estará presente:
```json
{ "nombre": "Carlos", "salario": 0, "neto": 0, "carga": 0, "costo": 0, "error": "Salario inválido" }
```

---

### `POST /nomina/export-batch`

Exportar resultados de batch a Excel.

**Body:**
```json
{
  "rows": [
    { "nombre": "Juan Pérez", "salario": 1750905, "neto": 1859928, "carga": 438112, "costo": 2438112 },
    { "nombre": "María López", "salario": 3500000, "neto": 3115000, "carga": 756000, "costo": 4256000 }
  ]
}
```

**Response `200`:**
- Excel con headers navy, filas alternas, fila de totales en naranja
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

---

## Facturas — `/facturas`

### `POST /facturas/upload`

Subir uno o más archivos PDF/XML DIAN.

**Request:** `multipart/form-data`
```
files: <archivo1.pdf>
files: <archivo2.xml>
ingresos_gravados: 5000000    (opcional, para prorrateo)
ingresos_excluidos: 1000000   (opcional)
```

**Response `200`:**
```json
{
  "procesados": 2,
  "insertados": 2,
  "duplicados": 0,
  "errores": [],
  "facturas": [
    {
      "id": "uuid",
      "cufe": "96chars...",
      "tipo": "Factura Electrónica",
      "folio": "FE-001",
      "fecha": "2026-03-15",
      "nit_emisor": "900123456-7",
      "nombre_emisor": "PROVEEDOR SA",
      "total": 1190000,
      "iva_19": 190000,
      "retencion_fuente": 25000,
      "validacion": "OK"
    }
  ]
}
```

---

### `GET /facturas/`

Listar facturas del tenant autenticado.

**Query params:**
- `skip` (int, default 0)
- `limit` (int, default 100)
- `mes` (str, opcional, ej. `"2026-03"`)
- `tipo` (str, opcional, ej. `"Factura Electrónica"`)

**Response `200`:** Array de facturas

---

### `POST /facturas/export`

Descargar Excel con 3 hojas.

**Body (opcional):**
```json
{
  "mes": "2026-03",
  "ingresos_gravados": 5000000,
  "ingresos_excluidos": 1000000
}
```

**Response:** Excel con hojas BASE_DATOS, VALIDACION, PRORRATEO_IVA

---

## Chatbot — `/chatbot`

### `POST /chatbot/mensaje`

Enviar mensaje al asistente contable.

**Body:**
```json
{
  "mensaje": "¿Cuánto IVA pagué en marzo?",
  "modulo": "facturas",
  "contexto": { "mes": "2026-03", "total_iva": 2500000 }
}
```

**Response `200`:**
```json
{
  "respuesta": "En marzo 2026 pagaste $2,500,000 de IVA distribuidos en...",
  "tokens_usados": 312
}
```

---

### `GET /chatbot/historial`

Historial de mensajes de la sesión del usuario autenticado.

**Response `200`:**
```json
[
  { "rol": "user", "contenido": "¿Qué es el CUFE?", "ts": "2026-05-10T10:30:00Z" },
  { "rol": "assistant", "contenido": "El CUFE es el Código Único...", "ts": "2026-05-10T10:30:05Z" }
]
```

---

### `DELETE /chatbot/historial`

Limpiar historial de la sesión actual.

**Response `204`:** Sin contenido

---

## Códigos de error comunes

| Código | Significado |
|--------|-------------|
| `400` | Bad Request — datos inválidos o faltantes |
| `401` | Unauthorized — token expirado o inválido |
| `403` | Forbidden — sin permisos para el recurso |
| `404` | Not Found — recurso no existe |
| `409` | Conflict — ej. email ya registrado, CUFE duplicado |
| `422` | Unprocessable Entity — validación Pydantic fallida |
| `500` | Internal Server Error — error inesperado del servidor |

**Formato de error:**
```json
{
  "detail": "Descripción del error"
}
```

Para errores de validación `422`:
```json
{
  "detail": [
    {
      "loc": ["body", "salario_basico"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```
