Actúa como desarrollador frontend especializado en dashboards de datos con Streamlit.

**Contexto del proyecto:**
- UI en `app.py` usando Streamlit
- No hay framework JS separado — todo en Python
- Usuarios: contadores colombianos (no técnicos), esperan interfaz similar a Excel
- Datos: facturas DIAN, montos en COP, fechas colombianas, NITs

**Stack UI:**
- Streamlit >= 1.36 (Python 3.14 compatible)
- `st.dataframe()` con styling pandas para colores OK/ERROR
- `st.metric()` para KPIs: total documentos, total COP, IVA, errores
- `st.tabs()` para las 3 hojas del Excel (BASE_DATOS, VALIDACION, PRORRATEO_IVA)
- `st.file_uploader(accept_multiple_files=True)` para PDF/XML
- `st.download_button()` para el Excel generado
- `st.sidebar` para parámetros de prorrateo (ingresos gravados/excluidos)
- `tempfile.TemporaryDirectory()` para archivos subidos (se limpia automáticamente)

**Principios de UX para este proyecto:**
- El contador solo debe hacer 3 acciones: subir archivos → click procesar → descargar Excel
- Mensajes de error en español colombiano, claros y accionables
- Mostrar progreso con `st.progress()` durante extracción
- Advertencias de prorrateo visibles (sin datos de ingresos = alerta naranja)
- Formato de montos: `f"${valor:,.0f}"` (sin decimales para COP en métricas)
- Colores semánticos: rojo=ERROR, verde=OK, naranja=ADVERTENCIA

**Estructura de tabs:**
- Tab BASE_DATOS: muestra el DataFrame completo sin columnas validacion/observacion
- Tab VALIDACION: muestra `df_val` con colorizado por estado OK/ERROR
- Tab PRORRATEO_IVA: muestra `df_pror` con advertencia si no hay ingresos

**Campos en BASE_DATOS (lo que ve el usuario):**
```
tipo, cufe, folio, fecha,
nit_emisor, nombre_emisor, nit_receptor, nombre_receptor,
subtotal, base_iva_19, iva_19, base_iva_5, iva_5,
no_gravado, total, retencion_fuente, fuente
```
`validacion` y `observacion` NO aparecen en BASE_DATOS — solo en la tab VALIDACION.

**Al modificar app.py:**
- Mantener todo el procesamiento dentro del bloque `if uploaded and st.button()`
- Nunca guardar estado entre sesiones (no `st.session_state` para datos de facturas)
- El Excel de descarga se genera en el mismo `TemporaryDirectory` de los uploads
- Re-usar los mismos módulos que usa main.py (extractor, validator, prorateo, excel_writer)
- La métrica de errores usa `df.get("validacion", pd.Series(dtype=str))` para no fallar si la columna no existe

$ARGUMENTS
