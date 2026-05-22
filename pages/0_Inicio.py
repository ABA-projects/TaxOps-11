"""Página de inicio — Landing principal de TaxOps."""

import streamlit as st
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat
from utils.theme import _get_palette

# ── Inyectar CSS del tema activo ──────────────────────────────────────────────
apply_theme()
theme_topright()
render_sidebar_chat()
p = _get_palette()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <div class="logo-link" style="margin-bottom:1rem;">
    <span style="font-size:2.6rem;font-weight:900;color:{p['accent']};letter-spacing:-2px;line-height:1;">Tax</span><span style="font-size:2.6rem;font-weight:900;color:{p['text']};letter-spacing:-2px;line-height:1;">Ops</span>
    <span style="font-size:0.82rem;color:{p['text_muted']};display:block;margin-top:2px;letter-spacing:0.5px;">Automatización Contable Colombia</span>
  </div>
  <div class="badge">✅ Automatización · DIAN · Colombia</div>
  <h1>Bienvenido a TaxOps</h1>
  <p>Selecciona el módulo con el que quieres trabajar.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Módulos principales ───────────────────────────────────────────────────────
col_mod1, col_mod2 = st.columns(2, gap="large")

with col_mod1:
    st.markdown(f"""
    <div class="card card-navy" style="min-height:200px;">
      <div class="icon">🧾</div>
      <h3>Facturas DIAN</h3>
      <p>Procesa facturas electrónicas PDF/XML. Extrae CUFE, NITs, IVA y retención.
         Genera Excel con BASE_DATOS, VALIDACION y PRORRATEO_IVA. Chatbot contable incluido.</p>
    </div>""", unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("🧾 Ir a Facturas DIAN", use_container_width=True, type="primary", key="btn_facturas_procesar"):
            st.switch_page("pages/1_Procesar.py")

with col_mod2:
    st.markdown(f"""
    <div class="card card-orange" style="min-height:200px;">
      <div class="icon">📋</div>
      <h3>Exógenas · Formato 1003</h3>
      <p>Procesa certificados de retención en la fuente (PDF). Extrae NIT, razón social,
         base y retención. Genera el Formato 1003 DIAN listo para reportar exógenas.</p>
    </div>""", unsafe_allow_html=True)
    col_d, col_e = st.columns([1, 2])
    with col_d:
        if st.button("📋 Ir a Exógenas", use_container_width=True, type="primary", key="btn_exogenas"):
            st.switch_page("pages/6_Exogenas.py")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

# ── Cómo funciona ─────────────────────────────────────────────────────────────
col_steps, col_tech = st.columns([1, 1], gap="large")

with col_steps:
    st.markdown("### ¿Cómo funciona?")
    st.markdown(f"""
    <div class="step">
      <div class="step-num">1</div>
      <div class="step-text">
        <h4>Sube tus documentos</h4>
        <p>PDF y/o XML directamente desde el navegador, o apunta a una carpeta local.</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <div class="step-text">
        <h4>Procesamiento automático</h4>
        <p>El sistema extrae CUFE, NITs, fechas, valores de IVA y retención automáticamente.</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <div class="step-text">
        <h4>Validación inteligente</h4>
        <p>Detecta errores contables: duplicados, campos vacíos, cuadre subtotal+IVA≈total.</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">4</div>
      <div class="step-text">
        <h4>Descarga Excel listo para DIAN</h4>
        <p>Facturas: BASE_DATOS, VALIDACION, PRORRATEO_IVA. Exógenas: Formato 1003.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_tech:
    st.markdown("### Documentos soportados")
    st.markdown("""
    | Tipo | Formato | Módulo |
    |------|---------|--------|
    | Factura Electrónica | PDF / XML | Facturas |
    | Nota Crédito / Débito | PDF / XML | Facturas |
    | Documento Soporte | PDF | Facturas |
    | Mandato / Peaje | PDF | Facturas |
    | Certificado Retención Renta | PDF | Exógenas |
    | Certificado Retención IVA | PDF | Exógenas |
    """)

    st.markdown("### Normativa aplicada")
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        st.info("**Art. 490 ET**\nProrrateo IVA ingresos gravados/excluidos")
        st.info("**Res. 000042/2020**\nFacturación electrónica DIAN")
    with col_n2:
        st.info("**Art. 771-2 ET**\nRequisitos IVA descontable")
        st.info("**Formato 1003 DIAN**\nRetenciones en la fuente exógenas")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="footer">
  <span style="font-weight:700;color:{p['accent']};">TaxOps</span>
  &nbsp;·&nbsp; <span style="color:{p['text_muted']};">Automatización contable para Colombia
  &nbsp;·&nbsp; Resolución DIAN 000042/2020 · Art. 490 ET</span>
</div>
""", unsafe_allow_html=True)
