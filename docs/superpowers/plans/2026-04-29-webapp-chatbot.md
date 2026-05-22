# Webapp V2 + Accounting Assistant Chatbot — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir `app_v2.py` (nueva Streamlit con modo carpeta + chatbot) y `chatbot.py` (Accounting Assistant con Claude API tool use), sin modificar ningún archivo existente, desplegable en Streamlit Community Cloud.

**Architecture:** Solución 100% paralela. Los módulos existentes (`extractor.py`, `validator.py`, `prorateo.py`, `excel_writer.py`) se importan pero nunca se editan. `chatbot.py` encapsula toda la lógica del asistente con tool use; `app_v2.py` solo orquesta UI y estado de sesión.

**Tech Stack:** Python 3.14, Streamlit ≥1.36, anthropic ≥0.40 (Claude claude-sonnet-4-6), pytest, Streamlit Community Cloud

---

## Regla de oro
**NUNCA editar:** `app.py`, `main.py`, `extractor.py`, `validator.py`, `prorateo.py`, `excel_writer.py`, `watcher.py`

Solo se crean archivos nuevos o se agrega una línea a `requirements.txt`.

---

## Mapa de archivos

| Acción | Archivo | Responsabilidad |
|--------|---------|----------------|
| Modificar | `requirements.txt` | Agregar `anthropic>=0.40` |
| Crear | `.streamlit/config.toml` | Tema + límite upload para cloud |
| Crear | `chatbot.py` | Accounting Assistant: tools + loop Claude API |
| Crear | `tests/test_chatbot.py` | Unit tests con df mock, sin llamar API real |
| Crear | `app_v2.py` | Nueva UI: 5 tabs + session state + modo carpeta |

---

## Chunk 1: Setup base

### Task 1: Dependencia anthropic + config Streamlit

**Files:**
- Modify: `requirements.txt`
- Create: `.streamlit/config.toml`

- [ ] **Step 1: Agregar anthropic a requirements.txt**

Agregar al final de `requirements.txt`:
```
anthropic>=0.40
```

- [ ] **Step 2: Crear `.streamlit/config.toml`**

```toml
[server]
maxUploadSize = 200

[theme]
primaryColor = "#1f4e79"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
```

- [ ] **Step 3: Instalar la nueva dependencia**

```bash
pip install anthropic>=0.40
```

Verificar:
```bash
python -c "import anthropic; print(anthropic.__version__)"
```
Expected: versión ≥ 0.40

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .streamlit/config.toml
git commit -m "feat: add anthropic dependency and streamlit cloud config"
```

---

## Chunk 2: chatbot.py — Accounting Assistant

### Task 2: Tests del chatbot (primero)

**Files:**
- Create: `tests/test_chatbot.py`

- [ ] **Step 1: Crear `tests/test_chatbot.py` con DataFrame mock**

```python
"""Tests para chatbot.py — no llaman a la API real de Claude."""
import pandas as pd
import pytest
from chatbot import (
    _tool_consultar_iva_mes,
    _tool_top_proveedores,
    _tool_buscar_factura,
    _tool_resumen_errores,
    _tool_resumen_general,
)


@pytest.fixture
def df_mock():
    return pd.DataFrame([
        {
            "tipo": "Factura Electrónica", "folio": "FE-001", "fecha": "2026-03-15",
            "nit_emisor": "900123456", "nombre_emisor": "Proveedor Alpha S.A.S",
            "nit_receptor": "901050311", "nombre_receptor": "Mi Empresa",
            "subtotal": 1_000_000, "base_iva_19": 1_000_000, "iva_19": 190_000,
            "base_iva_5": 0, "iva_5": 0, "no_gravado": 0,
            "total": 1_190_000, "retencion_fuente": 25_000, "fuente": "XML",
            "validacion": "OK", "observacion": "",
        },
        {
            "tipo": "Factura Electrónica", "folio": "FE-002", "fecha": "2026-03-20",
            "nit_emisor": "800987654", "nombre_emisor": "Proveedor Beta Ltda",
            "nit_receptor": "901050311", "nombre_receptor": "Mi Empresa",
            "subtotal": 2_000_000, "base_iva_19": 2_000_000, "iva_19": 380_000,
            "base_iva_5": 0, "iva_5": 0, "no_gravado": 0,
            "total": 2_380_000, "retencion_fuente": 50_000, "fuente": "PDF",
            "validacion": "ERROR", "observacion": "CUFE vacío",
        },
        {
            "tipo": "Mandato/Peaje", "folio": "MAN-001", "fecha": "2026-04-05",
            "nit_emisor": "700111222", "nombre_emisor": "Concesión Vial",
            "nit_receptor": "901050311", "nombre_receptor": "Mi Empresa",
            "subtotal": 500_000, "base_iva_19": 0, "iva_19": 0,
            "base_iva_5": 0, "iva_5": 0, "no_gravado": 500_000,
            "total": 500_000, "retencion_fuente": 0, "fuente": "PDF",
            "validacion": "OK", "observacion": "",
        },
    ])


