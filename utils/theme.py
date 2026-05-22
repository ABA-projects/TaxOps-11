"""utils/theme.py — Sistema de temas: Dark · Light · System.

Uso en cada página:
    from utils.theme import apply_theme, theme_selector
    theme_selector()   # dentro de st.sidebar, muestra el toggle
    apply_theme()      # inyecta el CSS correspondiente
"""
from __future__ import annotations
import streamlit as st

# ── Paletas ───────────────────────────────────────────────────────────────────

_DARK = {
    "bg":           "#0D1117",
    "bg2":          "#161B22",
    "bg_card":      "#1C2333",
    "border":       "#30363D",
    "text":         "#E6EDF3",
    "text_muted":   "#8B949E",
    "accent":       "#E05519",
    "blue":         "#58A6FF",
    "blue_dim":     "#1F3A5F",
    "success":      "#3FB950",
    "hero_grad":    "linear-gradient(135deg, #161B22 0%, #1C2333 60%, #0D1117 100%)",
    "badge_bg":     "#2D1A0E",
    "badge_text":   "#E05519",
    "badge_border": "#5A2A10",
    "step_bg":      "#E05519",
    "footer_border":"#30363D",
    "shadow":       "rgba(0,0,0,0.4)",
}

_LIGHT = {
    "bg":           "#FFFFFF",
    "bg2":          "#F6F8FA",
    "bg_card":      "#FFFFFF",
    "border":       "#D0D7DE",
    "text":         "#1F2328",
    "text_muted":   "#656D76",
    "accent":       "#E05519",
    "blue":         "#0969DA",
    "blue_dim":     "#DDF4FF",
    "success":      "#1A7F37",
    "hero_grad":    "linear-gradient(135deg, #FDF0E8 0%, #F5F0EB 50%, #E8EEF6 100%)",
    "badge_bg":     "#FDE8D8",
    "badge_text":   "#C0400A",
    "badge_border": "#F0B890",
    "step_bg":      "#E05519",
    "footer_border":"#F0E8E0",
    "shadow":       "rgba(43,74,122,0.09)",
}

# ── CSS de Streamlit nativo ────────────────────────────────────────────────────

