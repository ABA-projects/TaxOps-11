"""pages/14_Mi_Perfil.py — Cambio de contraseña, visible para todos los usuarios."""

import streamlit as st

from home_gate import get_auth_session, login_required
from utils.org_id import get_org_id

st.set_page_config(page_title="TaxOps · Mi perfil", page_icon="👤", layout="centered")

if not login_required():
    st.info("La gestión de perfil solo está disponible en modo SaaS (con DATABASE_URL).")
    st.stop()

auth = get_auth_session(st.session_state)
if auth is None:
    st.error("Debes iniciar sesión.")
    st.stop()

org_id = get_org_id(st.session_state)

from db.database import update_user_password, db_available
from db.auth import verify_password, authenticate

if not db_available():
    st.warning("Base de datos no disponible.")
    st.stop()

st.title("👤 Mi perfil")

st.write(f"**Correo:** {auth['email']}")
st.write(f"**Rol:** {auth['role'].capitalize()}")

st.divider()
st.subheader("Cambiar contraseña")

with st.form("cambiar_pass"):
    actual   = st.text_input("Contraseña actual", type="password")
    nueva    = st.text_input("Nueva contraseña", type="password")
    confirma = st.text_input("Confirmar nueva contraseña", type="password")
    submitted = st.form_submit_button("Actualizar contraseña", type="primary")

if submitted:
    if not actual or not nueva or not confirma:
        st.error("Todos los campos son obligatorios.")
    elif nueva != confirma:
        st.error("La nueva contraseña y su confirmación no coinciden.")
    elif len(nueva) < 6:
        st.error("La contraseña debe tener al menos 6 caracteres.")
    else:
        session = authenticate(auth["email"], actual)
        if not session:
            st.error("La contraseña actual es incorrecta.")
        else:
            try:
                update_user_password(auth["user_id"], org_id, nueva)
                st.success("✅ Contraseña actualizada correctamente.")
            except Exception as e:
                st.error(f"Error al actualizar: {e}")
