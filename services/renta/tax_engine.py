"""services/renta/tax_engine.py — Motor de declaración de renta personas naturales.

Implementa Art. 241 ET (tabla progresiva en UVT) para año gravable 2025.
Fuente de reglas: tabla reglas_tributarias en DB (seed en migración 004).
"""
from __future__ import annotations

import json
from typing import Any


# ─── Entrada al motor ─────────────────────────────────────────────────────────

def calcular_declaracion(contribuyente_id: str, año: int) -> dict:
    """
    Lee documentos del contribuyente, consolida valores y aplica tabla Art. 241 ET.

    Returns:
        dict con todos los campos de renta_declaraciones + detalle_calculo + inconsistencias
    """
    from sqlalchemy import text
    from db.database import get_db

    with get_db() as db:
        reglas = _cargar_reglas(db, año)
        docs = _cargar_documentos(db, contribuyente_id)

    consolidado = _consolidar_datos(docs, reglas)
    impuesto = _calcular_impuesto(consolidado["renta_gravable"], reglas)
    inconsistencias = _detectar_inconsistencias(consolidado, docs)

    saldo_pagar = max(0.0, impuesto - consolidado["retenciones"])
    saldo_favor = max(0.0, consolidado["retenciones"] - impuesto)

    detalle = {
        "uvt":              reglas.get("uvt", 49799),
        "consolidado":      consolidado,
        "impuesto_bruto":   impuesto,
        "tramo_aplicado":   _tramo_aplicado(consolidado["renta_gravable"], reglas),
    }

    return {
        "año_gravable":          año,
        "patrimonio_bruto":      consolidado["patrimonio_bruto"],
        "patrimonio_liquido":    consolidado["patrimonio_liquido"],
        "ingresos_laborales":    consolidado["ingresos_laborales"],
        "rentas_capital":        consolidado["rentas_capital"],
        "rentas_no_laborales":   consolidado["rentas_no_laborales"],
        "dividendos":            consolidado["dividendos"],
        "ganancias_ocasionales": consolidado["ganancias_ocasionales"],
        "rentas_exentas":        consolidado["rentas_exentas"],
        "deducciones":           consolidado["deducciones"],
        "retenciones":           consolidado["retenciones"],
        "impuesto_cargo":        impuesto,
        "saldo_pagar":           saldo_pagar,
        "saldo_favor":           saldo_favor,
        "estado":                "borrador",
        "inconsistencias":       inconsistencias,
        "detalle_calculo":       detalle,
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

    # Defaults si no hay seed en DB
    if "uvt" not in reglas:
        reglas["uvt"] = 49799
    if "tabla_art241" not in reglas:
        reglas["tabla_art241"] = _tabla_art241_default()
    return reglas


def _tabla_art241_default() -> list[dict]:
    return [
        {"desde_uvt": 0,     "hasta_uvt": 1090,  "tarifa_marginal": 0.00, "impuesto_base_uvt": 0},
        {"desde_uvt": 1090,  "hasta_uvt": 1700,  "tarifa_marginal": 0.19, "impuesto_base_uvt": 0},
        {"desde_uvt": 1700,  "hasta_uvt": 4100,  "tarifa_marginal": 0.28, "impuesto_base_uvt": 116},
        {"desde_uvt": 4100,  "hasta_uvt": 8670,  "tarifa_marginal": 0.33, "impuesto_base_uvt": 788},
        {"desde_uvt": 8670,  "hasta_uvt": 18970, "tarifa_marginal": 0.35, "impuesto_base_uvt": 2296},
        {"desde_uvt": 18970, "hasta_uvt": 31000, "tarifa_marginal": 0.37, "impuesto_base_uvt": 5901},
        {"desde_uvt": 31000, "hasta_uvt": None,  "tarifa_marginal": 0.39, "impuesto_base_uvt": 10352},
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
            "id":        str(r[0]),
            "categoria": r[1],
            "datos":     datos,
            "confianza": float(r[4] or 0),
        })
    return result


# ─── Consolidación ────────────────────────────────────────────────────────────

def _consolidar_datos(docs: list[dict], reglas: dict) -> dict:
    uvt = reglas.get("uvt", 49799)

    ingresos_laborales = 0.0
    rentas_capital     = 0.0
    rentas_no_lab      = 0.0
    dividendos         = 0.0
    ganancias_oc       = 0.0
    retenciones        = 0.0
    patrimonio_bruto   = 0.0
    patrimonio_liq     = 0.0

    for doc in docs:
        d = doc["datos"]
        cat = doc["categoria"]

        if cat == "ingresos":
            ingresos_laborales += _num(d, "total_ingresos", "salario_mensual") * (
                12 if "salario_mensual" in d and "total_ingresos" not in d else 1
            )
            retenciones += _num(d, "total_retencion")

        elif cat == "bancos":
            # Rendimientos financieros van a rentas de capital
            rentas_capital += _num(d, "rendimientos", "intereses")

        elif cat == "patrimonio":
            patrimonio_bruto += _num(d, "valor")

        elif cat == "bienes":
            patrimonio_bruto += _num(d, "valor")

    # Pasivos estimados en 0 (usuario puede ajustar)
    patrimonio_liq = max(0.0, patrimonio_bruto)

    # Rentas exentas laborales — Art. 206 num 10: 25% con límite 240 UVT/mes
    limite_exento_anual = 240 * 12 * uvt  # 240 UVT/mes × 12 meses
    exento_laboral = min(ingresos_laborales * 0.25, limite_exento_anual)

    # Deducciones básicas aplicables (salud prepagada + dependientes en 0 si no hay docs)
    deduccion_dependientes = 0.0  # requiere doc categoría "otros" con tag dependiente
    deduccion_intereses    = 0.0  # requiere doc "patrimonio" tipo hipoteca
    deducciones_total = deduccion_dependientes + deduccion_intereses

    # Renta gravable laboral (cédula general simplificada)
    renta_gravable = max(
        0.0,
        ingresos_laborales
        + rentas_capital
        + rentas_no_lab
        - exento_laboral
        - deducciones_total
    )

    return {
        "ingresos_laborales":    round(ingresos_laborales, 2),
        "rentas_capital":        round(rentas_capital, 2),
        "rentas_no_laborales":   round(rentas_no_lab, 2),
        "dividendos":            round(dividendos, 2),
        "ganancias_ocasionales": round(ganancias_oc, 2),
        "retenciones":           round(retenciones, 2),
        "patrimonio_bruto":      round(patrimonio_bruto, 2),
        "patrimonio_liquido":    round(patrimonio_liq, 2),
        "rentas_exentas":        round(exento_laboral, 2),
        "deducciones":           round(deducciones_total, 2),
        "renta_gravable":        round(renta_gravable, 2),
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
        hasta = tramo.get("hasta_uvt")  # None = sin límite
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
                "desde_uvt":        tramo["desde_uvt"],
                "hasta_uvt":        tramo.get("hasta_uvt"),
                "tarifa_marginal":  tramo["tarifa_marginal"],
                "renta_en_uvt":     round(renta_en_uvt, 2),
            }
    return {"tarifa_marginal": 0.0, "renta_en_uvt": round(renta_en_uvt, 2)}


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

    if consolidado["retenciones"] > consolidado["renta_gravable"] * 0.5 and consolidado["retenciones"] > 0:
        issues.append({
            "nivel": "info",
            "codigo": "RETENCIONES_ALTAS",
            "mensaje": "Retenciones son > 50% de la renta gravable — probable saldo a favor",
        })

    return issues
