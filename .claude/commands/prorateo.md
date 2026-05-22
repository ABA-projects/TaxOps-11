Actúa como especialista en el módulo de prorrateo IVA (prorateo.py) de este sistema.

**Base legal:**
- Art. 490 ET: cuando una empresa tiene ingresos gravados Y excluidos/exentos, el IVA de compras se proratea
- Fórmula: `pct_deducible = ingresos_gravados / (gravados + excluidos)`
- Solo aplica si hay mezcla; si todos los ingresos son gravados → 100% deducible sin prorrateo

**Funciones del módulo:**

`calcular_prorateo(df, ingresos_gravados, ingresos_excluidos)`
- `ingresos_gravados` y `ingresos_excluidos`: dicts `{YYYY-MM: float}` — pueden tener meses distintos
- Agrupa por mes (campo `fecha[:7]`)
- Mandatos siempre van a `iva_mandatos` (no descontable), independiente del prorrateo
- Notas crédito: `iva_19` y `iva_5` son negativos → reducen automáticamente el total del mes
- Nota Débito: mismo tratamiento que Factura (suma al mes)
- Retorna DataFrame con columnas: `mes, iva_total, iva_mandatos, iva_base_prorateo, pct_prorateo, iva_descontable, iva_no_descontable`

`calcular_prorateo_simple(df)`
- Versión sin datos de ingresos → asume 100% deducible
- Agrega columna `advertencia` = "Sin datos de ingresos: se asume 100% descontable"
- Usar cuando el usuario no pasó `--ingresos` al CLI

**Reglas críticas de clasificación:**
```python
# Mandatos: SIEMPRE no descontable
es_mandato = tipo in ("Mandato/Peaje",)

# Prorrateo aplica solo al IVA no-mandato
iva_base_prorateo = iva_total - iva_mandatos
iva_descontable = iva_base_prorateo * pct_prorateo
iva_no_descontable = iva_base_prorateo * (1 - pct_prorateo) + iva_mandatos
```

**Casos edge importantes:**
- Mes con SOLO mandatos → `iva_base_prorateo = 0`, `pct_prorateo = N/A`, `iva_descontable = 0`
- Mes sin documentos pero con ingresos informados → no aparece en el DataFrame (no generar fila vacía)
- Ingresos excluidos = 0 → `pct_prorateo = 1.0` (100%), no dividir por cero
- Ingresos gravados = 0 → `pct_prorateo = 0.0` (0% deducible)

**Validaciones de entrada:**
- `ingresos_gravados` y `ingresos_excluidos` pueden tener meses sin documentos (ignorar)
- Si un mes tiene documentos pero no tiene datos de ingresos → usar `calcular_prorateo_simple` para ese mes con advertencia

**Al modificar prorateo.py:**
- El módulo debe ser stateless (solo recibe DataFrame, retorna DataFrame)
- No tiene side effects de I/O (ni logs, ni archivos)
- Las columnas `validacion`/`observacion` nunca entran aquí — ya están en validator.py
- Mantener la separación: extracción ≠ validación ≠ prorrateo

**Tests relevantes:**
```bash
python -m pytest tests/test_prorateo.py -v
```
Casos mínimos a cubrir:
- Sin ingresos → pct=100%, advertencia presente
- 50/50 → pct=50%
- Solo mandatos → iva_descontable=0
- Nota crédito reduce el mes
- Mes con ingresos excluidos=0 → no divide por cero

$ARGUMENTS
