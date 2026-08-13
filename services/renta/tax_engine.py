"""services/renta/tax_engine.py — Motor de declaración de renta personas naturales.

Implementa Art. 241 ET (tabla progresiva en UVT) para año gravable 2025.
Fuente de reglas: tabla reglas_tributarias en DB (seed en migración 004).
"""
from __future__ import annotations

import json
from typing import Any


# ─── Entrada al motor ─────────────────────────────────────────────────────────

def calcular_declaracion(
    contribuyente_id: str,
    año: int,
    ajuste_manual: dict | None = None,
) -> dict:
    """
    Lee documentos del contribuyente, consolida valores y aplica tabla Art. 241 ET.
    Carga datos guardados manualmente (formulario Zona A) y aplica overrides del editor.

    Returns:
        dict con todos los campos de renta_declaraciones + detalle_calculo + inconsistencias
    """
    from db.database import get_db

    with get_db() as db:
        reglas = _cargar_reglas(db, año)
        docs = _cargar_documentos(db, contribuyente_id)
        datos_guardados = _cargar_datos_guardados(db, contribuyente_id, año)

    consolidado = _consolidar_datos(docs, reglas, datos_guardados)

    # Overrides: usa el parámetro explícito, o el ajuste_manual guardado en DB
    override = ajuste_manual or datos_guardados.get("ajuste_manual")
    consolidado = _aplicar_overrides(consolidado, override)

    uvt = reglas.get("uvt", 49799)
    pasivos = float(datos_guardados.get("pasivos") or 0)
    patrimonio_liquido = _calcular_patrimonio_liquido(consolidado["patrimonio_bruto"], pasivos)

    impuesto_general = _calcular_impuesto(consolidado["renta_gravable"], reglas)
    impuesto_dividendos = _calcular_impuesto_dividendos(consolidado.get("dividendos", 0), uvt)
    impuesto_ocasional = _calcular_impuesto_ocasional(
        consolidado.get("ganancias_ocasionales", 0),
        datos_guardados.get("tipo_ganancia"),
    )

    impuesto_cargo = round(impuesto_general + impuesto_dividendos + impuesto_ocasional, 2)
    retenciones = consolidado["retenciones"]
    saldo_pagar = max(0.0, impuesto_cargo - retenciones)
    saldo_favor = max(0.0, retenciones - impuesto_cargo)

    inconsistencias = _detectar_inconsistencias(consolidado, docs)

    detalle = {
        "uvt": uvt,
        "consolidado": consolidado,
        "impuesto_cedula_general": impuesto_general,
        "impuesto_dividendos": impuesto_dividendos,
        "impuesto_ocasional": impuesto_ocasional,
        "tramo_aplicado": _tramo_aplicado(consolidado["renta_gravable"], reglas),
        "ajustados_manualmente": consolidado.get("_ajustados_manualmente", []),
    }

    return {
        "año_gravable": año,
        "patrimonio_bruto": consolidado["patrimonio_bruto"],
        "patrimonio_liquido": patrimonio_liquido,
        "ingresos_laborales": consolidado["ingresos_laborales"],
        "rentas_capital": consolidado["rentas_capital"],
        "rentas_no_laborales": consolidado["rentas_no_laborales"],
        "dividendos": consolidado.get("dividendos", 0),
        "ganancias_ocasionales": consolidado.get("ganancias_ocasionales", 0),
        "rentas_exentas": consolidado["rentas_exentas"],
        "deducciones": consolidado["deducciones"],
        "retenciones": retenciones,
        "impuesto_cargo": impuesto_cargo,
        "saldo_pagar": saldo_pagar,
        "saldo_favor": saldo_favor,
        "estado": "borrador",
        "inconsistencias": inconsistencias,
        "detalle_calculo": detalle,
        # Campos S4
        "aportes_pension": float(datos_guardados.get("aportes_pension") or 0),
        "afc_fvp": float(datos_guardados.get("afc_fvp") or 0),
        "intereses_vivienda": float(datos_guardados.get("intereses_vivienda") or 0),
        "medicina_prepagada": float(datos_guardados.get("medicina_prepagada") or 0),
        "dependientes": int(datos_guardados.get("dependientes") or 0),
        "tipo_ganancia": datos_guardados.get("tipo_ganancia"),
        "pasivos": pasivos,
        "ajuste_manual": override,
    }


