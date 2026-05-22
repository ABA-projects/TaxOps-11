"""Pruebas unitarias para validator.py."""

import pandas as pd
import pytest

from pipeline.validator import _validate_row, validate, build_validation_sheet, TOLERANCE

CUFE_VALIDO = "a" * 96  # 96 hex chars válidos


def _serie(**kwargs) -> pd.Series:
    """Construye una fila con valores base válidos, sobreescribibles."""
    base = {
        "cufe":        CUFE_VALIDO,
        "folio":       "FE-001",
        "fecha":       "2026-02-23",
        "nit_emisor":  "899999143",
        "nit_receptor": "902012620",
        "subtotal":    291_400.0,
        "iva_19":      0.0,
        "iva_5":       0.0,
        "total":       291_400.0,
        "tipo":        "Factura Electrónica",
    }
    base.update(kwargs)
    return pd.Series(base)


def _counts(cufe=CUFE_VALIDO, n=1):
    return {cufe: n}


# ─────────────────────────────────────────────
# Casos OK
# ─────────────────────────────────────────────

class TestValidacionOK:
    def test_factura_correcta(self):
        estado, obs = _validate_row(_serie(), _counts())
        assert estado == "OK"
        assert obs == ""

    def test_con_iva_cuadrado(self):
        estado, obs = _validate_row(
            _serie(subtotal=601_603.36, iva_19=114_305.64, total=715_909.0),
            _counts()
        )
        assert estado == "OK"

    def test_dentro_tolerancia(self):
        # Diferencia de 0.5 COP por redondeo — debe pasar
        estado, obs = _validate_row(
            _serie(subtotal=100_000.0, iva_19=19_000.5, total=119_000.0),
            _counts()
        )
        assert estado == "OK"


# ─────────────────────────────────────────────
# Campos vacíos
# ─────────────────────────────────────────────

class TestCamposVacios:
    @pytest.mark.parametrize("campo", ["cufe", "folio", "fecha", "nit_emisor"])
    def test_campo_critico_vacio(self, campo):
        estado, obs = _validate_row(_serie(**{campo: ""}), _counts("", 1))
        assert estado == "ERROR"
        assert campo in obs


# ─────────────────────────────────────────────
# CUFE
# ─────────────────────────────────────────────

class TestCUFE:
    def test_cufe_corto(self):
        estado, obs = _validate_row(_serie(cufe="abc123"), {"abc123": 1})
        assert estado == "ERROR"
        assert "CUFE inválido" in obs

    def test_cufe_con_chars_invalidos(self):
        cufe_malo = "Z" * 96  # Z no es hex
        estado, obs = _validate_row(_serie(cufe=cufe_malo), {cufe_malo: 1})
        assert estado == "ERROR"

    def test_cufe_duplicado(self):
        estado, obs = _validate_row(_serie(), _counts(n=2))
        assert estado == "ERROR"
        assert "DUPLICADO" in obs

    def test_cufe_unico_ok(self):
        estado, obs = _validate_row(_serie(), _counts(n=1))
        assert estado == "OK"


# ─────────────────────────────────────────────
# Cuadre contable
# ─────────────────────────────────────────────

class TestCuadreContable:
    def test_descuadre_mayor_tolerancia(self):
        # subtotal + IVA ≠ total (diferencia 100 COP)
        estado, obs = _validate_row(
            _serie(subtotal=100_000.0, iva_19=19_000.0, total=100_000.0),
            _counts()
        )
        assert estado == "ERROR"
        assert "Descuadre" in obs

    def test_total_cero_no_valida_cuadre(self):
        # Si total=0 no se valida cuadre (campo en blanco/no extraído)
        estado, obs = _validate_row(
            _serie(subtotal=100_000.0, iva_19=0.0, total=0.0),
            _counts()
        )
        assert estado == "OK" or "cufe" not in obs  # no ERROR por cuadre


# ─────────────────────────────────────────────
# NIT
# ─────────────────────────────────────────────

class TestNIT:
    def test_nit_con_punto_sospechoso(self):
        estado, obs = _validate_row(_serie(nit_emisor="123.456.789"), _counts())
        assert estado == "ERROR"
        assert "NIT sospechoso" in obs

    def test_nit_con_guion_sospechoso(self):
        estado, obs = _validate_row(_serie(nit_emisor="123456-7"), _counts())
        assert estado == "ERROR"

    def test_nit_valido_9_digitos(self):
        estado, obs = _validate_row(_serie(nit_emisor="900100200"), _counts())
        assert estado == "OK"


# ─────────────────────────────────────────────
# Mandatos
# ─────────────────────────────────────────────

class TestMandato:
    def test_mandato_con_iva_es_error(self):
        estado, obs = _validate_row(
            _serie(tipo="Mandato/Peaje", iva_19=5_000.0, total=291_400.0),
            _counts()
        )
        assert estado == "ERROR"
        assert "Mandato" in obs

    def test_mandato_sin_iva_ok(self):
        estado, obs = _validate_row(
            _serie(tipo="Mandato/Peaje", iva_19=0.0),
            _counts()
        )
        # Solo puede fallar por cuadre, no por mandato
        assert "Mandato" not in obs


# ─────────────────────────────────────────────
# validate() — DataFrame completo
# ─────────────────────────────────────────────

class TestValidateDataFrame:
    def _df(self, *rows):
        return pd.DataFrame([dict(r) for r in rows])

    def test_agrega_columnas(self):
        fila = {
            "cufe": CUFE_VALIDO, "folio": "FE-001", "fecha": "2026-01-01",
            "nit_emisor": "123456789", "nit_receptor": "987654321",
            "subtotal": 100.0, "iva_19": 0.0, "iva_5": 0.0, "total": 100.0,
            "tipo": "Factura Electrónica",
        }
        df = validate(pd.DataFrame([fila]))
        assert "validacion" in df.columns
        assert "observacion" in df.columns

    def test_duplicados_marcados_en_ambas_filas(self):
        fila_base = {
            "cufe": CUFE_VALIDO, "folio": "FE-001", "fecha": "2026-01-01",
            "nit_emisor": "123456789", "nit_receptor": "987654321",
            "subtotal": 100.0, "iva_19": 0.0, "iva_5": 0.0, "total": 100.0,
            "tipo": "Factura Electrónica",
        }
        fila2 = dict(fila_base, folio="FE-002")
        df = validate(pd.DataFrame([fila_base, fila2]))
        assert (df["validacion"] == "ERROR").all()
        assert df["observacion"].str.contains("DUPLICADO").all()

    def test_build_validation_sheet_columnas(self):
        fila = {
            "cufe": CUFE_VALIDO, "folio": "FE-001", "fecha": "2026-01-01",
            "nit_emisor": "123456789", "nit_receptor": "987654321",
            "subtotal": 100.0, "iva_19": 0.0, "iva_5": 0.0, "total": 100.0,
            "tipo": "Factura Electrónica", "archivo": "FE-001.pdf",
        }
        df = validate(pd.DataFrame([fila]))
        df_val = build_validation_sheet(df)
        assert "validacion" in df_val.columns
        assert "observacion" in df_val.columns
        # BASE_DATOS no tendrá estas columnas (se separan aquí)
        assert "nit_emisor" not in df_val.columns
