"""Interfaz Streamlit — Dashboard de facturas DIAN."""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from extractor import extract_document
from validator import validate, build_validation_sheet
from prorateo import calcular_prorateo, calcular_prorateo_simple
from excel_writer import write_excel

st.set_page_config(page_title="Facturas DIAN", page_icon="🧾", layout="wide")
st.title("🧾 Gestión de Facturas Electrónicas DIAN")

# ── Sidebar: ingresos para prorrateo ───────────────────────────────────────
st.sidebar.header("Ingresos para Prorrateo")
st.sidebar.caption("Opcional: ingresa ingresos gravados y excluidos por mes (YYYY-MM)")
meses_input = st.sidebar.text_area(
    "Formato: YYYY-MM=gravados|excluidos  (un mes por línea)",
    placeholder="2026-04=5000000|1000000\n2026-03=4500000|800000",
    height=120,
)


def parse_sidebar_ingresos(raw: str) -> tuple[dict, dict]:
    grav, excl = {}, {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        mes, vals = line.split("=", 1)
        partes = vals.split("|")
        grav[mes.strip()] = float(partes[0].strip().replace(",", ""))
        if len(partes) > 1:
            excl[mes.strip()] = float(partes[1].strip().replace(",", ""))
    return grav, excl


# ── Upload ─────────────────────────────────────────────────────────────────
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

        processed: set[str] = set()
        filas = []
        prog = st.progress(0, text="Extrayendo...")
        archivos = sorted(
            p for p in tmp_path.iterdir()
            if p.suffix.lower() in (".pdf", ".xml")
        )
        for i, archivo in enumerate(archivos):
            row = extract_document(archivo, processed)
            if row:
                filas.append(row)
            prog.progress((i + 1) / len(archivos), text=f"Procesando {archivo.name}")

        if not filas:
            st.error("No se pudieron extraer datos.")
            st.stop()

        df = pd.DataFrame(filas)
        df = validate(df)
        df_val  = build_validation_sheet(df)

        grav, excl = parse_sidebar_ingresos(meses_input)
        df_pror = calcular_prorateo(df, grav, excl) if grav else calcular_prorateo_simple(df)

        # ── Métricas ───────────────────────────────────────────────────
        st.subheader("Resumen")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Documentos",  len(df))
        col2.metric("Total COP",   f"${df['total'].sum():,.0f}")
        col3.metric("IVA 19%",     f"${df['iva_19'].sum():,.0f}")
        col4.metric("Errores",     int((df.get("validacion", pd.Series(dtype=str)) == "ERROR").sum()))

        tab1, tab2, tab3 = st.tabs(["BASE_DATOS", "VALIDACION", "PRORRATEO_IVA"])
        with tab1:
            st.dataframe(df, use_container_width=True)
        with tab2:
            st.dataframe(df_val.style.apply(
                lambda col: [
                    "background-color:#FF4444;color:white" if v == "ERROR"
                    else "background-color:#70AD47" if v == "OK" else ""
                    for v in col
                ],
                subset=["validacion"] if "validacion" in df_val.columns else [],
            ), use_container_width=True)
        with tab3:
            st.dataframe(df_pror, use_container_width=True)
            if "advertencia" in df_pror.columns:
                st.warning(df_pror["advertencia"].iloc[0])

        # ── Descarga Excel ─────────────────────────────────────────────
        cols_base = [
            "tipo", "cufe", "folio", "fecha",
            "nit_emisor", "nombre_emisor", "nit_receptor", "nombre_receptor",
            "subtotal", "base_iva_19", "iva_19", "base_iva_5", "iva_5",
            "no_gravado", "total", "retencion_fuente", "fuente",
        ]
        df_base = df[[c for c in cols_base if c in df.columns]]

        out_excel = tmp_path / "facturas_dian.xlsx"
        write_excel(df_base, df_val, df_pror, out_excel)

        st.download_button(
            "⬇️ Descargar Excel",
            data=out_excel.read_bytes(),
            file_name="facturas_dian.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
