"""pages/11_Admin_Clientes.py — Gestión de clientes (empresas que gestiona la firma)."""

import streamlit as st

from home_gate import get_auth_session
from utils.org_id import get_org_id

st.set_page_config(page_title="TaxOps · Clientes", page_icon="🏢", layout="wide")

auth = get_auth_session(st.session_state)
if auth is None:
    st.error("Debes iniciar sesión.")
    st.stop()

if auth["role"] not in ("owner", "admin"):
    st.error("No tienes permisos para acceder a esta sección.")
    st.stop()

org_id = get_org_id(st.session_state)

from db.database import list_clients, create_client, set_client_active, db_available

if not db_available():
    st.warning("Base de datos no disponible.")
    st.stop()

st.title("🏢 Clientes")

# ── Client list ────────────────────────────────────────────────────────────────
clientes = list_clients(org_id)

if clientes:
    st.subheader(f"{len(clientes)} cliente{'s' if len(clientes) != 1 else ''} registrado{'s' if len(clientes) != 1 else ''}")
    for c in clientes:
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        col1.write(f"**{c['razon_social']}**")
        col2.write(f"NIT: `{c['nit']}`")
        col3.write(f"{'🟢 Activo' if c['active'] else '🔴 Inactivo'}")
        label = "Desactivar" if c["active"] else "Activar"
        if col4.button(label, key=f"cli_{c['id']}"):
            set_client_active(str(c["id"]), org_id, not c["active"])
            st.rerun()
else:
    st.info("No hay clientes registrados aún.")

st.divider()

# ── Add client ─────────────────────────────────────────────────────────────────
st.subheader("Agregar cliente")

with st.form("crear_cliente", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    nuevo_nit    = col_a.text_input("NIT (sin dígito de verificación)")
    nueva_razon  = col_b.text_input("Razón social")
    submitted    = st.form_submit_button("Agregar cliente", type="primary")

if submitted:
    if not nuevo_nit or not nueva_razon:
        st.error("NIT y razón social son obligatorios.")
    else:
        nits_existentes = [c["nit"] for c in clientes]
        if nuevo_nit.strip() in nits_existentes:
            st.error("Ya existe un cliente con ese NIT.")
        else:
            try:
                create_client(org_id, nuevo_nit, nueva_razon)
                st.success(f"✅ Cliente **{nueva_razon}** agregado.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al agregar cliente: {e}")
