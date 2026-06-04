"""Tests unitarios para los bugs en exogenas/extractor.py.

Cubre 6 casos documentados sin necesidad de archivos reales.
"""
from __future__ import annotations

import pytest


# ── helpers ────────────────────────────────────────────────────────────────────

def _parse(s: str) -> float:
    from exogenas.extractor import _parse_money
    return _parse_money(s)


def _emisor(text: str):
    from exogenas.extractor import _extract_emisor
    return _extract_emisor(text)


def _amounts(text: str, tipo: str = "RENTA", nit: str = "") -> tuple[float, float]:
    from exogenas.extractor import _extract_amounts
    return _extract_amounts(text, tipo, nit_hint=nit)


def _tipo_doc(nit: str, text: str) -> str:
    from exogenas.extractor import _tipo_doc_from_context
    return _tipo_doc_from_context(nit, text)


# ── Bug 3: IND FANTASIA ICA — base/ret intercambiados ─────────────────────────

TEXT_ICA_FANTASIA = """\
CERTIFICADO DE RETENCIÓN ICA
Contribuyente IND FANTASIA
NIT 900123456-1

Período fiscal 2025
Año gravable 2025
Fecha 25.12.31

Enero - Diciembre   50.000.000   2.025
MONTO DEL PAGO SUJETO A RETENCIÓN ICA
50.000.000  2.025
"""


def test_ica_fantasia_base_no_es_fecha():
    """25.12.31 no debe parsear como monto (es una fecha)."""
    assert _parse("25.12.31") == 0.0


def test_ica_fantasia_year_not_retencion():
    """
    Cuando la bimestral row tiene (50.000.000, 2.025) y 2025 es un año,
    el ratio 2025/50000000 ≈ 0.00004 está BAJO 0.001 → no debe usarse.
    Después del fix, solo se retorna si 0.001 < r/b < 0.025.
    """
    # La fila bimestral sería:  base_str="50.000.000", ret_str="2.025"
    # _parse_money("2.025") = 2025 (3 decimales → miles)
    # ratio = 2025/50000000 = 0.0000405 → por debajo del umbral
    b, r = _amounts(TEXT_ICA_FANTASIA, tipo="ICA")
    # Con el fix, debe venir de _RE_ICA_MONTO_TOTAL o fallar; NO retornar ret=2025
    # Si hay montos reales detectados, no deben ser base=50000000, ret=2025
    if b > 0 and r > 0:
        ratio = r / b
        assert ratio > 0.001, f"ratio {ratio:.6f} demasiado bajo — año confundido con retención"


def test_ica_bimestral_valida_ratio():
    """Row bimestral válida: base=50M, ret=500k → ratio=0.01 ∈ (0.001, 0.025) → pasa."""
    text = """\
CERTIFICADO DE RETENCIÓN ICA
NIT 900123456-1

Enero - Diciembre   50.000.000   500.000
"""
    b, r = _amounts(text, tipo="ICA")
    assert b == 50_000_000
    assert r == 500_000


# ── Bug 4: LEAM SAS — retención=2500 (captura tasa como monto) ────────────────

TEXT_LEAM = """\
Certificado de Retención en la Fuente
LEAM SAS NIT 900111222-3

Señores: Proveedor ABC

TOTAL COMPRAS 10.000.000 2.500

Ciudad Bogotá
"""


def test_leam_total_line_tasa_como_monto():
    """
    '2.500' debería ser tasa 2.5% NOT retención $2,500.
    Con base=10M y r=2500: ratio=0.00025 < 0.001 → NO debe retornarse.
    """
    b, r = _amounts(TEXT_LEAM)
    # Si el TOTAL_LINE retorna (10000000, 2500), ratio=0.00025 < 0.001 → BUG
    # Con el fix, debe rechazarse y buscar en otros patrones o retornar (0, 0)
    if b > 0 and r > 0:
        ratio = r / b
        assert ratio > 0.001, (
            f"Bug LEAM: retención={r} parece tasa (ratio={ratio:.6f} < 0.001)"
        )


def test_leam_fix_pct_as_amount_r_pequeno():
    """_fix_pct_as_amount: r=2.5 con base=1M → recalcula a 25000."""
    from exogenas.extractor import _fix_pct_as_amount
    resultado = _fix_pct_as_amount(1_000_000, 2.5)
    assert resultado == pytest.approx(25_000.0)


def test_leam_fix_pct_as_amount_r_normal():
    """_fix_pct_as_amount no toca retenciones con ratio normal."""
    from exogenas.extractor import _fix_pct_as_amount
    assert _fix_pct_as_amount(10_000_000, 250_000) == 250_000


# ── Bug 5: EL BUCANERO RTE IVA — razón social vacía ──────────────────────────

TEXT_SAP_IVA = """\
CERTIFICADO DE RETENCIÓN IVA

EL BUCANERO SA
Calle 50 # 40-20 Medellín

Company Code Tax No. 8001974634
(TOTAL) SERVICIOS  5.000.000  0.75  37.500
"""


def test_sap_iva_razon_no_vacia():
    """
    SAP IVA: NIT en la misma línea 'Company Code Tax No. 8001974634'.
    El nombre 'EL BUCANERO SA' está en las líneas ANTERIORES.
    """
    razon, nit, dv = _emisor(TEXT_SAP_IVA)
    assert nit == "8001974634", f"NIT no extraído correctamente: '{nit}'"
    assert razon != "", f"Bug EL BUCANERO: razón social vacía (nit={nit})"
    assert "BUCANERO" in razon.upper()


