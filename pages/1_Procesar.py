"""Página: Procesar facturas — upload o carpeta local."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from pipeline.excel_writer import write_excel
from services.processor import procesar, parse_ingresos
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat
from utils.org_id import get_org_id

apply_theme()
theme_topright()
render_sidebar_chat()

# ── Estado compartido ─────────────────────────────────────────────────────────
for key, default in [
    ("df_base", None), ("df_val", None), ("df_pror", None),
    ("messages", []), ("processed", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    modo = st.radio("Modo de entrada", ["📤 Upload archivos", "📁 Carpeta local"])
    st.divider()
    st.subheader("Ingresos para Prorrateo")
    st.caption("Opcional · YYYY-MM=gravados|excluidos")
    meses_input = st.text_area(
        "Un mes por línea",
        placeholder="2026-04=5000000|1000000\n2026-03=4500000|800000",
        height=100,
    )
    st.divider()

    # ── Estado DB (solo visible si está conectada) ────────────────────────────
    from db.database import db_available
    _db_ok = db_available()
    guardar_db = _db_ok  # auto-guardar si hay DB disponible
    if _db_ok:
        st.caption("💾 PostgreSQL conectado — se guardará automáticamente")


# ── UI principal ──────────────────────────────────────────────────────────────
st.title("⚙️ Procesar Facturas")

if modo == "📤 Upload archivos":
    uploaded = st.file_uploader(
        "Sube tus PDF y/o XML de la DIAN",
        type=["pdf", "xml", "docx"],
        accept_multiple_files=True,
    )
    ready = bool(uploaded)
    archivos_fn = lambda tmp: sorted(
        p for p in tmp.rglob("*") if p.suffix.lower() in (".pdf", ".xml", ".docx")
    )
else:
    carpeta_input = st.text_input("Ruta de la carpeta", placeholder="/ruta/a/facturas")
    ready = bool(carpeta_input)
    uploaded = None

if ready and st.button("⚙️ Procesar", type="primary"):
    prog = st.progress(0, text="Iniciando…")

    def on_progress(i, total, nombre):
        prog.progress((i + 1) / max(total, 1), text=f"Procesando {nombre}…")

    org_id = get_org_id(st.session_state) if guardar_db else None

    if modo == "📤 Upload archivos":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in uploaded:
                (tmp_path / f.name).write_bytes(f.read())
            archivos = archivos_fn(tmp_path)
            grav, excl = parse_ingresos(meses_input)
            resultado = procesar(archivos, grav, excl, on_progress=on_progress, org_id=org_id)
    else:
        carpeta = Path(carpeta_input)
        if not carpeta.exists():
            st.error(f"Carpeta no encontrada: {carpeta}")
            st.stop()
        archivos = sorted(p for p in carpeta.rglob("*") if p.suffix.lower() in (".pdf", ".xml", ".docx"))
        grav, excl = parse_ingresos(meses_input)
        resultado = procesar(archivos, grav, excl, on_progress=on_progress, org_id=org_id)

    prog.empty()

    if resultado.df_base.empty:
        st.error("No se pudieron extraer datos.")
        st.stop()

    st.session_state.df_base = resultado.df_base
    st.session_state.df_val  = resultado.df_val
    st.session_state.df_pror = resultado.df_pror
    st.session_state.processed = True
    st.session_state.messages = []

    # Mensaje de resultado con stats de DB
    msg = f"✅ **{len(resultado.df_base)}** documentos procesados · **{resultado.errores}** errores"
    if resultado.db_guardado:
        msg += f" · 💾 **{resultado.db_nuevas}** nuevas en DB · **{resultado.db_duplicadas}** duplicadas omitidas"
    elif guardar_db and not resultado.db_guardado:
        msg += " · ⚠️ No se pudo guardar en DB"
    st.success(msg)

# ── Resultados ────────────────────────────────────────────────────────────────
if st.session_state.processed:
    df   = st.session_state.df_base
    dval = st.session_state.df_val
    dpro = st.session_state.df_pror

    st.divider()
    st.markdown("### 2️⃣ Resultados")

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    errores_n = int((df.get("validacion", pd.Series(dtype=str)) == "ERROR").sum()) if "validacion" in df.columns else 0
    c1.metric("📄 Documentos",    len(df))
    c2.metric("💰 Total COP",     f"${df['total'].sum():,.0f}"  if "total"  in df.columns else "N/D")
    c3.metric("🧾 IVA 19%",       f"${df['iva_19'].sum():,.0f}" if "iva_19" in df.columns else "N/D")
    c4.metric("❌ Errores",        errores_n)

    st.markdown("#### Detalle de facturas")

    # Filtros rápidos
    col_search, col_tipo, col_periodo = st.columns([3, 1, 1])
    with col_search:
        busqueda = st.text_input("🔍 Buscar emisor, folio o NIT", placeholder="Ej: EPM, FE-001, 900123456",
                                  label_visibility="collapsed")
    with col_tipo:
        tipos = ["Todos"] + sorted(df["tipo"].dropna().unique().tolist()) if "tipo" in df.columns else ["Todos"]
        tipo_sel = st.selectbox("Tipo", tipos, label_visibility="collapsed")
    with col_periodo:
        periodos = ["Todos"] + sorted(df["periodo"].dropna().unique().tolist(), reverse=True) \
            if "periodo" in df.columns else ["Todos"]
        periodo_sel = st.selectbox("Período", periodos, label_visibility="collapsed")

    df_show = df.copy()
    if busqueda:
        mask = (
            df_show.get("nombre_emisor", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
            | df_show.get("folio", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
            | df_show.get("nit_emisor", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
        )
        df_show = df_show[mask]
    if tipo_sel != "Todos" and "tipo" in df_show.columns:
        df_show = df_show[df_show["tipo"] == tipo_sel]
    if periodo_sel != "Todos" and "periodo" in df_show.columns:
        df_show = df_show[df_show["periodo"] == periodo_sel]

    st.caption(f"{len(df_show)} de {len(df)} documentos")

    # Columnas prioritarias al frente
    _priority = ["folio", "fecha", "tipo", "nombre_emisor", "nit_emisor",
                 "subtotal", "iva_19", "iva_5", "total", "validacion", "observacion"]
    _hide = {"id", "org_id", "session_id", "procesado_at", "updated_at"}
    _visible = [c for c in _priority if c in df_show.columns] + \
               [c for c in df_show.columns if c not in _priority and c not in _hide]

    st.dataframe(
        df_show[_visible],
        use_container_width=True,
        column_config={
            "subtotal":   st.column_config.NumberColumn("Subtotal",  format="$ %d"),
            "iva_19":     st.column_config.NumberColumn("IVA 19%",   format="$ %d"),
            "iva_5":      st.column_config.NumberColumn("IVA 5%",    format="$ %d"),
            "total":      st.column_config.NumberColumn("Total",     format="$ %d"),
            "validacion": st.column_config.TextColumn("Validación"),
        },
        hide_index=True,
    )

    # Descarga
    st.divider()
    st.markdown("### 3️⃣ Descargar Excel")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_xl:
        write_excel(df, dval, dpro, Path(tmp_xl.name))
        st.download_button(
            "⬇️ Descargar Excel completo (Base · Validación · Prorrateo)",
            data=Path(tmp_xl.name).read_bytes(),
            file_name="facturas_dian.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
