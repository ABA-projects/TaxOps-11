"""Página: BASE_DATOS — consulta, importación y gestión de facturas."""

from __future__ import annotations

import io
import os

import pandas as pd
import streamlit as st
from sqlalchemy import text

from db.database import db_available, get_db, insert_invoices_batch
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat

apply_theme()
theme_topright()
render_sidebar_chat()

_ORG_ID = os.environ.get("TAXOPS_ORG_ID", "00000000-0000-0000-0000-000000000000")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🗄️ Fuente de datos")
    _db_ok = db_available()
    _tiene_sesion = bool(
        st.session_state.get("processed") and st.session_state.get("df_base") is not None
    )

    opciones = []
    if _tiene_sesion:
        opciones.append("📋 Sesión actual")
    if _db_ok:
        opciones.append("🐘 PostgreSQL")
    if not opciones:
        opciones = ["📋 Sesión actual"]

    fuente = st.radio("Fuente", opciones, index=0)

    periodo_filter = ""
    if "🐘 PostgreSQL" in fuente:
        if _db_ok:
            st.caption("✅ Conectado a PostgreSQL")
        else:
            st.warning("PostgreSQL no disponible.")
        periodo_filter = st.text_input("Filtrar período (YYYY-MM)", placeholder="2026-04")
    else:
        st.caption("Datos de la sesión en memoria")

    st.divider()
    st.markdown("### ➕ Añadir datos a DB")

    if not _db_ok:
        st.error("DB no disponible")
    else:
        # ── Opción 1: Guardar sesión actual ──
        if _tiene_sesion:
            if st.button("💾 Guardar sesión en DB", use_container_width=True,
                         help="Guarda los resultados de la última sesión de procesamiento"):
                rows = st.session_state.df_base.to_dict("records")
                with st.spinner("Guardando…"):
                    try:
                        nuevas, dupes = insert_invoices_batch(rows, _ORG_ID)
                        st.session_state["_db_save_msg"] = ("ok", nuevas, dupes)
                    except Exception as e:
                        st.session_state["_db_save_msg"] = ("err", str(e))
                st.rerun()
        else:
            st.caption("Procesa facturas primero para guardar desde sesión.")

        st.divider()

        # ── Opción 2: Importar Excel ──
        st.markdown("**📥 Importar desde Excel**")
        st.caption("El archivo debe tener una hoja `BASE_DATOS`")
        excel_upload = st.file_uploader(
            "Sube el Excel exportado por TaxOps",
            type=["xlsx", "xls"],
            key="excel_import",
            label_visibility="collapsed",
        )
        if excel_upload and st.button("⬆️ Importar a DB", use_container_width=True, type="primary"):
            st.session_state["_excel_to_import"] = excel_upload.read()
            st.rerun()


# ── Mensajes de resultado de guardado ────────────────────────────────────────
if "_db_save_msg" in st.session_state:
    msg_data = st.session_state.pop("_db_save_msg")
    if msg_data[0] == "err":
        st.error(f"❌ Error al guardar en DB: `{msg_data[1]}`")
    else:
        _, nuevas, dupes = msg_data
        if nuevas > 0:
            st.success(f"✅ **{nuevas}** facturas guardadas en DB · **{dupes}** duplicadas omitidas")
        else:
            st.info(f"ℹ️ Todas las facturas ya existían en DB ({dupes} duplicadas omitidas)")
    st.cache_data.clear()

# ── Importación de Excel ──────────────────────────────────────────────────────
if "_excel_to_import" in st.session_state:
    excel_bytes = st.session_state.pop("_excel_to_import")
    try:
        xls = pd.ExcelFile(io.BytesIO(excel_bytes))
        if "BASE_DATOS" not in xls.sheet_names:
            st.error(f"❌ El Excel no tiene hoja `BASE_DATOS`. Hojas encontradas: {xls.sheet_names}")
        else:
            df_import = pd.read_excel(xls, sheet_name="BASE_DATOS", dtype=str)
            df_import = df_import.where(pd.notna(df_import), None)
            rows = df_import.to_dict("records")
            with st.spinner(f"Importando {len(rows)} filas…"):
                nuevas, dupes = insert_invoices_batch(rows, _ORG_ID)
            if nuevas > 0:
                st.success(f"✅ **{nuevas}** facturas importadas · **{dupes}** duplicadas omitidas")
            else:
                st.info(f"ℹ️ Todas las filas ya existían ({dupes} duplicadas)")
            st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ Error al leer el Excel: {e}")


