"""pages/9_Admin.py — User management for org owners and admins."""

import streamlit as st

from home_gate import get_auth_session
from utils.org_id import get_org_id

st.set_page_config(page_title="TaxOps · Admin", page_icon="⚙️", layout="wide")

auth = get_auth_session(st.session_state)
if auth is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()

if auth["role"] not in ("owner", "admin"):
    st.error("No tienes permisos para acceder a esta sección.")
    st.stop()

org_id = get_org_id(st.session_state)

from db.database import list_users, create_user, set_user_active, db_available

if not db_available():
    st.warning("Base de datos no disponible en modo local sin DATABASE_URL.")
    st.stop()

st.title("⚙️ Administración de usuarios")

# ── Current users ──────────────────────────────────────────────────────────────
st.subheader("Usuarios de la organización")

users = list_users(org_id)

if users:
    for u in users:
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        col1.write(f"**{u['email']}**" + (f"  ·  {u['full_name']}" if u.get("full_name") else ""))
        col2.write(u["role"])
        estado = "Activo" if u["active"] else "Inactivo"
        col3.write(f"{'🟢' if u['active'] else '🔴'} {estado}")

        # Owner can't deactivate themselves
        is_self = u["email"] == auth["email"]
        if not is_self:
            label = "Desactivar" if u["active"] else "Activar"
            if col4.button(label, key=f"toggle_{u['id']}"):
                set_user_active(u["id"], org_id, not u["active"])
                st.rerun()
        else:
            col4.write("_(tú)_")
else:
    st.info("No hay usuarios registrados.")

st.divider()

# ── Create new user ────────────────────────────────────────────────────────────
st.subheader("Agregar usuario")

with st.form("crear_usuario", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    nuevo_email    = col_a.text_input("Correo electrónico")
    nuevo_nombre   = col_b.text_input("Nombre completo (opcional)")
    col_c, col_d   = st.columns(2)
    nuevo_password = col_c.text_input("Contraseña temporal", type="password")
    nuevo_rol      = col_d.selectbox("Rol", ["contador", "admin"])
    submitted      = st.form_submit_button("Crear usuario", type="primary")

if submitted:
    if not nuevo_email or not nuevo_password:
        st.error("Correo y contraseña son obligatorios.")
    else:
        existing = [u["email"] for u in users]
        if nuevo_email.strip().lower() in existing:
            st.error("Ya existe un usuario con ese correo.")
        else:
            try:
                create_user(org_id, nuevo_email, nuevo_password, nuevo_rol, nuevo_nombre)
                st.success(f"✅ Usuario **{nuevo_email}** creado con rol **{nuevo_rol}**.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al crear usuario: {e}")
