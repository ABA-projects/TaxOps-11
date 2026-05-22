"""Página: VALIDACION — errores y advertencias contables."""

import streamlit as st
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat

apply_theme()
theme_topright()
render_sidebar_chat()

st.title("✅ Validación")

if not st.session_state.get("processed") or st.session_state.get("df_val") is None:
    st.info("Procesa tus facturas primero en ⚙️ Procesar.")
    if st.button("Ir a Procesar"):
        st.switch_page("pages/1_Procesar.py")
    st.stop()

df_val = st.session_state.df_val

errores = (df_val.get("validacion", "") == "ERROR").sum() if "validacion" in df_val.columns else 0
oks     = (df_val.get("validacion", "") == "OK").sum()    if "validacion" in df_val.columns else 0

c1, c2, c3 = st.columns(3)
c1.metric("Total documentos", len(df_val))
c2.metric("✅ OK",    int(oks),    delta=None)
c3.metric("❌ Errores", int(errores), delta=None)

filtro = st.radio("Mostrar", ["Todos", "Solo errores", "Solo OK"], horizontal=True)
df_show = df_val.copy()
if filtro == "Solo errores":
    df_show = df_show[df_show.get("validacion", "") == "ERROR"]
elif filtro == "Solo OK":
    df_show = df_show[df_show.get("validacion", "") == "OK"]

styled = df_show.style.apply(
    lambda col: [
        "background-color:#ffcdd2;color:#b71c1c" if v == "ERROR"
        else "background-color:#c8e6c9;color:#1b5e20" if v == "OK"
        else ""
        for v in col
    ],
    subset=["validacion"] if "validacion" in df_show.columns else [],
)
st.dataframe(styled, use_container_width=True, hide_index=True)
