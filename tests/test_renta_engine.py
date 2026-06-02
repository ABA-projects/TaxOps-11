"""Tests para services/renta/tax_engine.py — Semana 4."""
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_reglas(uvt=49799):
    from services.renta.tax_engine import _tabla_art241_default
    return {
        "uvt": uvt,
        "tabla_art241": _tabla_art241_default(),
    }


# ── Test límite 40% / 1.340 UVT (Art. 336 ET) ───────────────────────────────

def test_limite_40pct_aplicado():
    """Rentas exentas brutas > 40% ingresos → se recortan al 40%."""
    from services.renta.tax_engine import _consolidar_datos
    docs = [{
        "id": "1", "categoria": "ingresos", "confianza": 0.9,
        "datos": {"total_ingresos": 100_000_000, "total_retencion": 0},
    }]
    reglas = _make_reglas()
    result = _consolidar_datos(docs, reglas)
    ingresos_netos = result["ingresos_laborales"] - 0  # sin aportes_pension
    tope = min(ingresos_netos * 0.40, 1340 * 49799)
    # rentas_exentas + deducciones no puede superar el tope
    assert result["rentas_exentas"] + result["deducciones"] <= tope + 1


def test_limite_1340_uvt():
    """Con ingresos muy altos, el tope es 1.340 UVT, no 40%."""
    from services.renta.tax_engine import _consolidar_datos
    uvt = 49799
    # Ingresos de 5.000 UVT → 40% = 2000 UVT > 1340 → tope = 1340 UVT
    docs = [{
        "id": "1", "categoria": "ingresos", "confianza": 0.9,
        "datos": {"total_ingresos": 5000 * uvt, "total_retencion": 0},
    }]
    result = _consolidar_datos(docs, _make_reglas(uvt))
    assert result["rentas_exentas"] + result["deducciones"] <= 1340 * uvt + 1


# ── Test cédula dividendos (Art. 242 ET) ────────────────────────────────────

def test_dividendos_bajo_300_uvt_exentos():
    """Dividendos ≤ 300 UVT → impuesto_dividendos = 0."""
    from services.renta.tax_engine import _calcular_impuesto_dividendos
    uvt = 49799
    dividendos = 299 * uvt
    assert _calcular_impuesto_dividendos(dividendos, uvt) == 0.0


def test_dividendos_sobre_300_uvt_gravados():
    """Dividendos > 300 UVT → impuesto = (exceso) × 15%."""
    from services.renta.tax_engine import _calcular_impuesto_dividendos
    uvt = 49799
    dividendos = 400 * uvt  # 100 UVT sobre el límite
    expected = round(100 * uvt * 0.15, 2)
    assert _calcular_impuesto_dividendos(dividendos, uvt) == expected


# ── Test ganancias ocasionales (Art. 299-316 ET) ────────────────────────────

def test_ganancia_venta_activo_10pct():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(10_000_000, "venta_activo") == 1_000_000.0


def test_ganancia_herencia_10pct():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(10_000_000, "herencia") == 1_000_000.0


def test_ganancia_loteria_20pct():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(10_000_000, "loteria") == 2_000_000.0


def test_ganancia_negativa_es_cero():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(-1_000_000, "venta_activo") == 0.0


# ── Test patrimonio líquido ──────────────────────────────────────────────────

def test_patrimonio_liquido_con_pasivos():
    """patrimonio_liquido = patrimonio_bruto - pasivos (mín 0)."""
    from services.renta.tax_engine import _calcular_patrimonio_liquido
    assert _calcular_patrimonio_liquido(100_000_000, 30_000_000) == 70_000_000.0


def test_patrimonio_liquido_nunca_negativo():
    from services.renta.tax_engine import _calcular_patrimonio_liquido
    assert _calcular_patrimonio_liquido(10_000_000, 50_000_000) == 0.0


# ── Test overrides ajuste_manual ─────────────────────────────────────────────

def test_ajuste_manual_override_ingresos():
    """ajuste_manual sobreescribe el valor consolidado antes de calcular."""
    from services.renta.tax_engine import _aplicar_overrides
    consolidado = {"ingresos_laborales": 50_000_000, "retenciones": 0}
    ajuste = {"ingresos_laborales": 80_000_000}
    result = _aplicar_overrides(consolidado, ajuste)
    assert result["ingresos_laborales"] == 80_000_000


def test_ajuste_manual_key_invalida_ignorada():
    from services.renta.tax_engine import _aplicar_overrides
    consolidado = {"ingresos_laborales": 50_000_000}
    ajuste = {"campo_inventado": 999}
    result = _aplicar_overrides(consolidado, ajuste)
    assert "campo_inventado" not in result


def test_ajuste_manual_none_no_cambia_nada():
    from services.renta.tax_engine import _aplicar_overrides
    consolidado = {"ingresos_laborales": 50_000_000}
    result = _aplicar_overrides(consolidado, None)
    assert result["ingresos_laborales"] == 50_000_000
