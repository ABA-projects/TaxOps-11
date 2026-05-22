"""pages/10_Admin_Dashboard.py — Panel de control para owners y admins."""

import streamlit as st

from home_gate import get_auth_session
from utils.org_id import get_org_id

st.set_page_config(page_title="TaxOps · Dashboard", page_icon="📊", layout="wide")

auth = get_auth_session(st.session_state)
if auth is None:
    st.error("Debes iniciar sesión.")
    st.stop()

if auth["role"] not in ("owner", "admin"):
    st.error("No tienes permisos para acceder a esta sección.")
    st.stop()

org_id = get_org_id(st.session_state)

from db.database import get_dashboard_stats, list_processing_sessions, db_available

if not db_available():
    st.warning("Base de datos no disponible.")
    st.stop()

st.title("📊 Panel de control")

stats = get_dashboard_stats(org_id)

# ── KPI cards ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Facturas este mes",     stats["facturas_mes_actual"],
          delta=stats["facturas_mes_actual"] - stats["facturas_mes_anterior"])
c2.metric("Facturas mes anterior", stats["facturas_mes_anterior"])
c3.metric("Total histórico",       stats["facturas_total"])
c4.metric("Usuarios activos",      stats["usuarios_activos"])
c5.metric("Clientes activos",      stats["clientes_activos"])

st.divider()

# ── Last activity ──────────────────────────────────────────────────────────────
st.subheader("Últimas sesiones de procesamiento")

sessions = list_processing_sessions(org_id, limit=10)
if sessions:
    import pandas as pd
    df = pd.DataFrame(sessions)
    df["started_at"] = pd.to_datetime(df["started_at"]).dt.strftime("%Y-%m-%d %H:%M")
    df["finished_at"] = pd.to_datetime(df["finished_at"]).dt.strftime("%Y-%m-%d %H:%M").fillna("—")
    df = df.rename(columns={
        "started_at": "Inicio", "finished_at": "Fin", "status": "Estado",
        "total_archivos": "Archivos", "procesados": "Procesados",
        "errores": "Errores", "nuevas": "Nuevas", "duplicadas": "Duplicadas",
        "usuario": "Usuario",
    })
    st.dataframe(df[["Inicio", "Fin", "Estado", "Archivos", "Procesados",
                      "Errores", "Nuevas", "Duplicadas", "Usuario"]],
                 use_container_width=True, hide_index=True)
else:
    st.info("Aún no hay sesiones de procesamiento registradas.")
