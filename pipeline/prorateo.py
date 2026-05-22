"""
Prorrateo de IVA según normativa colombiana (Art. 490 ET).

Fórmula:
    % prorrateo = ingresos_gravados / (ingresos_gravados + ingresos_excluidos)
    IVA descontable = IVA total × % prorrateo

Mandatos/Peajes: IVA siempre NO descontable.
Notas Crédito: restan de sus respectivos acumulados.
"""

import pandas as pd


def _mes(fecha: str) -> str:
    """Extrae YYYY-MM de una fecha YYYY-MM-DD."""
    try:
        return str(fecha)[:7]
    except Exception:
        return "Sin fecha"


def calcular_prorateo(
    df: pd.DataFrame,
    ingresos_gravados: dict[str, float],
    ingresos_excluidos: dict[str, float],
) -> pd.DataFrame:
    """
    df: DataFrame con columnas tipo, fecha, iva_19, iva_5.
    ingresos_gravados / ingresos_excluidos: {YYYY-MM: valor_COP}

    Retorna DataFrame agrupado por mes con columnas:
        mes, iva_total, iva_mandatos, iva_base,
        pct_prorateo, iva_descontable, iva_no_descontable
    """
    df = df.copy()
    df["mes"] = df["fecha"].apply(_mes)
    df["iva_total"] = df["iva_19"].fillna(0) + df["iva_5"].fillna(0)

    filas = []
    for mes, grupo in df.groupby("mes"):
        es_mandato = grupo["tipo"].str.lower().str.contains("mandato|peaje", na=False)
        mandatos  = grupo[es_mandato]["iva_total"].sum()
        iva_base  = grupo[~es_mandato]["iva_total"].sum()  # IVA sujeto a prorrateo

        grav  = ingresos_gravados.get(mes, 0.0)
        excl  = ingresos_excluidos.get(mes, 0.0)
        total_ing = grav + excl

        if total_ing > 0:
            pct = grav / total_ing
        else:
            pct = 1.0  # sin datos → conservador: 100% descontable

        iva_desc     = round(iva_base * pct, 2)
        iva_no_desc  = round(iva_base * (1 - pct) + mandatos, 2)

        filas.append({
            "mes":               mes,
            "iva_total":         round(iva_base + mandatos, 2),
            "iva_mandatos":      round(mandatos, 2),
            "iva_base_prorateo": round(iva_base, 2),
            "ingresos_gravados": grav,
            "ingresos_excluidos": excl,
            "pct_prorateo":      round(pct * 100, 2),
            "iva_descontable":   iva_desc,
            "iva_no_descontable": iva_no_desc,
        })

    return pd.DataFrame(filas).sort_values("mes").reset_index(drop=True)


def calcular_prorateo_simple(df: pd.DataFrame) -> pd.DataFrame:
    """
    Versión sin datos de ingresos: muestra IVA agrupado por mes
    con advertencia de que el % prorrateo requiere datos adicionales.
    """
    empty_grav = {}
    empty_excl = {}
    result = calcular_prorateo(df, empty_grav, empty_excl)
    result["advertencia"] = "Ingresos no ingresados — prorrateo al 100% (revisar)"
    return result
