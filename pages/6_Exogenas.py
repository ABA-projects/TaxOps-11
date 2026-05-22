"""Página: Exógenas — Procesamiento de certificados de retención (Formato 1003)."""

import io
import tempfile
from pathlib import Path

import streamlit as st

from services.processor_exogenas import procesar_exogenas
from exogenas.excel_writer import write_1003
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat
from utils.org_id import get_org_id

apply_theme()
theme_topright()
render_sidebar_chat()

st.title("📋 Exógenas — Certificados de Retención")
st.caption("Procesa certificados de retención en la fuente (PDF) y genera el **Formato 1003 DIAN**.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ℹ️ Formatos soportados")
    st.markdown("""
    - Certificado Retención en la Fuente (Renta)
    - Certificado Retención por IVA
    - ~~ICA~~ (detectado pero excluido del 1003)
    """)
    st.divider()
    st.markdown("### 📐 Conceptos 1003")
    st.markdown("""
    | Código | Tipo | Tasa |
    |--------|------|------|
    | **1302** | Ventas/Compras | 2.5% |
    | **1303** | Servicios | 4% / 6% |
    | **1309** | Retención IVA | 15% |
    """)
    st.divider()
    if st.button("🗑️ Limpiar resultados", use_container_width=True):
        for k in ("exogenas_resultado", "exogenas_processed"):
            st.session_state.pop(k, None)
        st.rerun()

# ── Upload ────────────────────────────────────────────────────────────────────
st.markdown("### 1️⃣ Sube los certificados PDF")
uploaded = st.file_uploader(
    "Certificados de retención",
    type=["pdf", "docx"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

# ── Procesar ──────────────────────────────────────────────────────────────────
if uploaded and st.button("⚙️ Procesar certificados", type="primary", use_container_width=True):
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for f in uploaded:
            dest = Path(tmpdir) / f.name
            dest.write_bytes(f.read())
            paths.append(dest)

        progress_bar = st.progress(0, text="Procesando…")

        def _on_progress(i: int, total: int, name: str) -> None:
            pct = int((i + 1) / total * 100)
            progress_bar.progress(pct, text=f"[{i+1}/{total}] {name}")

        org_id = get_org_id(st.session_state)
        resultado = procesar_exogenas(paths, on_progress=_on_progress, org_id=org_id)
        progress_bar.empty()

        st.session_state["exogenas_resultado"] = resultado
        st.session_state["exogenas_processed"] = True

# ── Resultados ────────────────────────────────────────────────────────────────
resultado = st.session_state.get("exogenas_resultado")

if resultado and st.session_state.get("exogenas_processed"):
    st.divider()
    st.markdown("### 2️⃣ Resultados")

    # Métricas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Certificados", resultado.total_archivos)
    m2.metric("✅ Filas 1003",   len(resultado.df_1003))
    m3.metric("🚫 ICA excluidos", resultado.ica_excluidos)
    m4.metric("❌ Errores",       resultado.errores)

    # Advertencias
    if resultado.advertencias:
        with st.expander(f"⚠️ {len(resultado.advertencias)} advertencias", expanded=False):
            for adv in resultado.advertencias:
                st.markdown(adv)

    # Tabla principal 1003
    if not resultado.df_1003.empty:
        st.markdown("#### Formato 1003 (agregado por NIT + concepto)")

        df_show = resultado.df_1003.copy()
        rename = {
            "concepto": "Concepto", "tipo_doc": "Tipo Doc", "nit": "NIT", "dv": "DV",
            "razon_social": "Razón Social", "direccion": "Dirección",
            "ciudad_retencion": "Ciudad", "cod_dpto": "Dpto", "cod_mpio": "Mpio",
            "base": "Base ($)", "retencion": "Retención ($)", "porcentaje": "% Ret",
        }
        df_show = df_show.rename(columns=rename)
        drop_cols = ["primer_apellido","segundo_apellido","primer_nombre","otros_nombres"]
        df_show = df_show.drop(columns=[c for c in drop_cols if c in df_show.columns])

        # Columnas clave primero para que sean visibles sin scroll
        priority = ["Concepto", "NIT", "Razón Social", "Base ($)", "Retención ($)", "% Ret",
                    "Ciudad", "Dpto", "Mpio", "Tipo Doc", "DV", "Dirección"]
        show_cols = [c for c in priority if c in df_show.columns]

        st.dataframe(
            df_show[show_cols],
            use_container_width=True,
            column_config={
                "Base ($)":       st.column_config.NumberColumn(format="$ %d"),
                "Retención ($)":  st.column_config.NumberColumn(format="$ %d"),
                "% Ret":          st.column_config.NumberColumn(format="%.2f"),
            },
            hide_index=True,
        )

        # Totales rápidos
        t1, t2 = st.columns(2)
        t1.metric("Base total", f"$ {resultado.df_1003['base'].sum():,.0f}")
        t2.metric("Retención total", f"$ {resultado.df_1003['retencion'].sum():,.0f}")
    else:
        st.warning("No se generaron filas para el Formato 1003 (todos los certificados son ICA o fallaron).")

    # Detalle por certificado
    if not resultado.df_detalle.empty:
        with st.expander("📂 Ver detalle por certificado", expanded=False):
            cols_det = ["archivo","tipo_cert","razon_social","nit","concepto","base","retencion","ciudad_retencion","error"]
            df_det = resultado.df_detalle[[c for c in cols_det if c in resultado.df_detalle.columns]]
            st.dataframe(df_det, use_container_width=True, hide_index=True)

    # Descarga Excel
    st.divider()
    st.markdown("### 3️⃣ Descargar Excel")

    if not resultado.df_1003.empty:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        write_1003(resultado.df_1003, resultado.df_detalle, tmp_path)

        with open(tmp_path, "rb") as f:
            excel_bytes = f.read()

        st.download_button(
            label="⬇️ Descargar Formato 1003.xlsx",
            data=excel_bytes,
            file_name="Formato_1003_Exogenas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    else:
        st.info("Procesa certificados primero para habilitar la descarga.")

elif not uploaded:
    st.info(
        "📎 Sube uno o varios certificados de retención en PDF para comenzar. "
        "El sistema extrae automáticamente NIT, razón social, base y retención, "
        "y genera el Formato 1003 DIAN listo para reportar exógenas."
    )