def test_consultar_iva_mes_existente(df_mock):
    result = _tool_consultar_iva_mes(df_mock, "2026-03")
    assert "570.000" in result or "570000" in result.replace(".", "").replace(",", "")
    assert "2026-03" in result


def test_consultar_iva_mes_sin_datos(df_mock):
    result = _tool_consultar_iva_mes(df_mock, "2025-01")
    assert "no hay documentos" in result.lower() or "sin datos" in result.lower()


def test_top_proveedores(df_mock):
    result = _tool_top_proveedores(df_mock, n=2)
    assert "Proveedor Beta" in result or "800987654" in result
    assert "Proveedor Alpha" in result or "900123456" in result


def test_buscar_factura_por_folio(df_mock):
    result = _tool_buscar_factura(df_mock, "FE-001")
    assert "FE-001" in result
    assert "Proveedor Alpha" in result


def test_buscar_factura_sin_resultados(df_mock):
    result = _tool_buscar_factura(df_mock, "FE-999")
    assert "no se encontraron" in result.lower() or "sin resultados" in result.lower()


def test_resumen_errores(df_mock):
    result = _tool_resumen_errores(df_mock)
    assert "FE-002" in result
    assert "CUFE" in result


def test_resumen_errores_sin_errores():
    df = pd.DataFrame([{
        "tipo": "Factura Electrónica", "folio": "FE-OK", "fecha": "2026-03-01",
        "nit_emisor": "900000001", "nombre_emisor": "Ok S.A.S",
        "subtotal": 100_000, "iva_19": 19_000, "total": 119_000,
        "validacion": "OK", "observacion": "",
    }])
    result = _tool_resumen_errores(df)
    assert "sin errores" in result.lower() or "no hay errores" in result.lower()


def test_resumen_general(df_mock):
    result = _tool_resumen_general(df_mock)
    assert "3" in result  # 3 documentos
    assert "ERROR" in result or "error" in result.lower()
```

- [ ] **Step 2: Correr tests — deben fallar (chatbot.py no existe)**

```bash
python -m pytest tests/test_chatbot.py -v
```
Expected: `ImportError` o `ModuleNotFoundError` — chatbot no existe aún.

---

### Task 3: Implementar chatbot.py

**Files:**
- Create: `chatbot.py`

- [ ] **Step 1: Crear `chatbot.py`**

```python
"""Accounting Assistant — Claude API con tool use sobre DataFrame de facturas DIAN."""

from __future__ import annotations

import os
import json
import pandas as pd
import anthropic