# ─── Carga de reglas ──────────────────────────────────────────────────────────

def _cargar_reglas(db, año: int) -> dict:
    from sqlalchemy import text
    rows = db.execute(
        text("SELECT tipo_regla, concepto, parametros FROM reglas_tributarias WHERE año_gravable = :año"),
        {"año": año},
    ).fetchall()

    reglas: dict[str, Any] = {}
    for r in rows:
        tipo, concepto, params = r
        p = params if isinstance(params, dict) else json.loads(params)
        if tipo == "uvt":
            reglas["uvt"] = p.get("uvt", 49799)
        elif tipo == "tarifa_renta" and concepto == "tabla_art241":
            reglas["tabla_art241"] = p.get("tramos", [])
        elif tipo == "renta_exenta":
            reglas.setdefault("rentas_exentas", {})[concepto] = p
        elif tipo == "deduccion":
            reglas.setdefault("deducciones_reglas", {})[concepto] = p

    if "uvt" not in reglas:
        reglas["uvt"] = 49799
    if "tabla_art241" not in reglas:
        reglas["tabla_art241"] = _tabla_art241_default()
    return reglas


def _tabla_art241_default() -> list[dict]:
    return [
        {"desde_uvt": 0, "hasta_uvt": 1090, "tarifa_marginal": 0.00, "impuesto_base_uvt": 0},
        {"desde_uvt": 1090, "hasta_uvt": 1700, "tarifa_marginal": 0.19, "impuesto_base_uvt": 0},
        {"desde_uvt": 1700, "hasta_uvt": 4100, "tarifa_marginal": 0.28, "impuesto_base_uvt": 116},
        {"desde_uvt": 4100, "hasta_uvt": 8670, "tarifa_marginal": 0.33, "impuesto_base_uvt": 788},
        {"desde_uvt": 8670, "hasta_uvt": 18970, "tarifa_marginal": 0.35, "impuesto_base_uvt": 2296},
        {"desde_uvt": 18970, "hasta_uvt": 31000, "tarifa_marginal": 0.37, "impuesto_base_uvt": 5901},
        {"desde_uvt": 31000, "hasta_uvt": None, "tarifa_marginal": 0.39, "impuesto_base_uvt": 10352},
    ]


# ─── Carga de documentos ──────────────────────────────────────────────────────

def _cargar_documentos(db, contribuyente_id: str) -> list[dict]:
    from sqlalchemy import text
    rows = db.execute(
        text("""
            SELECT id, categoria, datos_extraidos, estado_ocr, confianza_clasificacion
            FROM renta_documentos
            WHERE contribuyente_id = :cid AND estado_ocr = 'completado'
        """),
        {"cid": contribuyente_id},
    ).fetchall()
    result = []
    for r in rows:
        datos = r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {})
        result.append({
            "id": str(r[0]),
            "categoria": r[1],
            "datos": datos,
            "confianza": float(r[4] or 0),
        })
    return result


def _cargar_datos_guardados(db, contribuyente_id: str, año: int) -> dict:
    """Lee la declaración guardada para tomar los campos manuales."""
    from sqlalchemy import text
    row = db.execute(
        text("SELECT * FROM renta_declaraciones WHERE contribuyente_id = :cid AND año_gravable = :año"),
        {"cid": contribuyente_id, "año": año},
    ).one_or_none()
    if not row:
        return {}
    d = dict(row._mapping)
    if d.get("ajuste_manual") and isinstance(d["ajuste_manual"], str):
        d["ajuste_manual"] = json.loads(d["ajuste_manual"])
    return d


# ─── Consolidación ────────────────────────────────────────────────────────────