# ── Carga de datos ────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load_from_db(periodo: str) -> tuple[pd.DataFrame, str | None]:
    """Lee facturas desde PostgreSQL. Retorna (df, error_msg)."""
    query = "SELECT * FROM invoices"
    params: dict = {}
    if periodo:
        query += " WHERE periodo = :periodo"
        params["periodo"] = periodo
    query += " ORDER BY fecha DESC NULLS LAST"
    try:
        with get_db() as db:
            result = db.execute(text(query), params)
            rows = result.fetchall()
            cols = list(result.keys())
        if not rows:
            return pd.DataFrame(), None
        return pd.DataFrame(rows, columns=cols), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# ── Cabecera ──────────────────────────────────────────────────────────────────
st.title("📊 Base de Datos")

if "🐘 PostgreSQL" in fuente:
    col_badge, col_refresh = st.columns([6, 1])
    with col_badge:
        st.badge("🐘 PostgreSQL", color="green")
    with col_refresh:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Cargando desde PostgreSQL…"):
        df, db_err = _load_from_db(periodo_filter)

    if db_err:
        st.error(f"❌ Error consultando PostgreSQL: `{db_err}`")
        st.stop()

    if df.empty:
        # DB vacía — mostrar estado vacío con acciones claras
        st.info(
            "La base de datos está vacía"
            + (f" para el período `{periodo_filter}`." if periodo_filter else ".")
        )
        st.markdown("#### ¿Cómo añadir facturas?")
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("**⚙️ Desde Procesar**")
                st.caption("Procesa tus PDF/XML y guarda el resultado directamente en DB.")
                if st.button("Ir a Procesar →", use_container_width=True):
                    st.switch_page("pages/1_Procesar.py")
        with c2:
            with st.container(border=True):
                st.markdown("**📥 Importar Excel**")
                st.caption("Sube un Excel exportado por TaxOps (hoja BASE_DATOS).")
                xls_quick = st.file_uploader(
                    "Selecciona el archivo",
                    type=["xlsx", "xls"],
                    key="excel_quick",
                    label_visibility="collapsed",
                )
                if xls_quick and st.button("⬆️ Importar ahora", type="primary", use_container_width=True):
                    st.session_state["_excel_to_import"] = xls_quick.read()
                    st.rerun()
        st.stop()

else:
    st.badge("📋 Sesión", color="blue")
    if not _tiene_sesion:
        st.info("Procesa tus facturas primero en ⚙️ Procesar.")
        if st.button("Ir a Procesar →"):
            st.switch_page("pages/1_Procesar.py")
        st.stop()
    df = st.session_state.df_base.copy()


# ── Filtros ───────────────────────────────────────────────────────────────────
col_search, col_tipo, col_periodo = st.columns([3, 1, 1])
with col_search:
    busqueda = st.text_input("🔍 Buscar por emisor, folio o NIT",
                              placeholder="Ej: EPM, FE-001, 900123456")
with col_tipo:
    tipos = ["Todos"] + sorted(df["tipo"].dropna().unique().tolist()) if "tipo" in df.columns else ["Todos"]
    tipo_sel = st.selectbox("Tipo", tipos)
with col_periodo:
    periodos = ["Todos"] + sorted(df["periodo"].dropna().unique().tolist(), reverse=True) \
        if "periodo" in df.columns else ["Todos"]
    periodo_sel = st.selectbox("Período", periodos)

df_filtrado = df.copy()
if busqueda:
    mask = (
        df_filtrado.get("nombre_emisor", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
        | df_filtrado.get("folio", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
        | df_filtrado.get("nit_emisor", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
    )
    df_filtrado = df_filtrado[mask]
if tipo_sel != "Todos" and "tipo" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["tipo"] == tipo_sel]
if periodo_sel != "Todos" and "periodo" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["periodo"] == periodo_sel]

# ── Métricas rápidas ──────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
_num = lambda col: pd.to_numeric(df_filtrado.get(col, pd.Series(dtype=float)), errors="coerce").sum()
m1.metric("Documentos", len(df_filtrado))
m2.metric("IVA 19%", f"${_num('iva_19'):,.0f}")
m3.metric("IVA 5%", f"${_num('iva_5'):,.0f}")
m4.metric("Total facturado", f"${_num('total'):,.0f}")

st.caption(f"{len(df_filtrado)} de {len(df)} documentos")

# Columnas visibles por defecto (ocultar UUIDs internos)
_hide = {"id", "org_id", "session_id", "procesado_at", "updated_at"}
cols_mostrar = [c for c in df_filtrado.columns if c not in _hide]
st.dataframe(df_filtrado[cols_mostrar], use_container_width=True, hide_index=True)