# ── Constantes ────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """Eres un asistente contable especializado en facturación electrónica \
colombiana (DIAN). Tienes acceso a las facturas procesadas de esta sesión de trabajo.
Respondes en español colombiano, de forma clara y concisa.
Cuando sea relevante, cita artículos del Estatuto Tributario (ET).
Usa las herramientas disponibles cuando el usuario pregunte sobre datos de sus facturas.
Si no hay facturas procesadas aún, indica amablemente que debe procesar primero sus archivos."""

TOOLS: list[dict] = [
    {
        "name": "consultar_iva_mes",
        "description": (
            "Retorna IVA total, IVA descontable (facturas normales) e IVA de mandatos "
            "para un mes específico en formato YYYY-MM."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "string", "description": "Mes en formato YYYY-MM, ej: 2026-03"}
            },
            "required": ["mes"],
        },
    },
    {
        "name": "top_proveedores",
        "description": "Lista los N proveedores con mayor gasto total (subtotal) en el período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Número de proveedores a mostrar", "default": 10}
            },
        },
    },
    {
        "name": "buscar_factura",
        "description": "Busca facturas por folio, NIT emisor, o nombre del emisor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto a buscar: folio, NIT o nombre"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "resumen_errores",
        "description": "Lista todas las facturas con errores de validación y su observación.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resumen_general",
        "description": (
            "KPIs generales: total de documentos, suma total COP, IVA 19%, IVA 5%, "
            "cantidad de errores de validación."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ── Implementación de herramientas ────────────────────────────────────────────

def _fmt_cop(valor: float) -> str:
    return f"${valor:,.0f} COP"


def _tool_consultar_iva_mes(df: pd.DataFrame, mes: str) -> str:
    df_mes = df[df["fecha"].str.startswith(mes, na=False)]
    if df_mes.empty:
        return f"No hay documentos registrados para {mes}."
    mandatos = df_mes[df_mes["tipo"].str.contains("mandato|peaje", case=False, na=False)]
    normales = df_mes[~df_mes["tipo"].str.contains("mandato|peaje", case=False, na=False)]
    iva_total = df_mes["iva_19"].sum() + df_mes["iva_5"].sum()
    iva_mandatos = mandatos["iva_19"].sum() + mandatos["iva_5"].sum()
    iva_descontable = normales["iva_19"].sum() + normales["iva_5"].sum()
    return (
        f"**IVA {mes}**\n"
        f"- IVA total: {_fmt_cop(iva_total)}\n"
        f"- IVA descontable (facturas normales): {_fmt_cop(iva_descontable)}\n"
        f"- IVA mandatos/peajes (no descontable): {_fmt_cop(iva_mandatos)}\n"
        f"- Documentos en el mes: {len(df_mes)}"
    )


def _tool_top_proveedores(df: pd.DataFrame, n: int = 10) -> str:
    if "nombre_emisor" not in df.columns:
        return "No hay datos de proveedores disponibles."
    top = (
        df.groupby(["nit_emisor", "nombre_emisor"])["subtotal"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )
    if top.empty:
        return "No hay datos de proveedores."
    lines = [f"**Top {n} proveedores por gasto:**"]
    for i, row in top.iterrows():
        lines.append(f"{i+1}. {row['nombre_emisor']} (NIT {row['nit_emisor']}): {_fmt_cop(row['subtotal'])}")
    return "\n".join(lines)


def _tool_buscar_factura(df: pd.DataFrame, query: str) -> str:
    q = query.lower().strip()
    mask = (
        df.get("folio", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
        | df.get("nit_emisor", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
        | df.get("nombre_emisor", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
    )
    resultado = df[mask]
    if resultado.empty:
        return f"No se encontraron facturas con '{query}'."
    cols = ["folio", "fecha", "nombre_emisor", "nit_emisor", "total", "validacion"]
    cols_present = [c for c in cols if c in resultado.columns]
    lines = [f"**{len(resultado)} factura(s) encontrada(s):**"]
    for _, row in resultado[cols_present].iterrows():
        total_str = _fmt_cop(row["total"]) if "total" in row else "N/D"
        lines.append(
            f"- {row.get('folio','?')} | {row.get('fecha','?')} | "
            f"{row.get('nombre_emisor','?')} | {total_str} | {row.get('validacion','?')}"
        )
    return "\n".join(lines)


def _tool_resumen_errores(df: pd.DataFrame) -> str:
    if "validacion" not in df.columns:
        return "No hay datos de validación disponibles."
    errores = df[df["validacion"] == "ERROR"]
    if errores.empty:
        return "Sin errores de validación. Todas las facturas están OK."
    lines = [f"**{len(errores)} factura(s) con errores:**"]
    for _, row in errores.iterrows():
        lines.append(
            f"- {row.get('folio','?')} | {row.get('nombre_emisor','?')} | "
            f"{row.get('observacion','sin detalle')}"
        )
    return "\n".join(lines)


def _tool_resumen_general(df: pd.DataFrame) -> str:
    total_docs = len(df)
    total_cop = df.get("total", pd.Series(dtype=float)).sum()
    iva_19 = df.get("iva_19", pd.Series(dtype=float)).sum()
    iva_5 = df.get("iva_5", pd.Series(dtype=float)).sum()
    errores = int((df.get("validacion", pd.Series(dtype=str)) == "ERROR").sum())
    return (
        f"**Resumen general**\n"
        f"- Documentos procesados: {total_docs}\n"
        f"- Total COP: {_fmt_cop(total_cop)}\n"
        f"- IVA 19%: {_fmt_cop(iva_19)}\n"
        f"- IVA 5%: {_fmt_cop(iva_5)}\n"
        f"- Errores de validación: {errores}"
    )


# ── Dispatcher de herramientas ────────────────────────────────────────────────

def _ejecutar_herramienta(nombre: str, args: dict, df: pd.DataFrame) -> str:
    if nombre == "consultar_iva_mes":
        return _tool_consultar_iva_mes(df, args.get("mes", ""))
    if nombre == "top_proveedores":
        return _tool_top_proveedores(df, args.get("n", 10))
    if nombre == "buscar_factura":
        return _tool_buscar_factura(df, args.get("query", ""))
    if nombre == "resumen_errores":
        return _tool_resumen_errores(df)
    if nombre == "resumen_general":
        return _tool_resumen_general(df)
    return f"Herramienta '{nombre}' no reconocida."


# ── Función principal ─────────────────────────────────────────────────────────

def responder(
    prompt: str,
    df: pd.DataFrame | None,
    historial: list[dict],
    api_key: str | None = None,
) -> str:
    """
    Llama a Claude con tool use y retorna la respuesta en texto.

    Args:
        prompt: Pregunta del usuario.
        df: DataFrame con las facturas procesadas (puede ser None si aún no se procesó).
        historial: Lista de mensajes previos [{role, content}].
        api_key: Clave de API opcional (si no está en env ANTHROPIC_API_KEY).
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return "⚠️ Falta la clave ANTHROPIC_API_KEY. Configúrala en el sidebar."

    client = anthropic.Anthropic(api_key=key)

    messages = historial + [{"role": "user", "content": prompt}]

    # Agentic loop — Claude puede usar múltiples herramientas en cadena
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS if df is not None else [],
            messages=messages,
        )

        # Si Claude quiere usar herramientas
        if response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == "tool_use":
                    resultado = _ejecutar_herramienta(block.name, block.input, df)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": resultado,
                    })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
            continue  # siguiente iteración del loop

        # Respuesta final en texto
        texto = next(
            (b.text for b in response.content if hasattr(b, "text")),
            "No se pudo generar una respuesta."
        )
        return texto
