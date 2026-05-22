"""Página: Exógenas — Analítica del Formato 1003."""

import streamlit as st
import pandas as pd

from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat

apply_theme()
theme_topright()
render_sidebar_chat()

st.title("📊 Analítica · Exógenas 1003")
st.caption("Visualización agregada de retenciones en la fuente por concepto y agente retenedor.")

resultado = st.session_state.get("exogenas_resultado")

if not resultado or resultado.df_1003.empty:
    st.info("Procesa certificados de retención primero en **Exógenas → Procesar** para ver la analítica.")
    st.stop()

df = resultado.df_1003.copy()

# ── Métricas generales ────────────────────────────────────────────────────────
st.markdown("### Resumen general")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Agentes retenedores", df["nit"].nunique() if "nit" in df.columns else 0)
m2.metric("Filas Formato 1003", len(df))
m3.metric("Base total", f"$ {df['base'].sum():,.0f}")
m4.metric("Retención total", f"$ {df['retencion'].sum():,.0f}")

st.markdown("---")

# ── Por concepto ──────────────────────────────────────────────────────────────
st.markdown("#### Retención por concepto")
if "concepto" in df.columns:
    por_concepto = (
        df.groupby("concepto")[["base", "retencion"]]
        .sum()
        .reset_index()
        .sort_values("retencion", ascending=False)
    )
    por_concepto.columns = ["Concepto", "Base ($)", "Retención ($)"]

    col_tbl, col_chart = st.columns([1, 1])
    with col_tbl:
        st.dataframe(
            por_concepto,
            use_container_width=True,
            column_config={
                "Base ($)":      st.column_config.NumberColumn(format="$ %d"),
                "Retención ($)": st.column_config.NumberColumn(format="$ %d"),
            },
            hide_index=True,
        )
    with col_chart:
        st.bar_chart(por_concepto.set_index("Concepto")["Retención ($)"])

st.markdown("---")

# ── Top agentes retenedores ───────────────────────────────────────────────────
st.markdown("#### Top agentes retenedores")
if "razon_social" in df.columns and "retencion" in df.columns:
    top_n = st.slider("Mostrar top N", 3, min(20, len(df)), min(10, len(df)), key="top_n_agentes")

    # Limpia nombres con artefactos del extractor
    df_clean = df.copy()
    df_clean["razon_social"] = df_clean["razon_social"].str.replace(r"^\[.*?\]\s*", "", regex=True).str.strip()
    df_clean["razon_social"] = df_clean["razon_social"].str.replace(r"^\|.*?\|\s*", "", regex=True).str.strip()
    df_clean["razon_social"] = df_clean["razon_social"].where(df_clean["razon_social"] != "", df_clean["nit"])

    top = (
        df_clean.groupby(["nit", "razon_social"], dropna=False)["retencion"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    top.columns = ["NIT", "Razón Social", "Retención ($)"]

    col_t, col_c = st.columns([1, 1])
    with col_t:
        st.dataframe(
            top,
            use_container_width=True,
            column_config={
                "Retención ($)": st.column_config.NumberColumn(format="$ %d"),
            },
            hide_index=True,
        )
    with col_c:
        st.bar_chart(top.set_index("Razón Social")["Retención ($)"])

st.markdown("---")

# ── Tabla completa ────────────────────────────────────────────────────────────
st.markdown("#### Detalle completo Formato 1003")
with st.expander(f"Ver {len(df)} filas", expanded=False):
    rename = {
        "concepto": "Concepto", "nit": "NIT", "razon_social": "Razón Social",
        "base": "Base ($)", "retencion": "Retención ($)", "porcentaje": "% Ret",
    }
    df_show = df.rename(columns=rename)
    show_cols = [c for c in ["Concepto", "NIT", "Razón Social", "Base ($)", "Retención ($)", "% Ret"] if c in df_show.columns]
    st.dataframe(
        df_show[show_cols],
        use_container_width=True,
        column_config={
            "Base ($)":      st.column_config.NumberColumn(format="$ %d"),
            "Retención ($)": st.column_config.NumberColumn(format="$ %d"),
            "% Ret":         st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=True,
    )
