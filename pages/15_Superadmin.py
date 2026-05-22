"""pages/15_Superadmin.py — Platform operator console (cross-tenant)."""

import streamlit as st
import pandas as pd

from home_gate import get_auth_session
from utils.superadmin import is_superadmin

st.set_page_config(page_title="TaxOps · SuperAdmin", page_icon="🛡️", layout="wide")

auth = get_auth_session(st.session_state)
if auth is None or not is_superadmin(auth["email"]):
    st.error("Acceso restringido.")
    st.stop()

from db.database import (
    superadmin_global_stats, superadmin_list_orgs,
    superadmin_set_org_active, superadmin_set_org_plan,
    superadmin_org_detail, db_available,
)

if not db_available():
    st.warning("Base de datos no disponible.")
    st.stop()

st.title("🛡️ Super Admin — Consola de plataforma")

# ── Global KPIs ────────────────────────────────────────────────────────────────
stats = superadmin_global_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Organizaciones",      stats["orgs_total"])
c2.metric("Orgs activas",        stats["orgs_activas"])
c3.metric("Usuarios totales",    stats["usuarios_total"])
c4.metric("Facturas este mes",   stats["facturas_mes"])
c5.metric("Facturas históricas", stats["facturas_total"])

st.divider()

# ── Org list ───────────────────────────────────────────────────────────────────
st.subheader("Organizaciones")

orgs = superadmin_list_orgs()

if not orgs:
    st.info("No hay organizaciones registradas.")
    st.stop()

PLANES = ["free", "starter", "pro"]

for org in orgs:
    oid  = str(org["id"])
    name = org["name"]
    activa = org["active"]

    with st.expander(
        f"{'🟢' if activa else '🔴'}  **{name}**  ·  {org['plan'].upper()}  ·  "
        f"{org['facturas']} facturas  ·  {org['usuarios']} usuarios  ·  "
        f"{org['clientes']} clientes",
        expanded=False,
    ):
        col_info, col_actions = st.columns([3, 2])

        with col_info:
            st.write(f"**ID:** `{oid}`")
            st.write(f"**Slug:** `{org['slug']}`")
            st.write(f"**NIT:** {org['nit'] or '—'}")
            st.write(f"**Creada:** {str(org['created_at'])[:10]}")
            ultima = org["ultima_actividad"]
            st.write(f"**Última actividad:** {str(ultima)[:16] if ultima else '—'}")

        with col_actions:
            # Plan selector
            plan_idx = PLANES.index(org["plan"]) if org["plan"] in PLANES else 0
            nuevo_plan = st.selectbox("Plan", PLANES, index=plan_idx, key=f"plan_{oid}")
            if st.button("Cambiar plan", key=f"btn_plan_{oid}"):
                superadmin_set_org_plan(oid, nuevo_plan)
                st.success(f"Plan actualizado a **{nuevo_plan}**.")
                st.rerun()

            st.write("")
            lbl = "Desactivar org" if activa else "Activar org"
            tipo = "secondary" if activa else "primary"
            if st.button(lbl, key=f"btn_act_{oid}", type=tipo):
                superadmin_set_org_active(oid, not activa)
                st.rerun()

        # Drill-down: users + sessions
        if st.toggle("Ver detalle", key=f"detail_{oid}"):
            detail = superadmin_org_detail(oid)

            st.markdown("**Usuarios**")
            if detail["users"]:
                df_u = pd.DataFrame(detail["users"])[
                    ["email", "full_name", "role", "active", "last_login_at", "created_at"]
                ].rename(columns={
                    "email": "Email", "full_name": "Nombre", "role": "Rol",
                    "active": "Activo", "last_login_at": "Último login", "created_at": "Creado",
                })
                df_u["Último login"] = pd.to_datetime(df_u["Último login"]).dt.strftime("%Y-%m-%d %H:%M").fillna("—")
                df_u["Creado"] = pd.to_datetime(df_u["Creado"]).dt.strftime("%Y-%m-%d")
                st.dataframe(df_u, use_container_width=True, hide_index=True)
            else:
                st.caption("Sin usuarios.")

            st.markdown("**Últimas sesiones de procesamiento**")
            if detail["sessions"]:
                df_s = pd.DataFrame(detail["sessions"])
                df_s["started_at"]  = pd.to_datetime(df_s["started_at"]).dt.strftime("%Y-%m-%d %H:%M")
                df_s["finished_at"] = pd.to_datetime(df_s["finished_at"]).dt.strftime("%Y-%m-%d %H:%M").fillna("—")
                df_s = df_s.rename(columns={
                    "started_at": "Inicio", "finished_at": "Fin", "status": "Estado",
                    "total_archivos": "Archivos", "procesados": "Procesados",
                    "errores": "Errores", "nuevas": "Nuevas", "duplicadas": "Dup.",
                    "usuario": "Usuario",
                })
                st.dataframe(
                    df_s[["Inicio", "Fin", "Estado", "Archivos", "Procesados",
                           "Errores", "Nuevas", "Dup.", "Usuario"]],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("Sin actividad registrada.")
