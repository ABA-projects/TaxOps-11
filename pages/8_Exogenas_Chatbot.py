"""Chatbot en contexto Exógenas — misma base que 5_Chatbot.py pero con datos 1003."""

import os
import streamlit as st
from services.chatbot import responder, PROVIDERS, MODEL_DEFAULT, PROVIDER_DEFAULT, get_groq_models
from utils.theme import apply_theme, theme_topright

apply_theme()
theme_topright()

st.title("🤖 Asistente · Exógenas")

@st.cache_data(ttl=3600, show_spinner=False)
def _groq_models_live():
    return get_groq_models()

with st.sidebar:
    st.markdown("### 🏭 Proveedor")
    provider_keys   = list(PROVIDERS.keys())
    provider_labels = [PROVIDERS[k]["name"] for k in provider_keys]
    _saved_prov = st.session_state.get("chatbot_provider", PROVIDER_DEFAULT)
    provider_idx = provider_keys.index(_saved_prov) if _saved_prov in provider_keys else 0
    selected_provider_label = st.radio("Proveedor", provider_labels, index=provider_idx, label_visibility="collapsed")
    selected_provider = provider_keys[provider_labels.index(selected_provider_label)]
    st.session_state["chatbot_provider"] = selected_provider

    st.divider()
    st.markdown("### 🧠 Modelo")
    models_list = _groq_models_live() if selected_provider == "groq" else PROVIDERS[selected_provider]["models"]
    model_labels = [m["label"] for m in models_list]
    model_ids    = [m["id"]    for m in models_list]
    prev_model   = st.session_state.get("chatbot_model", MODEL_DEFAULT)
    default_idx  = model_ids.index(prev_model) if prev_model in model_ids else 0
    use_custom = st.toggle("ID personalizado", value=False)
    if use_custom:
        custom_id = st.text_input("ID del modelo", placeholder="ej: llama-3.3-70b-versatile")
        selected_model = custom_id.strip() if custom_id.strip() else model_ids[0]
    else:
        selected_label = st.selectbox("Modelo", options=model_labels, index=default_idx, label_visibility="collapsed")
        selected_model = model_ids[model_labels.index(selected_label)]
        st.caption(f"`{selected_model}`")
    st.session_state["chatbot_model"] = selected_model

    key_name = PROVIDERS[selected_provider]["key_name"]
    try:
        _key_val = st.secrets.get(key_name, "") or os.environ.get(key_name, "")
    except Exception:
        _key_val = os.environ.get(key_name, "")
    if not _key_val:
        st.warning(f"⚠️ Falta `{key_name}`")
    else:
        st.caption(f"✅ `{key_name}` configurada")

    st.divider()
    if st.button("🗑️ Limpiar conversación", use_container_width=True, key="ex_chat_clear"):
        st.session_state["ex_chat_messages"] = []
        st.rerun()

# ── Contexto de datos ─────────────────────────────────────────────────────────
resultado = st.session_state.get("exogenas_resultado")
df = resultado.df_1003 if resultado and not resultado.df_1003.empty else None

if df is not None:
    st.success(
        f"📂 {len(df)} filas del Formato 1003 en sesión · base ${df['base'].sum():,.0f} · "
        f"retención ${df['retencion'].sum():,.0f} — puedo consultar estos datos."
    )
else:
    st.info(
        "💬 Pregúntame sobre retenciones, Formato 1003, exógenas DIAN o normativa colombiana. "
        "Si procesas certificados en 📋 Procesar, también podré analizarlos."
    )

st.divider()

if "ex_chat_messages" not in st.session_state:
    st.session_state["ex_chat_messages"] = []

# ── Sugerencias rápidas (siempre visibles) ────────────────────────────────────
if df is not None:
    _sugs = [
        ["¿Cuál es la retención total del 1003?", "¿Cuáles son los mayores agentes retenedores?",
         "¿Cuánto hay por concepto 1302?", "Dame el resumen del Formato 1003"],
        ["¿Qué agente retuvo más IVA?", "¿Cuántas filas tiene el 1003?",
         "¿Hay retenciones por concepto 1309?", "¿Cuál es la base gravable total?"],
    ]
else:
    _sugs = [
        ["¿Qué es el Formato 1003 DIAN?", "¿Cuándo hay que presentar exógenas?",
         "¿Qué es la retención de IVA art. 437-2?", "¿Qué tarifa aplica para servicios?"],
        ["¿Qué es el concepto 1302?", "Diferencia entre 1303 y 1309",
         "¿Quiénes son agentes de retención?", "¿Cuál es el UVT 2026?"],
    ]

_set = _sugs[len(st.session_state["ex_chat_messages"]) % len(_sugs)]

with st.expander("💡 Preguntas sugeridas", expanded=not st.session_state["ex_chat_messages"]):
    _cols = st.columns(2)
    for i, sug in enumerate(_set):
        with _cols[i % 2]:
            if st.button(sug, use_container_width=True, key=f"exsug8_{i}_{sug[:12]}"):
                st.session_state._ex_sug = sug
                st.rerun()

# ── Historial ─────────────────────────────────────────────────────────────────
for msg in st.session_state["ex_chat_messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
sug_pendiente = st.session_state.pop("_ex_sug", None)
prompt = st.chat_input("Pregunta sobre retenciones, Formato 1003 o normativa DIAN…") or sug_pendiente

if prompt:
    st.session_state["ex_chat_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Consultando…"):
            historial_previo = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["ex_chat_messages"][:-1]
            ]
            respuesta = responder(
                prompt=prompt,
                df=df,
                historial=historial_previo,
                model=selected_model,
                provider=selected_provider,
            )
        st.markdown(respuesta)
    st.session_state["ex_chat_messages"].append({"role": "assistant", "content": respuesta})
    st.rerun()
