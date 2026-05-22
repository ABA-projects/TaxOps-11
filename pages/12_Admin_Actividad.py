"""pages/12_Admin_Actividad.py — Log de actividad / historial de sesiones."""

import streamlit as st
import pandas as pd

from home_gate import get_auth_session
from utils.org_id import get_org_id

st.set_page_config(page_title="TaxOps · Actividad", page_icon="📋", layout="wide")

auth = get_auth_session(st.session_state)
if auth is None:
    st.error("Debes iniciar sesión.")
    st.stop()

if auth["role"] not in ("owner", "admin"):
    st.error("No tienes permisos para acceder a esta sección.")
    st.stop()

org_id = get_org_id(st.session_state)

from db.database import list_processing_sessions, db_available

if not db_available():
    st.warning("Base de datos no disponible.")
    st.stop()

st.title("📋 Registro de actividad")

limit = st.selectbox("Mostrar últimas", [25, 50, 100, 200], index=1)
sessions = list_processing_sessions(org_id, limit=limit)

if not sessions:
    st.info("No hay actividad registrada aún.")
    st.stop()

df = pd.DataFrame(sessions)
df["started_at"]  = pd.to_datetime(df["started_at"]).dt.strftime("%Y-%m-%d %H:%M")
df["finished_at"] = pd.to_datetime(df["finished_at"]).dt.strftime("%Y-%m-%d %H:%M").fillna("—")
df["usuario"]     = df["usuario"].fillna("sistema")

# Summary metrics
col1, col2, col3 = st.columns(3)
col1.metric("Sesiones mostradas",    len(df))
col2.metric("Total facturas nuevas", int(df["nuevas"].sum()))
col3.metric("Total errores",         int(df["errores"].sum()))

st.divider()

df_show = df.rename(columns={
    "started_at": "Inicio", "finished_at": "Fin", "status": "Estado",
    "total_archivos": "Archivos", "procesados": "Procesados",
    "errores": "Errores", "nuevas": "Nuevas", "duplicadas": "Duplicadas",
    "usuario": "Usuario",
})

# Color status
def _color_status(val):
    colors = {"done": "color: green", "failed": "color: red", "running": "color: orange"}
    return colors.get(val, "")

st.dataframe(
    df_show[["Inicio", "Fin", "Estado", "Archivos", "Procesados",
             "Errores", "Nuevas", "Duplicadas", "Usuario"]],
    use_container_width=True,
    hide_index=True,
)
