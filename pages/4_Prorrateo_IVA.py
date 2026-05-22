"""Página: PRORRATEO_IVA — cálculo Art. 490 ET."""

import streamlit as st
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat

apply_theme()
theme_topright()
render_sidebar_chat()

st.title("📈 Prorrateo IVA")
st.caption("Art. 490 Estatuto Tributario — IVA descontable cuando hay ingresos gravados y excluidos")

if not st.session_state.get("processed") or st.session_state.get("df_pror") is None:
    st.info("Procesa tus facturas primero en ⚙️ Procesar.")
    if st.button("Ir a Procesar"):
        st.switch_page("pages/1_Procesar.py")
    st.stop()

df_pror = st.session_state.df_pror

if "advertencia" in df_pror.columns:
    st.warning(
        "⚠️ " + df_pror["advertencia"].iloc[0] +
        " — Para un cálculo preciso, ingresa tus ingresos gravados/excluidos en ⚙️ Procesar."
    )

st.dataframe(df_pror, use_container_width=True, hide_index=True)

with st.expander("¿Cómo se calcula el prorrateo?"):
    st.markdown("""
    **Art. 490 ET — Fórmula:**

    ```
    % deducible = Ingresos gravados / (Ingresos gravados + Ingresos excluidos)
    IVA descontable = IVA total compras × % deducible
    ```

    **Reglas especiales:**
    - **Mandatos/Peajes**: IVA siempre NO descontable (el mandante no puede descontarlo)
    - **Notas Crédito**: valores negativos que reducen la base del mes
    - **Sin datos de ingresos**: se asume 100% deducible con advertencia
    """)
