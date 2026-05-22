"""Validación de facturas DIAN: totales, CUFE, duplicados, campos vacíos."""

import re
import pandas as pd

_CUFE_RE = re.compile(r"^[a-f0-9]{96}$", re.I)
_NIT_RE  = re.compile(r"^\d{6,12}$")
TOLERANCE = 1.0  # tolerancia COP para diferencias de redondeo


def _validate_row(row: pd.Series, cufe_counts: dict) -> tuple[str, str]:
    errors = []

    # 1. Campos críticos vacíos
    for campo in ("cufe", "folio", "fecha", "nit_emisor"):
        if not str(row.get(campo, "")).strip():
            errors.append(f"Campo vacío: {campo}")

    # 2. CUFE válido (96 hex chars)
    cufe = str(row.get("cufe", "")).strip()
    if cufe and not _CUFE_RE.match(cufe):
        errors.append("CUFE inválido (longitud/formato)")

    # 3. CUFE duplicado
    if cufe and cufe_counts.get(cufe, 0) > 1:
        errors.append("CUFE DUPLICADO")

    # 4. NIT formato
    for campo_nit in ("nit_emisor", "nit_receptor"):
        nit = str(row.get(campo_nit, "")).strip()
        if nit and not _NIT_RE.match(nit):
            errors.append(f"NIT sospechoso: {campo_nit}={nit}")

    # 5. Cuadre contable: subtotal + iva_19 + iva_5 ≈ total
    subtotal = float(row.get("subtotal", 0) or 0)
    iva19    = float(row.get("iva_19", 0) or 0)
    iva5     = float(row.get("iva_5", 0) or 0)
    total    = float(row.get("total", 0) or 0)
    calc     = subtotal + iva19 + iva5
    if total != 0 and abs(calc - total) > TOLERANCE:
        errors.append(
            f"Descuadre: {calc:,.0f} calculado ≠ {total:,.0f} total (dif={abs(calc-total):,.0f})"
        )

    # 6. Mandatos: no deben tener IVA descontable
    tipo = str(row.get("tipo", "")).lower()
    if "mandato" in tipo and (iva19 != 0 or iva5 != 0):
        errors.append("Mandato/Peaje con IVA: no es descontable")

    if errors:
        return "ERROR", " | ".join(errors)
    return "OK", ""


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas VALIDACION y OBSERVACION al DataFrame."""
    cufe_counts: dict[str, int] = {}
    for cufe in df["cufe"].dropna():
        cufe = str(cufe).strip()
        if cufe:
            cufe_counts[cufe] = cufe_counts.get(cufe, 0) + 1

    resultados = [_validate_row(row, cufe_counts) for _, row in df.iterrows()]
    df = df.copy()
    df["validacion"]  = [r[0] for r in resultados]
    df["observacion"] = [r[1] for r in resultados]
    return df


def build_validation_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Genera hoja VALIDACION con resumen de errores."""
    cols = ["archivo", "folio", "cufe", "tipo", "total", "validacion", "observacion"]
    available = [c for c in cols if c in df.columns]
    return df[available].copy()
