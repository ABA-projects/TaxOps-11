"""Pruebas unitarias para prorateo.py — Art. 490 E.T."""

import pandas as pd
import pytest

from pipeline.prorateo import calcular_prorateo, calcular_prorateo_simple


def _df(*filas):
    return pd.DataFrame(list(filas))


def _fila(tipo="Factura Electrónica", fecha="2026-02-16", iva19=0.0, iva5=0.0):
    return {"tipo": tipo, "fecha": fecha, "iva_19": iva19, "iva_5": iva5}


# ─────────────────────────────────────────────
# calcular_prorateo — con datos de ingresos
# ─────────────────────────────────────────────

class TestCalcularProrateo:
    def test_100_pct_solo_gravados(self):
        df = _df(_fila(iva19=114_305.64))
        result = calcular_prorateo(df, {"2026-02": 5_000_000.0}, {})
        row = result.iloc[0]
        assert row["pct_prorateo"] == 100.0
        assert row["iva_descontable"] == pytest.approx(114_305.64, abs=0.01)
        assert row["iva_no_descontable"] == 0.0

    def test_50_50_gravados_excluidos(self):
        df = _df(_fila(iva19=100_000.0))
        result = calcular_prorateo(
            df,
            {"2026-02": 500_000.0},
            {"2026-02": 500_000.0},
        )
        row = result.iloc[0]
        assert row["pct_prorateo"] == 50.0
        assert row["iva_descontable"] == pytest.approx(50_000.0, abs=0.01)
        assert row["iva_no_descontable"] == pytest.approx(50_000.0, abs=0.01)

    def test_0_pct_solo_excluidos(self):
        df = _df(_fila(iva19=50_000.0))
        result = calcular_prorateo(df, {}, {"2026-02": 1_000_000.0})
        row = result.iloc[0]
        assert row["pct_prorateo"] == 0.0
        assert row["iva_descontable"] == 0.0
        assert row["iva_no_descontable"] == pytest.approx(50_000.0, abs=0.01)

    def test_sin_datos_ingresos_prorrateo_100(self):
        # Sin ingresos → pct conservador 100% (no penalizar al contribuyente)
        df = _df(_fila(iva19=20_000.0))
        result = calcular_prorateo(df, {}, {})
        assert result.iloc[0]["pct_prorateo"] == 100.0


class TestMandatosPeajes:
    def test_mandato_va_a_no_descontable(self):
        df = _df(_fila(tipo="Mandato/Peaje", iva19=5_000.0))
        result = calcular_prorateo(df, {"2026-02": 1_000_000.0}, {})
        row = result.iloc[0]
        assert row["iva_mandatos"] == pytest.approx(5_000.0, abs=0.01)
        assert row["iva_base_prorateo"] == 0.0
        assert row["iva_descontable"] == 0.0
        assert row["iva_no_descontable"] == pytest.approx(5_000.0, abs=0.01)

    def test_mezcla_factura_y_mandato(self):
        df = _df(
            _fila(tipo="Factura Electrónica", iva19=10_000.0),
            _fila(tipo="Mandato/Peaje",       iva19=5_000.0),
        )
        result = calcular_prorateo(df, {"2026-02": 1_000_000.0}, {})
        row = result.iloc[0]
        assert row["iva_mandatos"] == pytest.approx(5_000.0, abs=0.01)
        assert row["iva_base_prorateo"] == pytest.approx(10_000.0, abs=0.01)
        assert row["iva_no_descontable"] == pytest.approx(5_000.0, abs=0.01)


class TestNotasCredito:
    def test_nota_credito_resta_del_mes(self):
        df = _df(
            _fila(tipo="Factura Electrónica", iva19=19_000.0),
            _fila(tipo="Nota Crédito",        iva19=-5_000.0),
        )
        result = calcular_prorateo(df, {"2026-02": 1_000_000.0}, {})
        row = result.iloc[0]
        assert row["iva_base_prorateo"] == pytest.approx(14_000.0, abs=0.01)
        assert row["iva_descontable"] == pytest.approx(14_000.0, abs=0.01)

    def test_nota_credito_puede_dejar_iva_total_negativo(self):
        # Nota crédito mayor que factura en el mes → IVA negativo es válido
        df = _df(
            _fila(tipo="Factura Electrónica", iva19=5_000.0),
            _fila(tipo="Nota Crédito",        iva19=-10_000.0),
        )
        result = calcular_prorateo(df, {"2026-02": 1_000_000.0}, {})
        assert result.iloc[0]["iva_base_prorateo"] == pytest.approx(-5_000.0, abs=0.01)


class TestAgrupacionPorMes:
    def test_dos_meses_separados(self):
        df = _df(
            _fila(fecha="2026-01-15", iva19=10_000.0),
            _fila(fecha="2026-02-10", iva19=20_000.0),
        )
        result = calcular_prorateo(df, {}, {})
        assert len(result) == 2
        meses = result["mes"].tolist()
        assert "2026-01" in meses
        assert "2026-02" in meses

    def test_mismo_mes_acumula(self):
        df = _df(
            _fila(fecha="2026-02-10", iva19=10_000.0),
            _fila(fecha="2026-02-20", iva19=20_000.0),
        )
        result = calcular_prorateo(df, {"2026-02": 1_000_000.0}, {})
        assert len(result) == 1
        assert result.iloc[0]["iva_total"] == pytest.approx(30_000.0, abs=0.01)


class TestProrateoSimple:
    def test_tiene_advertencia(self):
        df = _df(_fila(iva19=10_000.0))
        result = calcular_prorateo_simple(df)
        assert "advertencia" in result.columns
        assert result.iloc[0]["advertencia"] != ""

    def test_pct_es_100(self):
        df = _df(_fila(iva19=10_000.0))
        result = calcular_prorateo_simple(df)
        assert result.iloc[0]["pct_prorateo"] == 100.0
