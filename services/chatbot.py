"""Accounting Assistant — Multi-provider: Groq, OpenAI, Anthropic, Google."""

from __future__ import annotations

import json
import os
import uuid
import boto3
import pandas as pd


# ── API key helper ────────────────────────────────────────────────────────────

def _get_key(name: str) -> str:
    """Lee API key desde Streamlit secrets o variable de entorno."""
    try:
        import streamlit as st
        return st.secrets.get(name, "") or os.environ.get(name, "")
    except Exception:
        return os.environ.get(name, "")


# ── Catálogos de modelos ──────────────────────────────────────────────────────

GROQ_MODELS_FALLBACK: list[dict] = [
    {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (recomendado)"},
    {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B (más rápido)"},
    {"id": "openai/gpt-oss-safeguard-20b", "label": "GPT-OSS Safeguard 20B"},
    {"id": "qwen/qwen3.6-27b", "label": "Qwen 3.6 27B"},
    {"id": "groq/compound", "label": "Groq Compound · Con herramientas"},
    {"id": "groq/compound-mini", "label": "Groq Compound Mini · Con herramientas"},
    {"id": "allam-2-7b", "label": "Allam 2 7B"},
]

# Modelos de Groq que existen pero no sirven para chat de texto (audio, TTS,
# clasificadores de seguridad) — se excluyen de get_groq_models() para que el
# usuario no pueda elegirlos como si fueran un modelo conversacional.
_GROQ_NON_CHAT_PREFIXES = ("whisper", "canopylabs/", "meta-llama/llama-prompt-guard")

OPENAI_MODELS: list[dict] = [
    {"id": "gpt-4o", "label": "GPT-4o · Multimodal (recomendado)"},
    {"id": "gpt-4o-mini", "label": "GPT-4o mini · Rápido y económico"},
    {"id": "gpt-4-turbo", "label": "GPT-4 Turbo"},
    {"id": "o1", "label": "o1 · Razonamiento avanzado"},
    {"id": "o1-mini", "label": "o1-mini · Razonamiento rápido"},
    {"id": "o3-mini", "label": "o3-mini · Razonamiento (más reciente)"},
]

ANTHROPIC_MODELS: list[dict] = [
    {"id": "claude-opus-4-5", "label": "Claude Opus 4.5 · Más potente"},
    {"id": "claude-sonnet-4-5", "label": "Claude Sonnet 4.5 · Balanceado"},
    {"id": "claude-haiku-3-5", "label": "Claude Haiku 3.5 · Rápido"},
    {"id": "claude-3-7-sonnet-20250219", "label": "Claude 3.7 Sonnet · Razonamiento"},
    {"id": "claude-3-5-sonnet-20241022", "label": "Claude 3.5 Sonnet"},
    {"id": "claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku"},
    {"id": "claude-3-opus-20240229", "label": "Claude 3 Opus"},
]

GOOGLE_MODELS: list[dict] = [
    {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash · Recomendado"},
    {"id": "gemini-2.0-flash-exp", "label": "Gemini 2.0 Flash Experimental"},
    {"id": "gemini-2.0-flash-thinking-exp", "label": "Gemini 2.0 Flash Thinking"},
    {"id": "gemini-1.5-pro", "label": "Gemini 1.5 Pro"},
    {"id": "gemini-1.5-flash", "label": "Gemini 1.5 Flash · Rápido"},
    {"id": "gemini-1.5-flash-8b", "label": "Gemini 1.5 Flash 8B · Más rápido"},
]

PROVIDERS: dict[str,
                dict] = {"groq": {"name": "🟢 Groq (Llama, Gemma, Mistral…)",
                                  "models": GROQ_MODELS_FALLBACK,
                                  "key_name": "GROQ_API_KEY",
                                  "free": True},
                         }

MODEL_DEFAULT = "openai/gpt-oss-120b"
PROVIDER_DEFAULT = "groq"

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres TaxOps Assistant, un asistente contable colombiano experto. \
Puedes responder cualquier pregunta sobre contabilidad, impuestos colombianos, \
facturación electrónica DIAN, Estatuto Tributario, declaraciones de renta e IVA, \
retención en la fuente, exógenas, régimen simple, NIIF, y normativa contable colombiana.

Cuando el usuario haya cargado facturas o certificados de retención en la sesión, \
puedes consultar esos datos usando las herramientas disponibles.

=== NORMATIVA VIGENTE 2025-2026 ===

UVT 2025/2026: $49.799 COP (Decreto 2609/2024). El nuevo valor para año gravable 2026 \
se publica por la DIAN en diciembre 2025 — verificar en dian.gov.co.

RETENCIÓN EN LA FUENTE — Tarifas principales:
• Concepto 1302 (Compras/bienes): 2.5% — base mínima 27 UVT ($1.344.573)
• Concepto 1303 (Servicios generales): 4% — base mínima 4 UVT ($199.196)
• Concepto 1303 (Honorarios PJ / PN declarante): 10-11% — sin base mínima
• Concepto 1303 (Servicios transporte carga): 1% — base mínima 4 UVT
• Concepto 1303 (Limpieza, vigilancia, temporales): 2% — base mínima 4 UVT
• Concepto 1309 (Retención IVA): 15% del valor del IVA (Art. 437-2 ET, mod. Ley 2277/2022)

ICA: retención municipal, NO hace parte del Formato 1003 DIAN exógenas.

ARTÍCULOS ET RELEVANTES:
• Art. 437-1: Agentes de retención IVA (grandes contribuyentes, personas jurídicas/naturales DIAN)
• Art. 437-2: Tarifa retención IVA = 15% (modificado Ley 2277/2022, vigente desde 2023)
• Art. 438: Operaciones no sujetas a retención IVA
• Art. 395: Retención sobre salarios (tabla progresiva)
• Art. 401: Retención pagos al exterior (15% o convenio doble tributación)
• Art. 490 ET: Prorrateo IVA cuando empresa tiene ingresos gravados y excluidos

FORMATO 1003 — INFORMACIÓN EXÓGENA DIAN:
• Qué es: Reporte de retenciones en la fuente practicadas/recibidas (pagos sujetos a retención)
• Obligados: Personas jurídicas y naturales con ingresos brutos > 500 UVT ($24.899.500) \
  en el año anterior, o patrimonio > 4.500 UVT. Agentes de retención siempre obligados.
• Plazo 2026: Normalmente entre abril-junio 2026 según últimos dígitos del NIT \
  (Resolución DIAN de plazos, publicada oct-nov 2025)
• Contenido: NIT retenedor, NIT retenido, concepto, base gravable, valor retenido, mes
• Resolución base: Res. 000124/2021 y modificatorias anuales

AUTORRETENEDORES DIAN:
• Empresas autorretenedoras NO son sujetos de retención por terceros en renta
• Sí pueden ser sujetos de retención en IVA
• Lista oficial: dian.gov.co → actualización periódica

CAMBIOS NORMATIVOS RECIENTES:
• Ley 2277/2022 (reforma tributaria): redujo ret. IVA 50%→15%, nuevas tarifas renta naturales
• Decreto 2609/2024: UVT 2025 = $49.799
• Resolución DIAN 000042/2020: Facturación electrónica vigente

Respondes en español colombiano, de forma clara y práctica. \
Cita artículos del ET o resoluciones DIAN cuando sea relevante. \
Si no sabes algo con certeza, indícalo — nunca inventes normas ni cifras."""

# ── Tool definitions (formato OpenAI-compatible) ──────────────────────────────

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "consultar_iva_mes",
            "description": (
                "Retorna IVA total, descontable y de mandatos para un mes "
                "YYYY-MM desde las facturas cargadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {"mes": {"type": "string", "description": "Mes en formato YYYY-MM"}},
                "required": ["mes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_proveedores",
            "description": "Lista los N proveedores con mayor gasto total en las facturas cargadas.",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "default": 10}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_factura",
            "description": "Busca facturas por folio, NIT emisor o nombre del emisor.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_errores",
            "description": "Lista facturas con errores de validación.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_general",
            "description": "KPIs generales de las facturas: total documentos, suma COP, IVA, errores.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_exogenas",
            "description": "Resumen del Formato 1003 cargado: total base, total retención, filas por concepto.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_agentes_retension",
            "description": "Lista los N agentes retenedores con mayor retención practicada en el 1003 cargado.",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "default": 10}},
            },
        },
    },
]


# ── Groq: fetch live models ───────────────────────────────────────────────────

def get_groq_models() -> list[dict]:
    """Obtiene la lista actualizada de modelos desde la API de Groq."""
    key = _get_key("GROQ_API_KEY")
    if not key:
        return GROQ_MODELS_FALLBACK
    try:
        from groq import Groq
        data = Groq(api_key=key).models.list().data
        models = sorted(
            [
                {"id": m.id, "label": m.id}
                for m in data
                if getattr(m, "active", True) and not m.id.startswith(_GROQ_NON_CHAT_PREFIXES)
            ],
            key=lambda x: x["id"],
        )
        return models if models else GROQ_MODELS_FALLBACK
    except Exception:
        return GROQ_MODELS_FALLBACK


# ── Tool implementations ──────────────────────────────────────────────────────

from datetime import date


def _es_reciente(fecha_generado: date, dias: int = 7) -> bool:
    """True si fecha_generado está dentro de los últimos `dias` días desde hoy."""
    return (date.today() - fecha_generado).days <= dias


def _disparar_agente(agente: str, overrides: dict | None = None) -> str:
    """Encola una corrida on-demand del agente correspondiente en SQS — mismo mecanismo que ya
    usan exogenas/renta (ver api/routers/exogenas.py). Lee la config de AWS de env vars directo
    (no core.config.get_settings()) porque este archivo puede correr fuera del contexto FastAPI
    (Streamlit legacy), donde 'api/' no está garantizado en sys.path."""
    job_id = str(uuid.uuid4())
    region = os.environ.get("AWS_REGION", "us-east-1")
    queue_url = os.environ.get("SQS_QUEUE_URL", "")
    sqs = boto3.client("sqs", region_name=region)
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "tipo": "agente_contable",
            "agente": agente,
            "job_id": job_id,
            "overrides": overrides or {},
        }),
    )
    return job_id


def _ultima_novedad(tipo: str) -> dict | None:
    """Última fila de `novedades` para ese tipo. None si no hay datos o la DB no está disponible
    — mismo criterio de degradación que api/routers/novedades.py."""
    from db.database import db_available, get_db

    if not db_available():
        return None

    from sqlalchemy import text

    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT tipo, titulo, resumen, fecha_generado FROM novedades "
                    "WHERE tipo = :tipo ORDER BY fecha_generado DESC LIMIT 1"
                ),
                {"tipo": tipo},
            ).mappings().fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _tool_consultar_novedades(tipo: str, nombre_amigable: str, agente: str) -> str:
    novedad = _ultima_novedad(tipo)
    if novedad and _es_reciente(novedad["fecha_generado"]):
        return f"{novedad['titulo']} ({novedad['fecha_generado']}):\n\n{novedad['resumen']}"
    _disparar_agente(agente)
    return (
        f"No tengo novedades {nombre_amigable} recientes (últimos 7 días) — ya arranqué la "
        f"búsqueda, va a tardar unos minutos. Revisá la página de Novedades en un rato."
    )


def _tool_consultar_novedades_dian() -> str:
    return _tool_consultar_novedades(tipo="dian", nombre_amigable="DIAN", agente="dian-monitor")


def _tool_consultar_novedades_niif() -> str:
    return _tool_consultar_novedades(tipo="niif", nombre_amigable="NIIF", agente="monitor-niif")


def _leer_calendario() -> list[dict]:
    """Lee el Calendario Tributario DIAN desde S3 — mismo bucket/key que
    api/routers/calendario.py. [] si no hay datos o S3 no está disponible. Usa el `boto3` ya
    importado a nivel de módulo (agregado en Task 7 para _disparar_agente)."""
    bucket = os.environ.get("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)
    try:
        obj = s3.get_object(Bucket=bucket, Key="config/calendario_2026.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return []


def _tool_consultar_vencimientos_tributarios() -> str:
    hoy = date.today()
    eventos = _leer_calendario()
    proximos = [
        e for e in eventos
        if 0 <= (date.fromisoformat(e["fecha"]) - hoy).days <= 30
    ]
    if proximos:
        proximos.sort(key=lambda e: e["fecha"])
        lineas = [f"- {e['fecha']}: {e['titulo']}" for e in proximos]
        return "Vencimientos tributarios en los próximos 30 días:\n" + "\n".join(lineas)
    _disparar_agente("vencimientos-tributarios")
    return (
        "No tengo vencimientos cargados para los próximos 30 días — ya arranqué la búsqueda, "
        "va a tardar unos minutos. Revisá el Calendario DIAN en un rato."
    )


def _leer_calendario() -> list[dict]:
    """Lee el Calendario Tributario DIAN desde S3 — mismo bucket/key que
    api/routers/calendario.py. [] si no hay datos o S3 no está disponible. Usa el `boto3` ya
    importado a nivel de módulo (agregado en Task 7 para _disparar_agente)."""
    bucket = os.environ.get("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)
    try:
        obj = s3.get_object(Bucket=bucket, Key="config/calendario_2026.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return []


def _tool_consultar_vencimientos_tributarios() -> str:
    hoy = date.today()
    eventos = _leer_calendario()
    proximos = [
        e for e in eventos
        if 0 <= (date.fromisoformat(e["fecha"]) - hoy).days <= 30
    ]
    if proximos:
        proximos.sort(key=lambda e: e["fecha"])
        lineas = [f"- {e['fecha']}: {e['titulo']}" for e in proximos]
        return "Vencimientos tributarios en los próximos 30 días:\n" + "\n".join(lineas)
    _disparar_agente("vencimientos-tributarios")
    return (
        "No tengo vencimientos cargados para los próximos 30 días — ya arranqué la búsqueda, "
        "va a tardar unos minutos. Revisá el Calendario DIAN en un rato."
    )


def _fmt_cop(v: float) -> str:
    return f"${v:,.0f} COP"


def _df_summary(df: pd.DataFrame) -> str:
    """Resumen compacto del DataFrame para incluir en system prompt."""
    total = len(df)
    total_cop = df.get("total", pd.Series(dtype=float)).sum()
    iva = df.get("iva_19", pd.Series(dtype=float)).sum()
    periodos = df.get("fecha", pd.Series(dtype=str)).str[:7].dropna().unique().tolist()
    return (
        f"{total} facturas, total {_fmt_cop(total_cop)}, IVA 19% {_fmt_cop(iva)}. "
        f"Períodos: {', '.join(sorted(periodos))}."
    )


def _is_facturas_df(df: pd.DataFrame) -> bool:
    return "fecha" in df.columns and "iva_19" in df.columns


def _tool_consultar_iva_mes(df: pd.DataFrame, mes: str) -> str:
    if not _is_facturas_df(df):
        return "Esta herramienta requiere datos de facturas (no exógenas). Procesa facturas primero en ⚙️ Procesar."
    df_mes = df[df["fecha"].str.startswith(mes, na=False)]
    if df_mes.empty:
        return f"No hay facturas para el mes {mes}."
    mandatos = df_mes[df_mes["tipo"].str.contains("mandato|peaje", case=False, na=False)]
    normales = df_mes[~df_mes["tipo"].str.contains("mandato|peaje", case=False, na=False)]
    return (
        f"IVA {mes}:\n"
        f"- Total: {_fmt_cop(df_mes['iva_19'].sum() + df_mes['iva_5'].sum())}\n"
        f"- Descontable: {_fmt_cop(normales['iva_19'].sum() + normales['iva_5'].sum())}\n"
        f"- Mandatos/peajes (no descontable): {_fmt_cop(mandatos['iva_19'].sum() + mandatos['iva_5'].sum())}\n"
        f"- Documentos: {len(df_mes)}"
    )


def _tool_top_proveedores(df: pd.DataFrame, n: int = 10) -> str:
    if not _is_facturas_df(df):
        return (
            "Esta herramienta requiere datos de facturas. Para ver los mayores "
            "agentes retenedores usa 'resumen_exogenas' o 'top_agentes_retension'."
        )
    if "nombre_emisor" not in df.columns:
        return "Sin datos de proveedores."
    top = (
        df.groupby(["nit_emisor", "nombre_emisor"])["subtotal"]
        .sum().sort_values(ascending=False).head(n).reset_index()
    )
    lines = [f"Top {n} proveedores:"]
    for i, row in top.iterrows():
        lines.append(f"{i + 1}. {row['nombre_emisor']} (NIT {row['nit_emisor']}): {_fmt_cop(row['subtotal'])}")
    return "\n".join(lines)


def _tool_buscar_factura(df: pd.DataFrame, query: str) -> str:
    if not _is_facturas_df(df):
        return "Esta herramienta requiere datos de facturas. No hay facturas cargadas en sesión."
    q = query.lower()
    mask = (
        df.get("folio", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
        | df.get("nit_emisor", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
        | df.get("nombre_emisor", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
    )
    res = df[mask]
    if res.empty:
        return f"No se encontraron facturas con '{query}'."
    cols = [c for c in ["folio", "fecha", "nombre_emisor", "nit_emisor", "total", "validacion"] if c in res.columns]
    lines = [f"{len(res)} resultado(s):"]
    for _, row in res[cols].iterrows():
        lines.append(" | ".join(str(row.get(c, "")) for c in cols))
    return "\n".join(lines)


def _tool_resumen_errores(df: pd.DataFrame) -> str:
    if not _is_facturas_df(df):
        return "Esta herramienta requiere datos de facturas. No hay facturas cargadas en sesión."
    if "validacion" not in df.columns:
        return "Sin datos de validación."
    err = df[df["validacion"] == "ERROR"]
    if err.empty:
        return "Sin errores. Todas las facturas están OK."
    lines = [f"{len(err)} factura(s) con errores:"]
    for _, row in err.iterrows():
        folio = row.get("folio", "?")
        emisor = row.get("nombre_emisor", "?")
        observacion = row.get("observacion", "sin detalle")
        lines.append(f"- {folio} | {emisor} | {observacion}")
    return "\n".join(lines)


def _tool_resumen_general(df: pd.DataFrame) -> str:
    if not _is_facturas_df(df):
        return (
            "Esta herramienta requiere datos de facturas. "
            "Usa 'resumen_exogenas' para ver el resumen del Formato 1003."
        )
    return (
        f"Resumen:\n"
        f"- Documentos: {len(df)}\n"
        f"- Total COP: {_fmt_cop(df.get('total', pd.Series(dtype=float)).sum())}\n"
        f"- IVA 19%: {_fmt_cop(df.get('iva_19', pd.Series(dtype=float)).sum())}\n"
        f"- IVA 5%: {_fmt_cop(df.get('iva_5', pd.Series(dtype=float)).sum())}\n"
        f"- Errores: {int((df.get('validacion', pd.Series(dtype=str)) == 'ERROR').sum())}"
    )


def _tool_resumen_exogenas(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "No hay datos de exógenas (Formato 1003) cargados en la sesión."
    total_base = df.get("base", pd.Series(dtype=float)).sum()
    total_ret = df.get("retencion", pd.Series(dtype=float)).sum()
    por_concepto = df.groupby("concepto")[["base", "retencion"]].sum(
    ).reset_index() if "concepto" in df.columns else pd.DataFrame()
    lines = [
        "Resumen Formato 1003:",
        f"- Filas: {len(df)}",
        f"- Base total: {_fmt_cop(total_base)}",
        f"- Retención total: {_fmt_cop(total_ret)}",
    ]
    if not por_concepto.empty:
        lines.append("- Por concepto:")
        for _, row in por_concepto.iterrows():
            lines.append(f"  • {row['concepto']}: base {_fmt_cop(row['base'])}, ret. {_fmt_cop(row['retencion'])}")
    return "\n".join(lines)


def _tool_top_agentes_retencion(df: pd.DataFrame, n: int = 10) -> str:
    if df is None or df.empty:
        return "No hay datos de exógenas cargados en la sesión."
    if "razon_social" not in df.columns or "retencion" not in df.columns:
        return "El Formato 1003 no contiene las columnas esperadas."
    top = (
        df.groupby(["nit", "razon_social"])["retencion"]
        .sum().sort_values(ascending=False).head(n).reset_index()
    )
    lines = [f"Top {n} agentes retenedores por retención:"]
    for i, row in top.iterrows():
        lines.append(f"{i + 1}. {row['razon_social']} (NIT {row['nit']}): {_fmt_cop(row['retencion'])}")
    return "\n".join(lines)


def _ejecutar_herramienta(nombre: str, args: dict, df: pd.DataFrame) -> str:
    if nombre == "consultar_iva_mes":
        return _tool_consultar_iva_mes(df, args.get("mes", ""))
    if nombre == "top_proveedores":
        return _tool_top_proveedores(df, args.get("n", 10))
    if nombre == "buscar_factura":
        return _tool_buscar_factura(df, args.get("query", ""))
    if nombre == "resumen_errores":
        return _tool_resumen_errores(df)
    if nombre == "resumen_general":
        return _tool_resumen_general(df)
    if nombre == "resumen_exogenas":
        return _tool_resumen_exogenas(df)
    if nombre == "top_agentes_retension":
        return _tool_top_agentes_retencion(df, args.get("n", 10))
    return f"Herramienta '{nombre}' no reconocida."


# ── Provider: Groq ────────────────────────────────────────────────────────────

def _responder_groq(prompt: str, df, historial: list[dict], model: str) -> str:
    key = _get_key("GROQ_API_KEY")
    if not key:
        return "⚠️ Falta `GROQ_API_KEY` en `.streamlit/secrets.toml`."
    from groq import Groq
    client = Groq(api_key=key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + historial + [
        {"role": "user", "content": prompt}
    ]
    try:
        while True:
            resp = client.chat.completions.create(
                model=model, messages=messages,
                tools=TOOLS if df is not None else [],
                tool_choice="auto" if df is not None else "none",
                max_tokens=1024,
            )
            msg = resp.choices[0].message
            if resp.choices[0].finish_reason == "tool_calls" and msg.tool_calls:
                messages.append(msg)
                for tc in msg.tool_calls:
                    resultado = _ejecutar_herramienta(tc.function.name, json.loads(tc.function.arguments), df)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": resultado})
                continue
            return msg.content or "Sin respuesta."
    except Exception as e:
        return _handle_error(e, model)


# ── Provider: OpenAI ──────────────────────────────────────────────────────────

def _responder_openai(prompt: str, df, historial: list[dict], model: str) -> str:
    key = _get_key("OPENAI_API_KEY")
    if not key:
        return "⚠️ Falta `OPENAI_API_KEY` en `.streamlit/secrets.toml`."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + historial + [
            {"role": "user", "content": prompt}
        ]
        while True:
            resp = client.chat.completions.create(
                model=model, messages=messages,
                tools=TOOLS if df is not None else None,
                tool_choice="auto" if df is not None else None,
                max_tokens=1024,
            )
            msg = resp.choices[0].message
            if resp.choices[0].finish_reason == "tool_calls" and msg.tool_calls:
                messages.append(msg)
                for tc in msg.tool_calls:
                    resultado = _ejecutar_herramienta(tc.function.name, json.loads(tc.function.arguments), df)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": resultado})
                continue
            return msg.content or "Sin respuesta."
    except Exception as e:
        return _handle_error(e, model)


# ── Provider: Anthropic ───────────────────────────────────────────────────────

def _responder_anthropic(prompt: str, df, historial: list[dict], model: str) -> str:
    key = _get_key("ANTHROPIC_API_KEY")
    if not key:
        return "⚠️ Falta `ANTHROPIC_API_KEY` en `.streamlit/secrets.toml`."
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        system = SYSTEM_PROMPT
        if df is not None and not df.empty:
            system += f"\n\nDatos de facturas cargadas: {_df_summary(df)}"
        # Anthropic: roles deben alternar user/assistant
        messages = []
        for m in historial:
            role = "user" if m["role"] == "user" else "assistant"
            messages.append({"role": role, "content": m["content"]})
        messages.append({"role": "user", "content": prompt})
        resp = client.messages.create(
            model=model, max_tokens=1024, system=system, messages=messages
        )
        return resp.content[0].text
    except Exception as e:
        return _handle_error(e, model)


# ── Provider: Google Gemini ───────────────────────────────────────────────────

def _responder_google(prompt: str, df, historial: list[dict], model: str) -> str:
    key = _get_key("GOOGLE_API_KEY")
    if not key:
        return "⚠️ Falta `GOOGLE_API_KEY` en `.streamlit/secrets.toml`."
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        system = SYSTEM_PROMPT
        if df is not None and not df.empty:
            system += f"\n\nDatos de facturas: {_df_summary(df)}"
        gen_model = genai.GenerativeModel(model, system_instruction=system)
        history = []
        for m in historial:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
        resp = gen_model.start_chat(history=history).send_message(prompt)
        return resp.text
    except Exception as e:
        return _handle_error(e, model)


# ── Error handler ─────────────────────────────────────────────────────────────

def _handle_error(e: Exception, model: str) -> str:
    err = str(e)
    if "decommissioned" in err or "model_decommissioned" in err:
        return f"⚠️ El modelo `{model}` fue dado de baja. Selecciona otro en el sidebar."
    if "rate_limit" in err.lower():
        return "⏳ Límite de velocidad alcanzado. Espera unos segundos e intenta de nuevo."
    if "authentication" in err.lower() or "api_key" in err.lower() or "invalid" in err.lower():
        return "🔑 API key inválida o sin permisos. Verifica tu clave en `secrets.toml`."
    if "not found" in err.lower() or "404" in err or "models/" in err.lower():
        return (
            f"❌ Modelo `{model}` no encontrado.\n\n"
            f"Error de la API: `{err}`\n\n"
            "Usa el toggle **ID personalizado** para escribir un ID válido, "
            "o selecciona otro modelo de la lista."
        )
    return f"❌ Error ({type(e).__name__}): {err}"


# ── Función principal ─────────────────────────────────────────────────────────

def responder(
    prompt: str,
    df: pd.DataFrame | None,
    historial: list[dict],
    model: str = MODEL_DEFAULT,
    provider: str = PROVIDER_DEFAULT,
) -> str:
    if provider == "groq":
        return _responder_groq(prompt, df, historial, model)
    if provider == "openai":
        return _responder_openai(prompt, df, historial, model)
    if provider == "anthropic":
        return _responder_anthropic(prompt, df, historial, model)
    if provider == "google":
        return _responder_google(prompt, df, historial, model)
    return f"Proveedor '{provider}' no reconocido."