def _streamlit_overrides(p: dict) -> str:
    return f"""
    /* ── Streamlit structural overrides ── */
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .main .block-container {{
        background-color: {p['bg']} !important;
        color: {p['text']} !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: {p['bg2']} !important;
        border-right: 1px solid {p['border']} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {p['text']} !important;
    }}
    [data-testid="stHeader"] {{
        background-color: {p['bg']} !important;
    }}
    /* Markdown texto */
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    [data-testid="stMarkdownContainer"] p {{
        color: {p['text']} !important;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: {p['text']} !important;
    }}
    /* Tablas */
    [data-testid="stDataFrame"] {{
        border: 1px solid {p['border']} !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }}
    /* Inputs */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: {p['bg_card']} !important;
        border-color: {p['border']} !important;
        color: {p['text']} !important;
    }}
    /* Radio / Toggle */
    [data-testid="stRadio"] label,
    [data-testid="stToggle"] label {{
        color: {p['text']} !important;
    }}
    /* Info / Success / Warning boxes */
    [data-testid="stAlert"] {{
        background-color: {p['bg_card']} !important;
        border-left-color: {p['blue']} !important;
        color: {p['text']} !important;
    }}
    /* Metric */
    [data-testid="stMetric"] {{
        background-color: {p['bg_card']};
        border-radius: 10px;
        padding: 0.8rem 1rem;
        border: 1px solid {p['border']};
    }}
    [data-testid="stMetricValue"] {{ color: {p['accent']} !important; font-weight: 700; }}
    [data-testid="stMetricLabel"] {{ color: {p['text_muted']} !important; }}
    /* Caption */
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {p['text_muted']} !important;
    }}
    /* Divider */
    hr {{ border-color: {p['border']} !important; }}
    /* Progress bar */
    [data-testid="stProgress"] > div > div {{
        background-color: {p['accent']} !important;
    }}
    /* Scrollbar */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: {p['bg2']}; }}
    ::-webkit-scrollbar-thumb {{ background: {p['border']}; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {p['text_muted']}; }}
    /* ── Selectbox dropdown menu ── */
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"] ul,
    [data-baseweb="select"] [role="listbox"],
    [data-baseweb="select"] [role="option"] {{
        background-color: {p['bg_card']} !important;
        color: {p['text']} !important;
    }}
    [data-baseweb="select"] [role="option"]:hover {{
        background-color: {p['bg2']} !important;
    }}
    /* ── Number input ── */
    [data-testid="stNumberInput"] input {{
        background-color: {p['bg_card']} !important;
        color: {p['text']} !important;
        border-color: {p['border']} !important;
    }}
    /* ── Slider ── */
    [data-testid="stSlider"] label,
    [data-testid="stSlider"] [data-testid="stMarkdownContainer"] {{
        color: {p['text']} !important;
    }}
    /* ── File uploader ── */
    [data-testid="stFileUploader"] label,
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] button,
    [data-testid="stFileUploaderDropzone"] {{
        background-color: {p['bg_card']} !important;
        color: {p['text']} !important;
        border-color: {p['border']} !important;
    }}
    [data-testid="stFileUploaderFileName"] {{
        color: {p['text']} !important;
    }}
    /* ── Expander header ── */
    [data-testid="stExpander"] details summary {{
        background-color: {p['bg_card']} !important;
        color: {p['text']} !important;
    }}
    [data-testid="stExpander"] details {{
        background-color: {p['bg_card']} !important;
        border-color: {p['border']} !important;
    }}
    /* ── Popover ── */
    [data-testid="stPopover"] div[data-baseweb="popover"],
    [data-testid="stPopoverBody"] {{
        background-color: {p['bg_card']} !important;
        color: {p['text']} !important;
        border-color: {p['border']} !important;
    }}
    /* ── Spinner text ── */
    [data-testid="stSpinner"] p {{
        color: {p['text']} !important;
    }}
    /* ── Alert text children ── */
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span,
    [data-testid="stAlert"] div {{
        color: {p['text']} !important;
    }}
    /* ── Multiselect tags ── */
    [data-baseweb="tag"] {{
        background-color: {p['blue_dim']} !important;
        color: {p['text']} !important;
    }}
    """


