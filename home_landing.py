"""home_landing.py — Public marketing landing page for TaxOps.

Uses inline styles so CSS classes don't need to cross st.markdown() boundaries.
"""
from __future__ import annotations

import streamlit as st

# ── Layout overrides (injected once) ─────────────────────────────────────────

def _layout_css(dark: bool) -> str:
    bg = _DARK["bg"] if dark else _LIGHT["bg"]
    return f"""
<style>
[data-testid="stHeader"]       {{ display: none !important; }}
[data-testid="stSidebar"]      {{ display: none !important; }}
[data-testid="stToolbar"]      {{ display: none !important; }}
footer                          {{ display: none !important; }}
#MainMenu                       {{ display: none !important; }}
.main .block-container,
[data-testid="stMainBlockContainer"] {{
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}}
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"] {{ gap: 0 !important; }}
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.main {{ background: {bg} !important; }}
[data-testid="column"] {{ padding: 0.4rem !important; }}
</style>
"""

# ── Colour palettes ───────────────────────────────────────────────────────────

_LIGHT = {
    "bg":         "#F4F8FF",
    "white":      "#FFFFFF",
    "blue_dark":  "#1A3A5C",
    "blue_mid":   "#2563EB",
    "blue_light": "#DBEAFE",
    "blue_pale":  "#EBF4FF",
    "peach":      "#FEF3E8",
    "peach_mid":  "#FED7AA",
    "muted":      "#4A6080",
    "gray":       "#6B7A8D",
    "border":     "#DDE8F5",
    "hero_grad":  "linear-gradient(135deg,#EBF4FF 0%,#FEF3E8 100%)",
    "stat_grad":  "linear-gradient(135deg,#DBEAFE,#EBF4FF)",
    "about_grad": "linear-gradient(135deg,#EBF4FF,#FEF3E8)",
    "nav_bg":     "#FFFFFF",
    "footer_bg":  "#1A3A5C",
    "footer_txt": "#A0B4CC",
    "footer_sub": "#6B8BAA",
}

_DARK = {
    "bg":         "#0F172A",
    "white":      "#1E293B",
    "blue_dark":  "#E2EEFF",
    "blue_mid":   "#60A5FA",
    "blue_light": "#1E3A5F",
    "blue_pale":  "#172A45",
    "peach":      "#2A1F14",
    "peach_mid":  "#92400E",
    "muted":      "#94A3B8",
    "gray":       "#64748B",
    "border":     "#334155",
    "hero_grad":  "linear-gradient(135deg,#172A45 0%,#2A1F14 100%)",
    "stat_grad":  "linear-gradient(135deg,#1E3A5F,#172A45)",
    "about_grad": "linear-gradient(135deg,#172A45,#2A1F14)",
    "nav_bg":     "#1E293B",
    "footer_bg":  "#0F172A",
    "footer_txt": "#64748B",
    "footer_sub": "#475569",
}


def _palette() -> dict:
    return _DARK if st.session_state.get("landing_dark") else _LIGHT


def _sections(c: dict):
    return (
        f"background:{c['bg']};padding:3rem 3rem 1rem;width:100%;",
        f"background:{c['white']};padding:3rem 3rem 1rem;width:100%;",
    )


# Keep module-level aliases for backward compat — resolved at call time via _palette()
_C       = _LIGHT
_SECTION  = f"background:{_C['bg']};padding:3rem 3rem 1rem;width:100%;"
_SECTION_W = f"background:{_C['white']};padding:3rem 3rem 1rem;width:100%;"


# ── Nav ───────────────────────────────────────────────────────────────────────