def _consolidar_datos(
    docs: list[dict],
    reglas: dict,
    datos_guardados: dict | None = None,
) -> dict:
    uvt = reglas.get("uvt", 49799)
    datos_guardados = datos_guardados or {}

    ingresos_laborales = 0.0
    rentas_capital = 0.0
    rentas_no_lab = 0.0
    retenciones = 0.0
    patrimonio_bruto = 0.0

    for doc in docs:
        d = doc["datos"]
        cat = doc["categoria"]

        if cat == "ingresos":
            ingresos_laborales += _num(d, "total_ingresos", "salario_mensual") * (
                12 if "salario_mensual" in d and "total_ingresos" not in d else 1
            )
            retenciones += _num(d, "total_retencion")

        elif cat == "bancos":
            rentas_capital += _num(d, "rendimientos", "intereses")

        elif cat in ("patrimonio", "bienes"):
            patrimonio_bruto += _num(d, "valor")

    # Valores manuales tienen prioridad sobre los extraídos de documentos
    def _manual_or_ocr(campo: str, ocr_val: float) -> float:
        manual = float(datos_guardados.get(campo) or 0)
        return manual if manual > 0 else ocr_val

    ingresos_laborales = _manual_or_ocr("ingresos_laborales", ingresos_laborales)
    rentas_capital = _manual_or_ocr("rentas_capital", rentas_capital)
    rentas_no_lab = _manual_or_ocr("rentas_no_laborales", rentas_no_lab)
    retenciones = _manual_or_ocr("retenciones", retenciones)
    patrimonio_bruto = _manual_or_ocr("patrimonio_bruto", patrimonio_bruto)

    dividendos = float(datos_guardados.get("dividendos") or 0)
    ganancias_oc = float(datos_guardados.get("ganancias_ocasionales") or 0)
    aportes_pension = float(datos_guardados.get("aportes_pension") or 0)
    afc_fvp_val = float(datos_guardados.get("afc_fvp") or 0)
    intereses_viv = float(datos_guardados.get("intereses_vivienda") or 0)
    medicina_prep = float(datos_guardados.get("medicina_prepagada") or 0)
    num_dependientes = int(datos_guardados.get("dependientes") or 0)

    # Ingresos netos cédula general (Art. 336 ET — base para límite 40%/1.340 UVT)
    ingresos_netos = max(0.0,
                         ingresos_laborales - aportes_pension
                         + rentas_capital
                         + rentas_no_lab
                         )

    # Límite 40% / 1.340 UVT (Art. 336 ET) sobre total consolidado
    tope_limitadas = min(ingresos_netos * 0.40, 1340 * uvt)

    # Rentas exentas laborales — Art. 206 num 10: 25% con límite 240 UVT/mes
    limite_exento_anual = 240 * 12 * uvt
    exento_laboral_bruto = min(ingresos_laborales * 0.25, limite_exento_anual) + afc_fvp_val

    # Deducciones
    deduccion_dep = min(num_dependientes, 4) * 72 * uvt
    deducciones_brutas = intereses_viv + medicina_prep + deduccion_dep

    # Aplicar tope global y distribuir proporcionalmente
    exentas_y_deduc_aplicar = min(exento_laboral_bruto + deducciones_brutas, tope_limitadas)
    total_bruto = exento_laboral_bruto + deducciones_brutas
    if total_bruto > 0:
        factor = exentas_y_deduc_aplicar / total_bruto
        rentas_exentas_final = round(exento_laboral_bruto * factor, 2)
        deducciones_final = round(deducciones_brutas * factor, 2)
    else:
        rentas_exentas_final = 0.0
        deducciones_final = 0.0

    renta_gravable = max(0.0, ingresos_netos - rentas_exentas_final - deducciones_final)

    return {
        "ingresos_laborales": round(ingresos_laborales, 2),
        "rentas_capital": round(rentas_capital, 2),
        "rentas_no_laborales": round(rentas_no_lab, 2),
        "dividendos": round(dividendos, 2),
        "ganancias_ocasionales": round(ganancias_oc, 2),
        "retenciones": round(retenciones, 2),
        "patrimonio_bruto": round(patrimonio_bruto, 2),
        "rentas_exentas": rentas_exentas_final,
        "deducciones": deducciones_final,
        "renta_gravable": round(renta_gravable, 2),
    }


def _num(d: dict, *keys: str) -> float:
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(str(v).replace(",", "").replace("$", "").strip())
            except (ValueError, TypeError):
                continue
    return 0.0


# ─── Tabla Art. 241 ET ────────────────────────────────────────────────────────

def _calcular_impuesto(renta_gravable: float, reglas: dict) -> float:
    """Aplica tabla Art. 241 ET en UVT. Retorna impuesto en pesos."""
    uvt = reglas.get("uvt", 49799)
    tabla = reglas.get("tabla_art241", _tabla_art241_default())
    renta_en_uvt = renta_gravable / uvt

    for tramo in reversed(tabla):
        desde = tramo["desde_uvt"]
        hasta = tramo.get("hasta_uvt")
        if renta_en_uvt > desde:
            exceso_uvt = renta_en_uvt - desde
            if hasta is not None:
                exceso_uvt = min(exceso_uvt, hasta - desde)
            impuesto_uvt = tramo["impuesto_base_uvt"] + exceso_uvt * tramo["tarifa_marginal"]
            return round(impuesto_uvt * uvt, 2)
    return 0.0


