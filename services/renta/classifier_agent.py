"""services/renta/classifier_agent.py — Document classification via Groq (text only, minimal tokens)."""
from __future__ import annotations

import json
import os
import re

_GROQ_MODEL = "llama-3.3-70b-versatile"

_CATEGORIES = {
    "identificacion": "Cédula, pasaporte, cédula de extranjería",
    "ingresos":       "Certificado de ingresos y retenciones, desprendible de nómina",
    "bancos":         "Extracto bancario, certificado de saldo",
    "patrimonio":     "Escritura, certificado de libertad, factura de compra de activos",
    "bienes":         "Inventarios, factura de vehículo, avalúo catastral",
    "salud":          "Factura medicina prepagada, recibo de salud voluntaria",
    "pensiones":      "Certificado fondo de pensiones, extracto AFP",
    "tributario":     "RUT, formulario 210, declaración de renta anterior, certificado retefuente",
    "otros":          "Cualquier otro documento",
}

_CARPETA_MAP = {
    "identificacion": "01_Identificacion",
    "ingresos":       "02_Ingresos",
    "bancos":         "03_Bancos",
    "patrimonio":     "04_Patrimonio",
    "bienes":         "05_Bienes",
    "salud":          "06_Salud",
    "pensiones":      "07_Pensiones",
    "tributario":     "08_Tributario",
    "otros":          "09_Otros",
}

_CAMPOS_POR_CATEGORIA = {
    "ingresos":   ["empleador", "nit_empleador", "salario_mensual", "total_ingresos", "total_retencion", "año"],
    "bancos":     ["entidad", "nit_entidad", "saldo_dic31", "promedio_año", "año"],
    "pensiones":  ["fondo", "nit_fondo", "saldo", "aportes_año", "año"],
    "tributario": ["tipo_documento", "año_gravable", "total_impuesto", "saldo_pagar"],
    "patrimonio": ["tipo", "entidad", "valor", "fecha"],
    "bienes":     ["descripcion", "valor", "fecha"],
    "salud":      ["entidad", "valor_anual", "año"],
}

_PROMPT = """\
Eres experto en documentos tributarios colombianos para declaración de renta personas naturales.
Analiza el siguiente texto de un documento y responde SOLO con un JSON válido, sin explicaciones.

Categorías posibles:
{categorias}

Campos a extraer según categoría (extrae lo que encuentres, omite lo que no):
{campos}

Texto del documento (primeros 2000 caracteres):
\"\"\"
{texto}
\"\"\"

Responde SOLO con este JSON:
{{"categoria": "<categoria>", "confianza": <0.0-1.0>, "datos_extraidos": {{<campos_encontrados>}}}}
"""


def classify_document(text: str, filename: str) -> dict:
    """
    Returns:
        {categoria, carpeta_virtual, confianza, datos_extraidos}
    """
    if not text.strip():
        return _fallback_by_filename(filename)

    snippet = text[:2000]
    categorias_str = "\n".join(f"- {k}: {v}" for k, v in _CATEGORIES.items())
    campos_str = "\n".join(f"- {k}: {', '.join(v)}" for k, v in _CAMPOS_POR_CATEGORIA.items())

    prompt = _PROMPT.format(
        categorias=categorias_str,
        campos=campos_str,
        texto=snippet,
    )

    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
        return _parse_response(raw, filename)
    except Exception:
        return _fallback_by_filename(filename)


def _parse_response(raw: str, filename: str) -> dict:
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return _fallback_by_filename(filename)
        data = json.loads(m.group())
        cat = data.get("categoria", "otros").lower().strip()
        if cat not in _CATEGORIES:
            cat = "otros"
        return {
            "categoria":        cat,
            "carpeta_virtual":  _CARPETA_MAP.get(cat, "09_Otros"),
            "confianza":        float(data.get("confianza", 0.5)),
            "datos_extraidos":  data.get("datos_extraidos", {}),
        }
    except Exception:
        return _fallback_by_filename(filename)


def _fallback_by_filename(filename: str) -> dict:
    """Heuristic classification when Groq is unavailable or text is empty."""
    fname = filename.lower()
    cat = "otros"
    if any(w in fname for w in ["cedula", "cc", "pasaporte", "identificacion"]):
        cat = "identificacion"
    elif any(w in fname for w in ["ingreso", "retencion", "nomina", "salario", "cert"]):
        cat = "ingresos"
    elif any(w in fname for w in ["banco", "extracto", "saldo", "cuenta"]):
        cat = "bancos"
    elif any(w in fname for w in ["pension", "afp", "fondo"]):
        cat = "pensiones"
    elif any(w in fname for w in ["rut", "formulario", "declaracion", "210"]):
        cat = "tributario"
    elif any(w in fname for w in ["salud", "medicina", "eps", "prepagada"]):
        cat = "salud"
    return {
        "categoria":       cat,
        "carpeta_virtual": _CARPETA_MAP.get(cat, "09_Otros"),
        "confianza":       0.3,
        "datos_extraidos": {},
    }