def _component_css(p: dict) -> str:
    return f"""
    /* ── Componentes TaxOps ── */
    html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}

    .hero {{
        background: {p['hero_grad']};
        border-radius: 16px;
        padding: 2.5rem 2.5rem 2rem;
        text-align: center;
        margin-bottom: 2rem;
        border-top: 4px solid {p['accent']};
        border: 1px solid {p['border']};
    }}
    .hero h1 {{ font-size: 2.4rem; color: {p['text']}; margin-bottom: 0.4rem; font-weight: 700; }}
    .hero p  {{ font-size: 1.05rem; color: {p['text_muted']}; max-width: 640px; margin: 0 auto 1.5rem; }}

    .badge {{
        display: inline-block;
        background: {p['badge_bg']};
        color: {p['badge_text']};
        border-radius: 20px;
        padding: 4px 16px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
        border: 1px solid {p['badge_border']};
    }}

    .card {{
        background: {p['bg_card']};
        border-radius: 14px;
        padding: 1.6rem 1.4rem;
        box-shadow: 0 2px 16px {p['shadow']};
        border: 1px solid {p['border']};
        border-top: 4px solid;
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s;
        height: 100%;
    }}
    .card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 28px {p['shadow']};
        border-color: {p['accent']};
    }}
    .card h3 {{ font-size: 1.05rem; margin: 0.6rem 0 0.4rem; color: {p['text']}; font-weight: 700; }}
    .card p  {{ font-size: 0.9rem; color: {p['text_muted']}; margin: 0; line-height: 1.5; }}
    .card .icon {{ font-size: 2rem; }}

    .card-orange  {{ border-top-color: {p['accent']}  !important; }}
    .card-navy    {{ border-top-color: {p['blue']}    !important; }}
    .card-orange2 {{ border-top-color: #f0874a        !important; }}
    .card-navy2   {{ border-top-color: #4a8ac4        !important; }}
    .card-warm    {{ border-top-color: #c04010        !important; }}

    .step {{
        display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1.2rem;
    }}
    .step-num {{
        background: {p['accent']};
        color: #ffffff;
        border-radius: 50%;
        width: 36px; height: 36px;
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 1rem; flex-shrink: 0;
    }}
    .step-text h4 {{ margin: 0 0 2px; color: {p['text']}; font-size: 0.95rem; font-weight: 600; }}
    .step-text p  {{ margin: 0; color: {p['text_muted']}; font-size: 0.88rem; }}

    .footer {{
        text-align: center;
        color: {p['text_muted']};
        font-size: 0.82rem;
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid {p['footer_border']};
    }}

    #MainMenu {{ visibility: hidden; }}
    footer    {{ visibility: hidden; }}

    /* ── Fixes modo claro ── */
    /* Texto en inputs, selectbox y expanders */
    .stTextInput input, .stTextArea textarea, .stSelectbox select,
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {{
        color: {p['text']} !important;
        background-color: {p['bg_card']} !important;
    }}
    /* Texto en expanders */
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] p {{
        color: {p['text']} !important;
    }}
    /* Navegación st.navigation sidebar */
    [data-testid="stSidebarNavLink"] span,
    [data-testid="stSidebarNavLink"] p,
    nav [data-testid="stSidebarNavLink"] {{
        color: {p['text']} !important;
    }}
    /* Chat messages */
    [data-testid="stChatMessageContent"] p,
    [data-testid="stChatMessageContent"] {{
        color: {p['text']} !important;
    }}
    /* Tabs */
    [data-testid="stTabs"] button span {{
        color: {p['text']} !important;
    }}
    /* Checkbox y toggle labels */
    .stCheckbox label, .stToggle label {{
        color: {p['text']} !important;
    }}
    /* Captions y small text */
    small, .small {{ color: {p['text_muted']} !important; }}
    """


# ── API pública ───────────────────────────────────────────────────────────────

def _get_palette() -> dict:
    theme = st.session_state.get("taxops_theme", "🌙 Oscuro")
    if theme == "☀️ Claro":
        return _LIGHT
    if theme == "🌙 Oscuro":
        return _DARK
    # Sistema: detecta preferencia con media query JS trick → fallback oscuro
    return _DARK


def apply_theme() -> None:
    """Inyecta el CSS del tema activo. Llamar al inicio de cada página."""
    p = _get_palette()
    # Favicon personalizado (TaxOps logo)
    st.markdown(
        '<link rel="icon" type="image/svg+xml" href="/app/static/favicon.svg">',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<style>{_streamlit_overrides(p)}{_component_css(p)}</style>",
        unsafe_allow_html=True,
    )


def theme_selector() -> None:
    """Selector de tema (radio vertical) — usar dentro de st.popover o sidebar."""
    options = ["🌙 Oscuro", "☀️ Claro", "💻 Sistema"]
    current = st.session_state.get("taxops_theme", "🌙 Oscuro")
    selected = st.radio(
        "Tema",
        options,
        index=options.index(current) if current in options else 0,
        key="taxops_theme_radio",
        label_visibility="collapsed",
    )
    if selected != current:
        st.session_state["taxops_theme"] = selected
        st.rerun()


def theme_topright() -> None:
    """Botón '🎨 Tema' en la esquina superior derecha que abre un popover con el selector de tema."""
    _, col_btn = st.columns([7, 1])
    with col_btn:
        with st.popover("🎨 Tema", use_container_width=True):
            theme_selector()