def _tramo_aplicado(renta_gravable: float, reglas: dict) -> dict:
    uvt = reglas.get("uvt", 49799)
    tabla = reglas.get("tabla_art241", _tabla_art241_default())
    renta_en_uvt = renta_gravable / uvt
    for tramo in reversed(tabla):
        if renta_en_uvt > tramo["desde_uvt"]:
            return {
                "desde_uvt": tramo["desde_uvt"],
                "hasta_uvt": tramo.get("hasta_uvt"),
                "tarifa_marginal": tramo["tarifa_marginal"],
                "renta_en_uvt": round(renta_en_uvt, 2),
            }
    return {"tarifa_marginal": 0.0, "renta_en_uvt": round(renta_en_uvt, 2)}


# ─── Cédula dividendos (Art. 242 ET) ─────────────────────────────────────────

def _calcular_impuesto_dividendos(dividendos: float, uvt: float) -> float:
    limite = 300 * uvt
    if dividendos <= limite:
        return 0.0
    return round((dividendos - limite) * 0.15, 2)


# ─── Ganancias ocasionales (Art. 299-316 ET) ──────────────────────────────────

def _calcular_impuesto_ocasional(ganancia: float, tipo: str | None) -> float:
    if ganancia <= 0:
        return 0.0
    tarifa = 0.20 if tipo == "loteria" else 0.10
    return round(ganancia * tarifa, 2)


# ─── Patrimonio líquido ───────────────────────────────────────────────────────

def _calcular_patrimonio_liquido(bruto: float, pasivos: float) -> float:
    return max(0.0, bruto - pasivos)


# ─── Overrides manuales ───────────────────────────────────────────────────────

_OVERRIDE_ALLOWED = frozenset({
    "ingresos_laborales", "rentas_capital", "rentas_no_laborales",
    "dividendos", "ganancias_ocasionales", "rentas_exentas", "deducciones",
    "retenciones", "patrimonio_bruto", "patrimonio_liquido",
    "aportes_pension", "afc_fvp", "intereses_vivienda", "medicina_prepagada", "pasivos",
})


def _aplicar_overrides(consolidado: dict, ajuste_manual: dict | None) -> dict:
    if not ajuste_manual:
        return consolidado
    result = dict(consolidado)
    aplicados = []
    for k, v in ajuste_manual.items():
        if k not in _OVERRIDE_ALLOWED:
            continue
        if k != "rentas_no_laborales" and isinstance(v, (int, float)) and v < 0:
            continue
        result[k] = float(v)
        aplicados.append(k)
    result["_ajustados_manualmente"] = aplicados
    return result


# ─── Risk checks ──────────────────────────────────────────────────────────────

def _detectar_inconsistencias(consolidado: dict, docs: list[dict]) -> list[dict]:
    issues: list[dict] = []

    if consolidado["ingresos_laborales"] == 0 and not any(d["categoria"] == "ingresos" for d in docs):
        issues.append({
            "nivel": "advertencia",
            "codigo": "SIN_INGRESOS",
            "mensaje": "No se encontraron documentos de ingresos (certificados de retención)",
        })

    docs_error = [d for d in docs if d.get("estado_ocr") == "error"]
    if docs_error:
        issues.append({
            "nivel": "advertencia",
            "codigo": "DOCS_OCR_ERROR",
            "mensaje": f"{len(docs_error)} documento(s) con error de OCR — revisar manualmente",
        })

    low_conf = [d for d in docs if 0 < d["confianza"] < 0.5]
    if low_conf:
        issues.append({
            "nivel": "info",
            "codigo": "CLASIFICACION_BAJA",
            "mensaje": f"{len(low_conf)} documento(s) con confianza de clasificación < 50% — verificar categoría",
        })

    if consolidado["retenciones"] > consolidado.get("renta_gravable", 0) * 0.5 and consolidado["retenciones"] > 0:
        issues.append({
            "nivel": "info",
            "codigo": "RETENCIONES_ALTAS",
            "mensaje": "Retenciones son > 50% de la renta gravable — probable saldo a favor",
        })

    return issues
