"""Página: Chatbot — Accounting Assistant multi-proveedor."""

import streamlit as st
from services.chatbot import responder, PROVIDERS, MODEL_DEFAULT, PROVIDER_DEFAULT, get_groq_models
from utils.theme import apply_theme, theme_topright
from utils.sidebar_chat import render_sidebar_chat

apply_theme()

st.title("🤖 Accounting Assistant")


# ── Cache modelos Groq (1h) ───────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _groq_models_live():
    return get_groq_models()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏭 Proveedor")
    provider_keys   = list(PROVIDERS.keys())
    provider_labels = [PROVIDERS[k]["name"] for k in provider_keys]
    _saved_prov = st.session_state.get("chatbot_provider", PROVIDER_DEFAULT)
    provider_idx = provider_keys.index(_saved_prov) if _saved_prov in provider_keys else 0
    selected_provider_label = st.radio(
        "Proveedor", provider_labels, index=provider_idx, label_visibility="collapsed"
    )
    selected_provider = provider_keys[provider_labels.index(selected_provider_label)]
    st.session_state["chatbot_provider"] = selected_provider

    st.divider()
    st.markdown("### 🧠 Modelo")

    # Modelos según proveedor (Groq: live desde API)
    if selected_provider == "groq":
        models_list = _groq_models_live()
    else:
        models_list = PROVIDERS[selected_provider]["models"]

    model_labels = [m["label"] for m in models_list]
    model_ids    = [m["id"]    for m in models_list]

    # Intentar mantener el modelo seleccionado si sigue en la lista
    prev_model = st.session_state.get("chatbot_model", MODEL_DEFAULT)
    default_idx = model_ids.index(prev_model) if prev_model in model_ids else 0

    use_custom = st.toggle("ID personalizado", value=False)
    if use_custom:
        custom_id = st.text_input(
            "ID del modelo",
            placeholder="ej: gpt-4o / claude-opus-4-5 / gemini-2.5-pro…",
        )
        selected_model = custom_id.strip() if custom_id.strip() else model_ids[0]
        if custom_id.strip():
            st.caption(f"`{selected_model}`")
        else:
            st.warning("Escribe el ID del modelo o desactiva el toggle.")
    else:
        selected_label = st.selectbox(
            "Modelo", options=model_labels, index=default_idx,
            label_visibility="collapsed",
        )
        selected_model = model_ids[model_labels.index(selected_label)]
        st.caption(f"`{selected_model}`")

    st.session_state["chatbot_model"] = selected_model

    # ── API key status ────────────────────────────────────────────────────────
    key_name = PROVIDERS[selected_provider]["key_name"]
    import os
    try:
        _key_val = st.secrets.get(key_name, "") or os.environ.get(key_name, "")
    except Exception:
        _key_val = os.environ.get(key_name, "")

    if not _key_val:
        st.divider()
        st.warning(f"⚠️ Falta `{key_name}`")
        st.caption(f"Añádela en `.streamlit/secrets.toml`:\n```\n{key_name} = \"tu-clave\"\n```")
    else:
        st.caption(f"✅ `{key_name}` configurada")

    st.divider()
    if st.button("🗑️ Limpiar conversación", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    if selected_provider == "groq" and st.button("🔄 Actualizar lista de modelos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Caption principal ────────────────────────────────────────────────────────
provider_name = PROVIDERS[selected_provider]["name"]
st.caption(f"{provider_name} · `{selected_model}`")

# ── Inicializar historial ─────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Contexto de datos ─────────────────────────────────────────────────────────
df_facturas  = st.session_state.get("df_base")
ex_resultado = st.session_state.get("exogenas_resultado")
df_exogenas  = ex_resultado.df_1003 if ex_resultado and not ex_resultado.df_1003.empty else None

# Prioriza facturas si están disponibles; si no, usa exógenas
df = df_facturas if (df_facturas is not None and not df_facturas.empty) else df_exogenas

ctx_parts = []
if df_facturas is not None and not df_facturas.empty:
    errores = int((df_facturas.get("validacion", "") == "ERROR").sum()) if "validacion" in df_facturas.columns else 0
    ctx_parts.append(f"🧾 {len(df_facturas)} facturas ({errores} errores)")
if df_exogenas is not None:
    ctx_parts.append(f"📋 {len(df_exogenas)} filas Formato 1003")

if ctx_parts:
    st.success("📂 Datos en sesión: " + " · ".join(ctx_parts) + " — puedo consultar estos datos.")
else:
    st.info(
        "💬 Pregúntame sobre contabilidad, IVA, retención, DIAN y normativa colombiana. "
        "Procesa facturas en ⚙️ Procesar o certificados en 📋 Exógenas para analizar tus datos."
    )

st.divider()

# ── Sugerencias rápidas (siempre visibles) ────────────────────────────────────
if df_facturas is not None and not df_facturas.empty:
    _sugs = [
        ["¿Cuánto IVA pagué este mes?", "¿Cuáles son mis 5 mayores proveedores?",
         "¿Qué facturas tienen errores?", "Dame un resumen general"],
        ["¿Cuánto IVA 19% acumulé en total?", "¿Qué facturas son de mandato o peaje?",
         "¿Cuál es el proveedor con más facturas?", "¿Hay facturas duplicadas?"],
    ]
elif df_exogenas is not None:
    _sugs = [
        ["¿Cuál es la retención total del 1003?", "¿Cuáles son los mayores agentes retenedores?",
         "¿Cuánto hay por concepto 1302?", "¿Qué diferencia hay entre 1303 y 1309?"],
        ["¿Qué es el Formato 1003?", "¿Cuándo se presenta exógenas 2026?",
         "Dame el resumen del Formato 1003", "¿Qué es retención de IVA art. 437-2?"],
    ]
else:
    _sugs = [
        ["¿Qué es el prorrateo de IVA Art. 490 ET?", "¿Cuándo aplica retención en la fuente?",
         "¿Cuál es la diferencia entre CUFE y CUDE?", "¿Qué documentos generan IVA descontable?"],
        ["¿Qué es el Formato 1003 DIAN?", "¿Cuándo aplica retención de IVA al 15%?",
         "¿Cuál es el UVT 2026?", "¿Qué es un autorretenedor?"],
    ]

# Rotar el set de sugerencias según cantidad de mensajes
_set = _sugs[len(st.session_state.get("messages", [])) % len(_sugs)]

with st.expander("💡 Preguntas sugeridas", expanded=not st.session_state.get("messages")):
    _cols = st.columns(2)
    for i, sug in enumerate(_set):
        with _cols[i % 2]:
            if st.button(sug, use_container_width=True, key=f"sug5_{i}_{sug[:12]}"):
                st.session_state._sugerencia = sug
                st.rerun()

# ── Historial ─────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
sugerencia_pendiente = st.session_state.pop("_sugerencia", None)
prompt = st.chat_input("Pregunta algo sobre contabilidad o tus facturas…") or sugerencia_pendiente

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando…"):
            historial_previo = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
            ]
            respuesta = responder(
                prompt=prompt,
                df=df,
                historial=historial_previo,
                model=selected_model,
                provider=selected_provider,
            )
        st.markdown(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
    st.rerun()