```

- [ ] **Step 2: Correr tests — deben pasar**

```bash
python -m pytest tests/test_chatbot.py -v
```
Expected: todos los tests en verde (`PASSED`).

- [ ] **Step 3: Commit**

```bash
git add chatbot.py tests/test_chatbot.py
git commit -m "feat: add accounting assistant chatbot with tool use"
```

---

## Chunk 3: app_v2.py — Nueva UI Streamlit

### Task 4: Implementar app_v2.py

**Files:**
- Create: `app_v2.py`

- [ ] **Step 1: Verificar imports antes de escribir el archivo**

```bash
python -c "from extractor import extract_one; print('extract_one OK')"
python -c "from validator import validate, build_validation_sheet; print('validator OK')"
python -c "from prorateo import calcular_prorateo, calcular_prorateo_simple; print('prorateo OK')"
python -c "from excel_writer import write_excel; print('excel_writer OK')"
```

Expected: las 4 líneas imprimen `OK`. Si `extract_one` falla, ajustar en el archivo a:
```python
from extractor import extract_document as extract_one
```

- [ ] **Step 2: Crear `app_v2.py`**

```python
"""app_v2.py — Facturas DIAN v2: modo upload + carpeta local + Accounting Assistant."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from extractor import extract_one
from validator import validate, build_validation_sheet
from prorateo import calcular_prorateo, calcular_prorateo_simple
from excel_writer import write_excel
import chatbot

# ── Config de página ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Facturas DIAN v2",
    page_icon="🧾",
    layout="wide",
)

# ── Inicializar session state ─────────────────────────────────────────────────
for key, default in [
    ("df", None),
    ("df_val", None),
    ("df_pror", None),
    ("messages", []),
    ("processed", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🧾 Facturas DIAN v2")

    # API Key
    api_key_input = st.text_input(
        "ANTHROPIC_API_KEY",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Requerida para el Accounting Assistant. Se lee de la variable de entorno si está disponible.",
    )

    st.divider()

    # Modo de procesamiento
    modo = st.radio("Modo de entrada", ["📤 Upload archivos", "📁 Carpeta local"])

    st.divider()

    # Ingresos para prorrateo
    st.subheader("Ingresos para Prorrateo")
    st.caption("Opcional. Formato: YYYY-MM=gravados|excluidos")
    meses_input = st.text_area(
        "Un mes por línea",
        placeholder="2026-04=5000000|1000000\n2026-03=4500000|800000",
        height=100,
    )


def _parse_ingresos(raw: str) -> tuple[dict, dict]:
    grav, excl = {}, {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        mes, vals = line.split("=", 1)
        partes = vals.split("|")
        try:
            grav[mes.strip()] = float(partes[0].strip().replace(",", ""))
            if len(partes) > 1:
                excl[mes.strip()] = float(partes[1].strip().replace(",", ""))
        except ValueError:
            pass
    return grav, excl


def _procesar_archivos(archivos: list[Path]) -> None:
    """Extrae, valida y proratea. Guarda resultados en session_state."""
    if not archivos:
        st.warning("No se encontraron archivos PDF o XML.")
        return

    processed: set[str] = set()
    filas = []
    prog = st.progress(0, text="Iniciando extracción...")

    for i, archivo in enumerate(archivos):
        clave = str(archivo.with_suffix("")).lower()
        if clave in processed:
            continue
        processed.add(clave)
        try:
            row = extract_one(archivo)
            if row:
                filas.append(row)
        except Exception as e:
            st.warning(f"Error en {archivo.name}: {e}")
        prog.progress((i + 1) / len(archivos), text=f"Procesando {archivo.name}…")

    prog.empty()

    if not filas:
        st.error("No se pudieron extraer datos de los archivos.")
        return

    df = pd.DataFrame(filas)
    df = validate(df)
    df_val = build_validation_sheet(df)

    grav, excl = _parse_ingresos(meses_input)
    df_pror = calcular_prorateo(df, grav, excl) if grav else calcular_prorateo_simple(df)

    cols_base = [
        "tipo", "cufe", "folio", "fecha",
        "nit_emisor", "nombre_emisor", "nit_receptor", "nombre_receptor",
        "subtotal", "base_iva_19", "iva_19", "base_iva_5", "iva_5",
        "no_gravado", "total", "retencion_fuente", "fuente",
    ]
    df_base = df[[c for c in cols_base if c in df.columns]]

    st.session_state.df = df_base
    st.session_state.df_val = df_val
    st.session_state.df_pror = df_pror
    st.session_state.processed = True
    st.session_state.messages = []  # resetear chat al reprocesar


# ── Tabs ──────────────────────────────────────────────────────────────────────
st.title("🧾 Gestión de Facturas DIAN")

tab_proc, tab_base, tab_val, tab_pror, tab_chat = st.tabs([
    "⚙️ Procesar", "📊 BASE_DATOS", "✅ VALIDACION", "📈 PRORRATEO_IVA", "🤖 Chatbot"
])

# ── Tab PROCESAR ──────────────────────────────────────────────────────────────
with tab_proc:
    if modo == "📤 Upload archivos":
        uploaded = st.file_uploader(
            "Sube tus PDF y/o XML de la DIAN",
            type=["pdf", "xml"],
            accept_multiple_files=True,
        )
        if uploaded and st.button("⚙️ Procesar facturas", type="primary"):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                for f in uploaded:
                    (tmp_path / f.name).write_bytes(f.read())
                archivos = sorted(
                    p for p in tmp_path.rglob("*")
                    if p.suffix.lower() in (".pdf", ".xml")
                )
                _procesar_archivos(archivos)

    else:  # Modo carpeta local
        carpeta_input = st.text_input(
            "Ruta de la carpeta de facturas",
            placeholder="/ruta/a/facturas o C:\\facturas",
        )
        if carpeta_input and st.button("⚙️ Procesar carpeta", type="primary"):
            carpeta = Path(carpeta_input)
            if not carpeta.exists():
                st.error(f"La carpeta no existe: {carpeta}")
            else:
                archivos = sorted(
                    p for p in carpeta.rglob("*")
                    if p.suffix.lower() in (".pdf", ".xml")
                )
                _procesar_archivos(archivos)

    # Métricas y descarga (después de procesar)
    if st.session_state.processed and st.session_state.df is not None:
        df = st.session_state.df
        df_val = st.session_state.df_val
        df_pror = st.session_state.df_pror

        st.subheader("Resumen")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Documentos", len(df))
        c2.metric("Total COP", f"${df['total'].sum():,.0f}" if "total" in df else "N/D")
        c3.metric("IVA 19%", f"${df['iva_19'].sum():,.0f}" if "iva_19" in df else "N/D")
        c4.metric(
            "Errores",
            int((df_val.get("validacion", pd.Series(dtype=str)) == "ERROR").sum())
            if df_val is not None else 0,
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_excel:
            write_excel(df, df_val, df_pror, Path(tmp_excel.name))
            st.download_button(
                "⬇️ Descargar Excel",
                data=Path(tmp_excel.name).read_bytes(),
                file_name="facturas_dian.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# ── Tab BASE_DATOS ────────────────────────────────────────────────────────────
with tab_base:
    if st.session_state.df is not None:
        st.dataframe(st.session_state.df, use_container_width=True)
    else:
        st.info("Procesa tus facturas primero en la pestaña ⚙️ Procesar.")

# ── Tab VALIDACION ────────────────────────────────────────────────────────────
with tab_val:
    if st.session_state.df_val is not None:
        df_val = st.session_state.df_val
        styled = df_val.style.apply(
            lambda col: [
                "background-color:#FF4444;color:white" if v == "ERROR"
                else "background-color:#70AD47;color:white" if v == "OK"
                else ""
                for v in col
            ],
            subset=["validacion"] if "validacion" in df_val.columns else [],
        )
        st.dataframe(styled, use_container_width=True)
    else:
        st.info("Procesa tus facturas primero en la pestaña ⚙️ Procesar.")

# ── Tab PRORRATEO_IVA ─────────────────────────────────────────────────────────
with tab_pror:
    if st.session_state.df_pror is not None:
        df_pror = st.session_state.df_pror
        st.dataframe(df_pror, use_container_width=True)
        if "advertencia" in df_pror.columns:
            st.warning(df_pror["advertencia"].iloc[0])
    else:
        st.info("Procesa tus facturas primero en la pestaña ⚙️ Procesar.")

# ── Tab CHATBOT ───────────────────────────────────────────────────────────────
with tab_chat:
    st.subheader("🤖 Accounting Assistant")

    if not st.session_state.processed:
        st.info("Procesa tus facturas primero. El asistente analizará los datos de tu sesión.")
    else:
        # Historial de mensajes
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Input del usuario
        if prompt := st.chat_input("Pregunta sobre tus facturas..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Consultando..."):
                    # Pasar solo el historial previo (sin el último mensaje del usuario)
                    historial_previo = st.session_state.messages[:-1]
                    respuesta = chatbot.responder(
                        prompt=prompt,
                        df=st.session_state.df,
                        historial=historial_previo,
                        api_key=api_key_input or None,
                    )
                st.markdown(respuesta)

            st.session_state.messages.append({"role": "assistant", "content": respuesta})
```

- [ ] **Step 3: Correr app_v2.py en local**

```bash
python -m streamlit run app_v2.py
```

Verificar manualmente:
- [ ] Sidebar muestra toggle Modo upload / Modo carpeta
- [ ] Upload de 2-3 facturas de prueba funciona
- [ ] Métricas aparecen después de procesar
- [ ] Descarga de Excel funciona
- [ ] Tab Chatbot aparece con el input de chat
- [ ] Una pregunta simple al chatbot ("¿cuántos documentos hay?") responde correctamente

- [ ] **Step 4: Commit**

```bash
git add app_v2.py
git commit -m "feat: add app_v2.py with local folder mode and chatbot tab"
```

---

## Chunk 4: Deploy en Streamlit Community Cloud

### Task 5: Configurar deploy

**Files:**
- Verify: `.streamlit/config.toml` (ya creado en Task 1)

- [ ] **Step 1: Verificar que el repo tiene un remote en GitHub**

```bash
git remote -v
```
Expected: ver una URL de GitHub. Si no hay remote, crear repo en GitHub y agregarlo:
```bash
git remote add origin https://github.com/<usuario>/<repo>.git
```

- [ ] **Step 2: Push a GitHub**

```bash
git push origin main
```

- [ ] **Step 3: Deploy en Streamlit Community Cloud**

1. Ir a [share.streamlit.io](https://share.streamlit.io)
2. Click **"New app"**
3. Seleccionar:
   - Repository: `<usuario>/proyecto-facturas`
   - Branch: `main`
   - Main file path: `app_v2.py`
4. Click **"Advanced settings"**
5. En **Secrets**, agregar:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
6. Click **"Deploy!"**
7. Esperar ~2-3 minutos
8. URL resultante: `https://<usuario>-proyecto-facturas-app-v2.streamlit.app`

- [ ] **Step 4: Verificar deploy**

- Abrir la URL en navegador
- Subir 2-3 facturas de prueba
- Confirmar que el chatbot responde
- Compartir URL con el contador

---

## Verificación final

```bash
# Tests unitarios completos
python -m pytest tests/ -v --tb=short

# App local funcionando
python -m streamlit run app_v2.py

# app.py original intacto
python -m streamlit run app.py
```

Expected: todas las pruebas en verde, ambas apps corren sin errores.
