"""Página: Exógenas — Procesamiento de certificados de retención (Formato 1003)."""

import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

import streamlit as st

from services.processor_exogenas import procesar_exogenas
from exogenas.excel_writer import write_1003
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat
from utils.org_id import get_org_id

apply_theme()
theme_topright()
render_sidebar_chat()

# ── Job store de módulo — sobrevive navegación entre páginas ──────────────────
# Clave: job_id (str UUID). Valor: dict con status, progreso y resultado.
_bg_jobs: dict[str, dict] = {}


def _run_bg_job(job_id: str, paths: list[Path], org_id: str, tmpdir: str) -> None:
    """Ejecuta el procesamiento en hilo de fondo y escribe el resultado en _bg_jobs."""
    def on_progress(i: int, total: int, name: str) -> None:
        _bg_jobs[job_id].update({"done": i, "total": total, "current": name})

    try:
        resultado = procesar_exogenas(paths, on_progress=on_progress, org_id=org_id)
        _bg_jobs[job_id].update({"status": "done", "resultado": resultado})
    except Exception as e:
        _bg_jobs[job_id].update({"status": "error", "error": str(e)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📋 Exógenas — Certificados de Retención")
st.caption("Procesa certificados de retención en la fuente (PDF) y genera el **Formato 1003 DIAN**.")

with st.sidebar:
    st.markdown("### ℹ️ Formatos soportados")
    st.markdown("""
    - Certificado Retención en la Fuente (Renta)
    - Certificado Retención por IVA
    - ~~ICA~~ (detectado pero excluido del 1003)
    """)
    st.divider()
    st.markdown("### 📐 Conceptos 1003")
    st.markdown("""
    | Código | Tipo | Tasa |
    |--------|------|------|
    | **1302** | Ventas/Compras | 2.5% |
    | **1303** | Servicios | 4% / 6% |
    | **1309** | Retención IVA | 15% |
    """)
    st.divider()
    if st.button("🗑️ Limpiar resultados", use_container_width=True):
        for k in ("exogenas_job_id", "exogenas_resultado"):
            st.session_state.pop(k, None)
        st.rerun()

# ── Estado actual del job ─────────────────────────────────────────────────────
job_id  = st.session_state.get("exogenas_job_id")
job     = _bg_jobs.get(job_id) if job_id else None
running = job is not None and job.get("status") == "running"

# ── Upload (oculto mientras hay un job activo) ────────────────────────────────
if not running:
    st.markdown("### 1️⃣ Sube los certificados PDF")
    uploaded = st.file_uploader(
        "Certificados de retención",
        type=["pdf", "docx", "xlsx", "xls", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded and st.button("⚙️ Procesar certificados", type="primary", use_container_width=True):
        tmpdir = tempfile.mkdtemp()
        paths: list[Path] = []
        for f in uploaded:
            dest = Path(tmpdir) / f.name
            dest.write_bytes(f.read())
            paths.append(dest)

        new_job_id = str(uuid.uuid4())
        _bg_jobs[new_job_id] = {
            "status": "running",
            "done": 0,
            "total": len(paths),
            "current": "iniciando…",
        }
        org_id = get_org_id(st.session_state)
        st.session_state["exogenas_job_id"] = new_job_id
        st.session_state.pop("exogenas_resultado", None)

        threading.Thread(
            target=_run_bg_job,
            args=(new_job_id, paths, org_id, tmpdir),
            daemon=True,
        ).start()
        st.rerun()
else:
    uploaded = []

# ── Barra de progreso (polling cada 2s) ───────────────────────────────────────
if running:
    done    = job.get("done", 0)
    total   = job.get("total", 1)
    current = job.get("current", "")
    pct     = done / total if total else 0

    st.markdown("### Procesando…")
    st.progress(pct, text=f"[{done}/{total}] {current}")
    st.info("Puedes navegar a otras secciones y volver — el procesamiento continúa en segundo plano.")
    time.sleep(2)
    st.rerun()

# Cuando el job termina, guardar resultado en session_state
if job and job.get("status") == "done" and "exogenas_resultado" not in st.session_state:
    st.session_state["exogenas_resultado"] = job["resultado"]

if job and job.get("status") == "error":
    st.error(f"Error en el procesamiento: {job.get('error', 'desconocido')}")

# ── Resultados ────────────────────────────────────────────────────────────────
resultado = st.session_state.get("exogenas_resultado")

if resultado:
    st.divider()
    st.markdown("### 2️⃣ Resultados")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Certificados", resultado.total_archivos)
    m2.metric("✅ Filas 1003",   len(resultado.df_1003))
    m3.metric("🚫 ICA excluidos", resultado.ica_excluidos)
    m4.metric("❌ Errores",       resultado.errores)

    if resultado.advertencias:
        with st.expander(f"⚠️ {len(resultado.advertencias)} advertencias", expanded=False):
            for adv in resultado.advertencias:
                st.markdown(adv)

    if not resultado.df_1003.empty:
        st.markdown("#### Formato 1003 (agregado por NIT + concepto)")

        df_show = resultado.df_1003.copy()
        rename = {
            "concepto": "Concepto", "tipo_doc": "Tipo Doc", "nit": "NIT", "dv": "DV",
            "razon_social": "Razón Social", "direccion": "Dirección",
            "ciudad_retencion": "Ciudad", "cod_dpto": "Dpto", "cod_mpio": "Mpio",
            "base": "Base ($)", "retencion": "Retención ($)", "porcentaje": "% Ret",
        }
        df_show = df_show.rename(columns=rename)
        drop_cols = ["primer_apellido", "segundo_apellido", "primer_nombre", "otros_nombres"]
        df_show = df_show.drop(columns=[c for c in drop_cols if c in df_show.columns])

        priority = ["Concepto", "NIT", "Razón Social", "Base ($)", "Retención ($)", "% Ret",
                    "Ciudad", "Dpto", "Mpio", "Tipo Doc", "DV", "Dirección"]
        show_cols = [c for c in priority if c in df_show.columns]

        st.dataframe(
            df_show[show_cols],
            use_container_width=True,
            column_config={
                "Base ($)":      st.column_config.NumberColumn(format="$ %d"),
                "Retención ($)": st.column_config.NumberColumn(format="$ %d"),
                "% Ret":         st.column_config.NumberColumn(format="%.2f"),
            },
            hide_index=True,
        )

        t1, t2 = st.columns(2)
        t1.metric("Base total",      f"$ {resultado.df_1003['base'].sum():,.0f}")
        t2.metric("Retención total", f"$ {resultado.df_1003['retencion'].sum():,.0f}")
    else:
        st.warning("No se generaron filas para el Formato 1003 (todos los certificados son ICA o fallaron).")

    if not resultado.df_detalle.empty:
        with st.expander("📂 Ver detalle por certificado", expanded=False):
            cols_det = ["archivo", "tipo_cert", "razon_social", "nit", "concepto",
                        "base", "retencion", "ciudad_retencion", "error"]
            df_det = resultado.df_detalle[[c for c in cols_det if c in resultado.df_detalle.columns]]
            st.dataframe(df_det, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### 3️⃣ Descargar Excel")

    if not resultado.df_1003.empty:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        write_1003(resultado.df_1003, resultado.df_detalle, tmp_path)
        excel_bytes = tmp_path.read_bytes()

        st.download_button(
            label="⬇️ Descargar Formato 1003.xlsx",
            data=excel_bytes,
            file_name="Formato_1003_Exogenas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    else:
        st.info("Procesa certificados primero para habilitar la descarga.")

elif not running and not uploaded:
    st.info(
        "📎 Sube uno o varios certificados de retención en PDF para comenzar. "
        "El sistema extrae automáticamente NIT, razón social, base y retención, "
        "y genera el Formato 1003 DIAN listo para reportar exógenas."
    )
