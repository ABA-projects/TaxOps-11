"""utils/sidebar_chat.py — Mini-chatbot persistente en el sidebar de todas las páginas."""

from __future__ import annotations

import streamlit as st


def render_sidebar_chat() -> None:
    with st.sidebar:
        st.divider()
        with st.expander("🤖 Asistente TaxOps", expanded=False):
            _render_chat_body()


def _get_context() -> tuple:
    """Devuelve (df_activo, tipo, descripcion) para el chatbot."""
    df_facturas = st.session_state.get("df_base")
    ex_resultado = st.session_state.get("exogenas_resultado")
    df_exogenas = ex_resultado.df_1003 if ex_resultado and not ex_resultado.df_1003.empty else None

    if df_facturas is not None and not df_facturas.empty:
        desc = f"✅ {len(df_facturas)} facturas"
        if df_exogenas is not None:
            desc += f" · {len(df_exogenas)} filas 1003"
        return df_facturas, "facturas", desc
    if df_exogenas is not None:
        return df_exogenas, "exogenas", f"✅ {len(df_exogenas)} filas Formato 1003"
    return None, None, "Sin datos — pregunta sobre normativa DIAN"


def _render_chat_body() -> None:
    from services.chatbot import responder, PROVIDER_DEFAULT, MODEL_DEFAULT

    if "sidebar_chat_history" not in st.session_state:
        st.session_state["sidebar_chat_history"] = []

    historial = st.session_state["sidebar_chat_history"]
    df_activo, tipo_datos, descripcion = _get_context()

    st.caption(descripcion)

    # Historial (últimos 6 mensajes)
    for msg in historial[-6:]:
        with st.chat_message(msg["role"]):
            st.markdown(f"<small>{msg['content']}</small>", unsafe_allow_html=True)

    # Usar form para evitar conflicto con st.chat_input de la página principal
    with st.form(key="sidebar_chat_form", clear_on_submit=True):
        prompt = st.text_input("Pregunta algo…", label_visibility="collapsed",
                               placeholder="Pregunta algo…")
        submitted = st.form_submit_button("Enviar", use_container_width=True)

    if submitted and prompt.strip():
        prompt = prompt.strip()
        historial.append({"role": "user", "content": prompt})

        prompt_con_contexto = prompt
        if df_activo is not None and tipo_datos == "exogenas":
            try:
                total_base = df_activo["base"].sum()
                total_ret  = df_activo["retencion"].sum()
                por_concepto = df_activo.groupby("concepto")[["base", "retencion"]].sum().to_string()
                contexto = (
                    f"\n[Datos del Formato 1003 en sesión: {len(df_activo)} filas, "
                    f"base ${total_base:,.0f}, retención ${total_ret:,.0f}. "
                    f"Por concepto:\n{por_concepto}]"
                )
                prompt_con_contexto = prompt + contexto
            except Exception:
                pass

        with st.spinner(""):
            respuesta = responder(
                prompt=prompt_con_contexto,
                df=df_activo,
                historial=historial[:-1],
                model=st.session_state.get("chatbot_model", MODEL_DEFAULT),
                provider=st.session_state.get("chatbot_provider", PROVIDER_DEFAULT),
            )

        historial.append({"role": "assistant", "content": respuesta})
        st.session_state["sidebar_chat_history"] = historial
        st.rerun()

    if historial:
        if st.button("🗑️ Limpiar", key="sidebar_chat_clear", use_container_width=True):
            st.session_state["sidebar_chat_history"] = []
            st.rerun()
