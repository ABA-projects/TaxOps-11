# Webapp V2 + Accounting Assistant Chatbot — Design Spec

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Construir una segunda app Streamlit (`app_v2.py`) con chatbot de contabilidad integrado (Claude API), desplegable en Streamlit Community Cloud vía GitHub, sin tocar el `app.py` existente que está en producción local.

**Architecture:** Solución paralela — todos los módulos de negocio existentes (`extractor.py`, `validator.py`, `prorateo.py`, `excel_writer.py`) se reutilizan sin modificación. La nueva `app_v2.py` agrega modo carpeta local, historial de chat, y un `chatbot.py` con tool use de Claude API.

**Tech Stack:** Python 3.14, Streamlit ≥1.36, Anthropic SDK (`anthropic>=0.40`), Claude claude-sonnet-4-6, Streamlit Community Cloud (deploy gratuito desde GitHub)

---

## Principio crítico: No tocar lo existente

```
app.py       ← INTACTO para siempre
main.py      ← INTACTO
extractor.py ← INTACTO
validator.py ← INTACTO
prorateo.py  ← INTACTO
excel_writer.py ← INTACTO
watcher.py   ← INTACTO
```

Solo se agregan archivos nuevos. Nunca se editan los existentes.

---

## Archivos nuevos

| Archivo | Responsabilidad |
|---------|----------------|
| `app_v2.py` | Nueva UI Streamlit: upload + modo carpeta + tabs + chatbot |
| `chatbot.py` | Accounting Assistant con Claude API y tool use |
| `.streamlit/config.toml` | Config de deploy (tema, servidor) |

`requirements.txt` se actualiza agregando `anthropic>=0.40`.

---

## app_v2.py — Diseño de UI

### Sidebar
- Toggle: **"Modo upload"** (subir archivos) vs **"Modo carpeta local"** (apuntar a ruta del servidor)
- Ingresos para prorrateo (igual que app.py actual)
- Campo ANTHROPIC_API_KEY si no está en env var

### Tabs principales
1. **PROCESAR** — upload o carpeta, botón procesar, progreso, métricas, descarga Excel
2. **BASE_DATOS** — DataFrame sin validacion/observacion
3. **VALIDACION** — DataFrame con colores OK/ERROR
4. **PRORRATEO_IVA** — DataFrame con advertencia si no hay ingresos
5. **CHATBOT** — Accounting Assistant (solo activo después de procesar)

### Estado de sesión (`st.session_state`)
```python
st.session_state.df          # DataFrame procesado
st.session_state.df_val      # DataFrame validación
st.session_state.df_pror     # DataFrame prorrateo
st.session_state.messages    # historial chat [{role, content}]
st.session_state.processed   # bool: si ya se procesó
```

---

## chatbot.py — Accounting Assistant

### Filosofía
- El chatbot responde en español colombiano
- Tiene acceso al DataFrame de la sesión actual
- Usa Claude API con tool use para operaciones estructuradas
- Diseñado para crecer: agregar herramientas nuevas sin cambiar la arquitectura

### Herramientas iniciales (tool use)

```python
tools = [
    {
        "name": "consultar_iva_mes",
        "description": "Retorna IVA total, descontable y no descontable para un mes YYYY-MM",
        "input_schema": {"type": "object", "properties": {"mes": {"type": "string"}}}
    },
    {
        "name": "top_proveedores",
        "description": "Top N proveedores por gasto total",
        "input_schema": {"type": "object", "properties": {"n": {"type": "integer", "default": 10}}}
    },
    {
        "name": "buscar_factura",
        "description": "Busca facturas por folio, NIT emisor o nombre",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
    },
    {
        "name": "resumen_errores",
        "description": "Lista facturas con errores de validación y su observación",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "resumen_general",
        "description": "KPIs generales: total documentos, total COP, IVA, errores",
        "input_schema": {"type": "object", "properties": {}}
    }
]
```

### System prompt del chatbot
```
Eres un asistente contable especializado en facturación electrónica colombiana (DIAN).
Tienes acceso a las facturas procesadas de esta sesión.
Respondes en español colombiano, citando artículos del ET cuando sea relevante.
Cuando el usuario pregunta algo que puedes resolver con una herramienta, úsala.
Si no tienes datos procesados, pide que el usuario procese primero sus facturas.
```

### Interfaz en Streamlit
```python
# Historial visual
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
if prompt := st.chat_input("Pregunta sobre tus facturas..."):
    # llamar chatbot.responder(prompt, df, historial)
    # agregar al historial
    # mostrar respuesta
```

---

## Deploy en Streamlit Community Cloud

### Pasos
1. Asegurarse de que el repo está en GitHub (público o privado)
2. Ir a [share.streamlit.io](https://share.streamlit.io) → "New app"
3. Seleccionar repo → branch `main` → archivo `app_v2.py`
4. En "Advanced settings" → agregar secret: `ANTHROPIC_API_KEY`
5. Deploy → URL: `https://<usuario>-proyecto-facturas.streamlit.app`

### `.streamlit/config.toml`
```toml
[server]
maxUploadSize = 200

[theme]
primaryColor = "#1f4e79"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
```

---

## Extensibilidad del chatbot

El diseño de `chatbot.py` permite agregar herramientas futuras sin modificar `app_v2.py`:
- `descargar_desde_dian(credenciales)` — descarga automática
- `generar_borrador_declaracion(periodo)` — pre-llenar formulario 300
- `alertar_vencimientos()` — facturas próximas a vencer
- `comparar_periodos(mes1, mes2)` — análisis comparativo

---

## Testing

- `app_v2.py`: test manual en local antes de deploy
- `chatbot.py`: unit tests con DataFrame mock, sin llamar a la API real
- Flujo completo: subir 3 facturas de prueba → procesar → preguntar al chatbot

---

## Decisiones de diseño

- **Sin base de datos**: el chatbot opera sobre el DataFrame en memoria de la sesión. No persiste entre sesiones (YAGNI para Fase 1).
- **API key en secrets**: nunca hardcodeada. En local se lee de variable de entorno `ANTHROPIC_API_KEY`.
- **app.py intacto**: el contador que usa la versión local no se ve afectado por ningún cambio.