def _nav():
    c = _palette()
    dark = st.session_state.get("landing_dark", False)
    icon = "☀️" if dark else "🌙"

    left, right = st.columns([5, 1])
    with left:
        st.markdown(f"""
        <div style="background:{c['nav_bg']};border-bottom:1.5px solid {c['border']};
                    padding:1rem 3rem;display:flex;align-items:center;gap:2rem;">
            <div style="font-size:1.6rem;font-weight:900;
                        background:linear-gradient(135deg,{c['blue_mid']},#F97316);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                🧾 TaxOps
            </div>
            <div style="font-size:.92rem;color:{c['muted']};font-weight:500;">
                Automatización contable para Colombia &nbsp;·&nbsp;
                <span style="color:{c['blue_mid']}">📍 Medellín</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with right:
        nav_bg = c["nav_bg"]
        border = c["border"]
        st.markdown(
            f"<div style='background:{nav_bg};border-bottom:1.5px solid {border};"
            f"padding:1rem .5rem;display:flex;align-items:center;justify-content:center;'>",
            unsafe_allow_html=True,
        )
        if st.button(icon, key="theme_toggle", help="Cambiar tema"):
            st.session_state["landing_dark"] = not dark
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ── Hero ──────────────────────────────────────────────────────────────────────

def _hero():
    c = _palette()
    st.markdown(f"""
    <div style="background:{c['hero_grad']};padding:5rem 3rem 4rem;text-align:center;width:100%;">
        <div style="display:inline-block;background:{c['blue_light']};color:{c['blue_mid']};
                    padding:.35rem 1.1rem;border-radius:999px;font-size:.85rem;
                    font-weight:700;margin-bottom:1.5rem;">
            🇨🇴 Hecho para firmas contables colombianas
        </div>
        <h1 style="font-size:3.2rem;font-weight:900;color:{c['blue_dark']};
                   line-height:1.15;margin:0 0 1.2rem;">
            Tu firma contable,<br>en piloto automático
        </h1>
        <p style="font-size:1.2rem;color:{c['muted']};line-height:1.7;
                  max-width:640px;margin:0 auto 2rem;">
            Procesa facturas DIAN, calcula el prorrateo de IVA según el Art. 490 E.T.
            y prepara tus exógenas — en minutos, no en días.
        </p>
        <div style="font-size:1rem;color:{c['gray']};">↓ Crea tu cuenta gratis más abajo</div>
    </div>
    """, unsafe_allow_html=True)


# ── Stats ─────────────────────────────────────────────────────────────────────

def _stats():
    c = _palette()
    S = f"background:{c['white']};padding:2rem 3rem;width:100%;"
    st.markdown(f"<div style='{S}'>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    items = [
        ("3.287+", "NITs autorretenedores DIAN"),
        ("< 5 min", "para procesar 100 facturas"),
        ("PDF + XML", "formatos DIAN soportados"),
        ("Art. 490", "prorrateo IVA automático"),
    ]
    for col, (num, lbl) in zip([c1, c2, c3, c4], items):
        col.markdown(f"""
        <div style="background:{c['stat_grad']};border-radius:1rem;
                    padding:1.5rem 1rem;text-align:center;margin:.3rem;">
            <div style="font-size:2.2rem;font-weight:900;color:{c['blue_mid']};">{num}</div>
            <div style="font-size:.88rem;color:{c['muted']};margin-top:.3rem;">{lbl}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ── Features ──────────────────────────────────────────────────────────────────

def _features():
    c = _palette()
    S = f"background:{c['bg']};padding:3rem 3rem 1rem;width:100%;"
    st.markdown(f"""
    <div style="{S}">
        <div style="text-align:center;margin-bottom:2rem;">
            <h2 style="font-size:2rem;font-weight:800;color:{c['blue_dark']};margin:0 0 .4rem;">
                Todo lo que tu firma necesita
            </h2>
            <p style="color:{c['gray']};font-size:1rem;">Una plataforma, todas las herramientas</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    feats = [
        ("⚙️", "Procesamiento masivo",
         "Carga carpetas de facturas PDF/XML. TaxOps extrae automáticamente todos los campos DIAN: CUFE, NIT, montos, fechas, tipos."),
        ("📈", "Prorrateo IVA Art. 490",
         "Calcula el IVA deducible vs no deducible con base en tus ingresos gravados y excluidos. Exporta a Excel listo para presentar."),
        ("📋", "Exógenas",
         "Genera el informe con clasificación por concepto, NIT y período. Compatible con los formatos de la DIAN."),
        ("🤖", "Asistente IA contable",
         "Chatbot especializado: top proveedores, IVA por mes, facturas con errores — en lenguaje natural."),
        ("✅", "Validación automática",
         "Detecta errores: CUFE inválido, NIT malformado, totales inconsistentes, duplicados, mandato/peaje."),
        ("☁️", "100% en la nube",
         "Accede desde cualquier navegador. Datos seguros con aislamiento completo por organización."),
    ]
    card = (f"background:{c['white']};border:1.5px solid {c['border']};"
            f"border-radius:1rem;padding:1.6rem 1.4rem;"
            f"box-shadow:0 2px 12px rgba(37,99,235,.07);height:100%;margin:.3rem;")
    for row_feats in [feats[:3], feats[3:]]:
        cols = st.columns(3)
        for col, (icon, title, desc) in zip(cols, row_feats):
            col.markdown(f"""
            <div style="{card}">
                <div style="font-size:2.2rem;margin-bottom:.7rem;">{icon}</div>
                <div style="font-size:1rem;font-weight:700;color:{c['blue_dark']};
                            margin-bottom:.5rem;">{title}</div>
                <div style="font-size:.88rem;color:{c['gray']};line-height:1.65;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


# ── About ─────────────────────────────────────────────────────────────────────

def _about():
    c = _palette()
    S = f"background:{c['white']};padding:3rem 3rem 2rem;width:100%;"
    st.markdown(f"""
    <div style="{S}">
        <div style="text-align:center;margin-bottom:2rem;">
            <h2 style="font-size:2rem;font-weight:800;color:{c['blue_dark']};margin:0 0 .4rem;">
                Quiénes somos
            </h2>
        </div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown(f"""
        <div style="background:{c['about_grad']};border-radius:1.2rem;padding:2.2rem;margin:.3rem;">
            <p style="color:{c['muted']};line-height:1.85;font-size:1rem;margin:0 0 1rem;">
                <strong style="color:{c['blue_dark']};">TaxOps</strong> es una plataforma SaaS
                colombiana construida por y para contadores. Nació de la frustración real de
                procesar cientos de facturas DIAN de forma manual cada cierre mensual.
            </p>
            <p style="color:{c['muted']};line-height:1.85;font-size:1rem;margin:0 0 1rem;">
                Combinamos experiencia contable profunda con tecnología moderna para automatizar
                el trabajo repetitivo — y devolverle tiempo a los profesionales que lo necesitan.
            </p>
            <p style="color:{c['muted']};font-size:.95rem;margin:0;">
                📍 Medellín, Colombia &nbsp;·&nbsp; ✉️ hola@taxops.co
            </p>
        </div>
        """, unsafe_allow_html=True)
    with right:
        for icon, title, desc in [
            ("🎯", "Especialización", "Conocemos la normativa DIAN por dentro."),
            ("🔒", "Seguridad", "Datos aislados por organización, nunca compartidos."),
            ("⚡", "Velocidad", "De horas a minutos en cada cierre mensual."),
            ("🤝", "Soporte", "Acompañamiento real, no solo software."),
        ]:
            st.markdown(f"""
            <div style="display:flex;align-items:flex-start;gap:.8rem;
                        background:{c['white']};border:1.5px solid {c['border']};
                        border-radius:.8rem;padding:1rem 1.2rem;margin:.35rem .3rem;">
                <span style="font-size:1.6rem;line-height:1;">{icon}</span>
                <div>
                    <div style="font-weight:700;color:{c['blue_dark']};font-size:.95rem;">{title}</div>
                    <div style="color:{c['gray']};font-size:.87rem;margin-top:.15rem;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ── Plans ─────────────────────────────────────────────────────────────────────

def _plans():
    c = _palette()
    S = f"background:{c['bg']};padding:3rem 3rem 1rem;width:100%;"
    st.markdown(f"""
    <div style="{S}">
        <div style="text-align:center;margin-bottom:2rem;">
            <h2 style="font-size:2rem;font-weight:800;color:{c['blue_dark']};margin:0 0 .4rem;">
                Planes y precios
            </h2>
            <p style="color:{c['gray']};font-size:.95rem;">Sin permanencia · Cancela cuando quieras</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    plans = [
        ("Free", "$0", "COP/mes", False, [
            ("✅", "Hasta 50 facturas/mes"), ("✅", "Procesamiento PDF + XML"),
            ("✅", "Export Excel"), ("❌", "Sin base de datos"),
            ("❌", "Sin chatbot IA"), ("❌", "Sin exógenas"),
        ]),
        ("Starter", "$300k", "COP/mes", True, [
            ("✅", "Facturas ilimitadas"), ("✅", "Base de datos PostgreSQL"),
            ("✅", "Chatbot IA contable"), ("✅", "Exógenas incluidas"),
            ("✅", "Hasta 3 usuarios"), ("❌", "Sin multi-cliente"),
        ]),
        ("Pro", "$600k", "COP/mes", False, [
            ("✅", "Todo de Starter"), ("✅", "Usuarios ilimitados"),
            ("✅", "Multi-cliente"), ("✅", "Panel de administración"),
            ("✅", "Soporte prioritario"), ("✅", "Onboarding personalizado"),
        ]),
    ]

    cols = st.columns(3)
    for col, (name, price, period, popular, features) in zip(cols, plans):
        border = c['blue_mid'] if popular else c['border']
        shadow = f"0 0 0 4px {c['blue_light']};" if popular else ""
        badge  = (f'<div style="text-align:center;margin-bottom:.5rem;">'
                  f'<span style="background:{c["blue_mid"]};color:white;padding:.25rem .9rem;'
                  f'border-radius:999px;font-size:.8rem;font-weight:700;">⭐ MÁS POPULAR</span></div>'
                  if popular else "<div style='height:1.8rem;'></div>")
        feats_html = "".join(
            f'<div style="font-size:.88rem;color:{c["muted"]};padding:.35rem 0;'
            f'border-bottom:1px solid {c["border"]};">{em} {txt}</div>'
            for em, txt in features
        )
        col.markdown(f"""
        <div style="background:{c['white']};border:2px solid {border};border-radius:1.2rem;
                    padding:1.8rem 1.5rem;text-align:center;box-shadow:{shadow}margin:.3rem;">
            {badge}
            <div style="font-size:1.15rem;font-weight:700;color:{c['blue_dark']};">{name}</div>
            <div style="font-size:2.2rem;font-weight:900;color:{c['blue_mid']};margin:.5rem 0;">
                {price} <span style="font-size:1rem;color:{c['gray']};font-weight:400;">{period}</span>
            </div>
            <div style="margin-top:1rem;text-align:left;">{feats_html}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)


# ── Auth forms ────────────────────────────────────────────────────────────────

def _auth_forms():
    c = _palette()
    S = f"background:{c['white']};padding:3rem 3rem 2rem;width:100%;"
    st.markdown(f"""
    <div style="{S}">
        <div style="text-align:center;margin-bottom:1.5rem;">
            <h2 style="font-size:2rem;font-weight:800;color:{c['blue_dark']};margin:0 0 .4rem;">
                Empieza hoy
            </h2>
            <p style="color:{c['gray']};font-size:.95rem;">Crea tu cuenta gratuita o inicia sesión</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 2, 1])
    with center:
        tab_reg, tab_login = st.tabs(["✨  Crear cuenta gratis", "🔐  Iniciar sesión"])

        with tab_reg:
            with st.form("f_register", clear_on_submit=True):
                firma = st.text_input("Nombre de la firma contable")
                email = st.text_input("Correo electrónico")
                pwd   = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
                pwd2  = st.text_input("Confirmar contraseña", type="password")
                ok    = st.form_submit_button("Crear cuenta gratis",
                                              type="primary", use_container_width=True)
            if ok:
                if not firma or not email or not pwd:
                    st.error("Todos los campos son obligatorios.")
                elif pwd != pwd2:
                    st.error("Las contraseñas no coinciden.")
                elif len(pwd) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                elif "@" not in email:
                    st.error("Ingresa un correo válido.")
                else:
                    from db.database import register_org, db_available
                    if not db_available():
                        st.error("Registro no disponible en modo sin base de datos.")
                    else:
                        try:
                            session = register_org(firma, email, pwd)
                            st.session_state["auth"] = session
                            st.rerun()
                        except Exception as e:
                            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                                st.error("Ya existe una cuenta con ese correo.")
                            else:
                                st.error(f"Error: {e}")

        with tab_login:
            with st.form("f_login"):
                lemail = st.text_input("Correo electrónico")
                lpwd   = st.text_input("Contraseña", type="password")
                lok    = st.form_submit_button("Entrar",
                                               type="primary", use_container_width=True)
            if lok:
                from db.auth import authenticate
                sess = authenticate(lemail, lpwd)
                if sess:
                    st.session_state["auth"] = sess
                    st.rerun()
                else:
                    st.error("Correo o contraseña incorrectos.")


# ── Footer ────────────────────────────────────────────────────────────────────

def _footer():
    c = _palette()
    st.markdown(f"""
    <div style="background:{c['footer_bg']};color:{c['footer_txt']};padding:2.5rem 3rem;
                margin-top:2rem;text-align:center;width:100%;">
        <div style="font-size:1.4rem;font-weight:800;color:white;margin-bottom:.5rem;">
            🧾 TaxOps
        </div>
        <p style="margin:.3rem 0;">Automatización contable para Colombia</p>
        <p style="margin:.3rem 0;">📍 Medellín, Colombia &nbsp;·&nbsp; ✉️ hola@taxops.co</p>
        <p style="margin-top:1.2rem;font-size:.8rem;color:{c['footer_sub']};">
            © 2026 TaxOps · Todos los derechos reservados
        </p>
    </div>
    """, unsafe_allow_html=True)


# ── Public entry point ────────────────────────────────────────────────────────

def show_landing() -> None:
    """Render the full public landing page."""
    dark = st.session_state.get("landing_dark", False)
    st.markdown(_layout_css(dark), unsafe_allow_html=True)
    _nav()
    _hero()
    _stats()
    _features()
    _about()
    _plans()
    _auth_forms()
    _footer()
