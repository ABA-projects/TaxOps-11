"""app_v2.py — Facturas DIAN v2: upload + carpeta local + Accounting Assistant."""

from __future__ import annotations

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

    st.divider()

    modo = st.radio("Modo de entrada", ["📤 Upload archivos", "📁 Carpeta local"])

    st.divider()

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
    if not archivos:
        st.warning("No se encontraron archivos PDF o XML.")
        return

    processed_keys: set[str] = set()
    filas = []
    prog = st.progress(0, text="Iniciando extracción...")

    for i, archivo in enumerate(archivos):
        clave = str(archivo.with_suffix("")).lower()
        if clave in processed_keys:
            continue
        processed_keys.add(clave)
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
    st.session_state.messages = []


# ── Tabs ──────────────────────────────────────────────────────────────────────
st.title("🧾 Gestión de Facturas DIAN")

tab_proc, tab_base, tab_val, tab_pror, tab_chat = st.tabs([
    "⚙️ Procesar", "📊 BASE_DATOS", "✅ VALIDACION", "📈 PRORRATEO_IVA", "🤖 Chatbot",
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
    else:
        carpeta_input = st.text_input(
            "Ruta de la carpeta de facturas",
            placeholder="/ruta/a/facturas",
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
    st.caption("Pregunta sobre tus facturas en lenguaje natural.")

    if not st.session_state.processed:
        st.info("Procesa tus facturas primero. El asistente analizará los datos de tu sesión.")
    else:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Pregunta sobre tus facturas..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Consultando..."):
                    historial_previo = st.session_state.messages[:-1]
                    respuesta = chatbot.responder(
                        prompt=prompt,
                        df=st.session_state.df,
                        historial=historial_previo,
                    )
                st.markdown(respuesta)

            st.session_state.messages.append({"role": "assistant", "content": respuesta})
