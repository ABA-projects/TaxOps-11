"""pages/13_Admin_Organizacion.py — Configuración de la organización."""

import streamlit as st

from home_gate import get_auth_session
from utils.org_id import get_org_id

st.set_page_config(page_title="TaxOps · Organización", page_icon="🏛️", layout="wide")

auth = get_auth_session(st.session_state)
if auth is None:
    st.error("Debes iniciar sesión.")
    st.stop()

if auth["role"] != "owner":
    st.error("Solo el propietario puede modificar la configuración de la organización.")
    st.stop()

org_id = get_org_id(st.session_state)

from db.database import get_org, update_org, db_available

if not db_available():
    st.warning("Base de datos no disponible.")
    st.stop()

st.title("🏛️ Organización")

org = get_org(org_id)
if not org:
    st.error("No se pudo cargar la información de la organización.")
    st.stop()

# ── Info read-only ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("Plan actual", org["plan"].capitalize())
col2.metric("Creada", str(org["created_at"])[:10])
col3.metric("Estado", "Activa" if org["active"] else "Inactiva")

st.divider()

# ── Editable fields ────────────────────────────────────────────────────────────
st.subheader("Datos de la firma")

with st.form("org_form"):
    nuevo_nombre = st.text_input("Nombre de la firma", value=org["name"] or "")
    nuevo_nit    = st.text_input("NIT de la firma", value=org["nit"] or "")
    submitted    = st.form_submit_button("Guardar cambios", type="primary")

if submitted:
    if not nuevo_nombre:
        st.error("El nombre no puede estar vacío.")
    else:
        try:
            update_org(org_id, nuevo_nombre, nuevo_nit)
            st.success("✅ Información actualizada.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