TEXT_SAP_IVA_NOMBRE_SIGUIENTE = """\
CERTIFICADO RETEIVA
Company Code Tax No. 8001974634
EL BUCANERO SA
"""


def test_sap_iva_nombre_linea_siguiente():
    """Cuando el nombre está en la línea siguiente al 'Company Code Tax No. NIT'."""
    razon, nit, _ = _emisor(TEXT_SAP_IVA_NOMBRE_SIGUIENTE)
    assert nit == "8001974634"
    assert "BUCANERO" in razon.upper()


# ── Bug 6: COMERTEX — "GIRON NIT 3144113024" → razon="GIRON" ─────────────────

TEXT_COMERTEX = """\
CERTIFICADO DE RETENCIÓN EN LA FUENTE
COMERCIALIZADORA COMERTEX LTDA
GIRON NIT 3144113024-5

Señores: Proveedor XYZ NIT 800.345.678-9

TOTAL SERVICIOS  8.000.000  2.5%  200.000
"""


def test_comertex_razon_no_es_ciudad():
    """
    Layout: 'GIRON NIT 3144113024-5' en una línea.
    re.split('NIT', ...) extraería 'GIRON' como razón social.
    Con el fix, 'GIRON' es un municipio (68-307) → se descarta y se sube una línea.
    """
    razon, nit, _ = _emisor(TEXT_COMERTEX)
    assert nit == "3144113024", f"NIT mal extraído: '{nit}'"
    assert razon.upper() not in ("GIRON", "GIRÓN"), (
        f"Bug COMERTEX: razón social es la ciudad '{razon}'"
    )
    # La razón social real debe contener COMERTEX
    assert "COMERTEX" in razon.upper(), f"Razón social incorrecta: '{razon}'"


def test_comertex_tipo_doc_nit_10_digitos():
    """NIT de 10 dígitos que NO empieza con 3 → tipo_doc='31'."""
    text = "NIT 3144113024 agente retenedor"
    # 3144113024 tiene 10 dígitos y empieza con 3 → podría confundirse con cédula
    # pero en este caso el label es NIT → debe ser '31'
    tipo = _tipo_doc("3144113024", text)
    assert tipo == "31"


def test_tipo_doc_cedula_label():
    """Cuando el contexto dice 'Cédula' → tipo_doc='13'."""
    nit = "12345678"
    text = "Cédula de Ciudadanía 12345678"
    tipo = _tipo_doc(nit, text)
    assert tipo == "13"


def test_tipo_doc_nit_label():
    """Cuando el contexto dice 'NIT' → tipo_doc='31'."""
    nit = "900123456"
    text = "NIT 900123456-1 empresa"
    tipo = _tipo_doc(nit, text)
    assert tipo == "31"


# ── Bug 1: Imagen baja calidad — _read_image usa variantes de preprocesamiento ─

def test_preprocess_genera_variantes():
    """_preprocess_for_ocr debe generar al menos 3 variantes para maximizar OCR."""
    try:
        from PIL import Image
        from exogenas.extractor import _preprocess_for_ocr
        img = Image.new("RGB", (800, 600), color=(240, 240, 240))
        variants = _preprocess_for_ocr(img)
        assert len(variants) >= 3, "Debe haber al menos 3 variantes de preprocesamiento"
    except ImportError:
        pytest.skip("PIL no disponible")


# ── Bug 2: Formato minimalista — _RE_BASE_LABEL y _RE_RET_LABEL ───────────────

TEXT_MINIMALISTA = """\
CERTIFICADO DE RETENCIÓN EN LA FUENTE
Año gravable 2025
Proveedor: SERVICIOS CAROLINA SAS
NIT: 901234567-8

BASE GRAVABLE: $5.000.000
RETENCIÓN EN LA FUENTE: $125.000

Expedido en Bogotá
"""


def test_minimalista_base_ret_label():
    """Formato con etiquetas 'BASE GRAVABLE' + 'RETENCIÓN EN LA FUENTE' → detectado."""
    b, r = _amounts(TEXT_MINIMALISTA)
    assert b == pytest.approx(5_000_000)
    assert r == pytest.approx(125_000)


TEXT_MINIMALISTA2 = """\
RETENCIÓN EN LA FUENTE 2025
VALOR BASE: 3.500.000
VALOR RETENIDO: 87.500
"""


def test_minimalista_valor_base_retenido():
    """Formato 'VALOR BASE' + 'VALOR RETENIDO' (variante minimalista)."""
    b, r = _amounts(TEXT_MINIMALISTA2)
    assert b == pytest.approx(3_500_000)
    assert r == pytest.approx(87_500)


# ── parse_money — fechas no deben parsearse como montos ──────────────────────

@pytest.mark.parametrize("fecha", [
    "25.12.31", "2025.12.31", "31/12/2025", "31-12-25", "2025-12-31",
])
def test_parse_money_rechaza_fechas(fecha: str):
    assert _parse(fecha) == 0.0, f"'{fecha}' fue parseada como monto"


@pytest.mark.parametrize("s,expected", [
    ("1.234.567", 1_234_567),
    ("1.234.567,00", 1_234_567.0),
    ("2.500", 2_500),           # 3 decimales → miles
    ("2,500", 2_500),           # 3 decimales → miles
    ("2.5", 2.5),               # 1 decimal → float
    ("144.325", 144_325),
    ("($ 144.325)", 144_325),
])
def test_parse_money_casos(s: str, expected: float):
    assert _parse(s) == pytest.approx(expected), f"_parse_money({s!r}) fallo"
