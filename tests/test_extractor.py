"""
Pruebas unitarias para extractor.py.
Cubre funciones puras (sin I/O real) y extracción con texto sintético.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipeline.extractor import (
    _clean_number,
    _parse_date,
    _date_from_folder,
    _detect_doc_type,
    _calc_retencion,
    _split_iva_bases,
    _search_money_near,
    _AUTORRETENEDORES,
    extract_pdf,
)


# ─────────────────────────────────────────────
# _clean_number — formato colombiano vs americano
# ─────────────────────────────────────────────

class TestCleanNumber:
    def test_colombiano_miles_punto(self):
        assert _clean_number("1.234.567,89") == 1_234_567.89

    def test_colombiano_sin_centavos(self):
        assert _clean_number("291.400,00") == 291_400.0

    def test_americano_miles_coma(self):
        assert _clean_number("1,234,567.89") == 1_234_567.89

    def test_entero_simple(self):
        assert _clean_number("715909") == 715_909.0

    def test_solo_coma_decimal(self):
        assert _clean_number("114,64") == 114.64

    def test_vacio(self):
        assert _clean_number("") == 0.0

    def test_con_espacio(self):
        assert _clean_number(" 100.000,00 ") == 100_000.0


# ─────────────────────────────────────────────
# _parse_date — normalización de fechas
# ─────────────────────────────────────────────

class TestParseDate:
    def test_iso(self):
        assert _parse_date("2026-02-23") == "2026-02-23"

    def test_colombiano_barras(self):
        assert _parse_date("23/02/2026") == "2026-02-23"

    def test_colombiano_guiones(self):
        assert _parse_date("16-02-2026") == "2026-02-16"

    def test_invalido_pasa_sin_crash(self):
        result = _parse_date("no-es-fecha")
        assert isinstance(result, str)


# ─────────────────────────────────────────────
# _date_from_folder — fecha desde nombre de carpeta
# ─────────────────────────────────────────────

class TestDateFromFolder:
    def test_formato_yyyy_mm(self, tmp_path):
        p = (tmp_path / "2026-03" / "FE-001.pdf")
        p.parent.mkdir()
        assert _date_from_folder(p) == "2026-03-01"

    def test_formato_yyyy_mm_dd(self, tmp_path):
        p = (tmp_path / "2026-03-15" / "FE-001.pdf")
        p.parent.mkdir()
        assert _date_from_folder(p) == "2026-03-15"

    def test_sin_fecha_en_carpeta(self, tmp_path):
        p = tmp_path / "FE-001.pdf"
        assert _date_from_folder(p) == ""

    def test_carpeta_no_fecha(self, tmp_path):
        p = (tmp_path / "facturas-varios" / "FE-001.pdf")
        p.parent.mkdir()
        assert _date_from_folder(p) == ""


# ─────────────────────────────────────────────
# _detect_doc_type
# ─────────────────────────────────────────────

class TestDetectDocType:
    def test_nota_credito_texto(self):
        assert _detect_doc_type("nota credito electronica dian", "") == "Nota Crédito"

    def test_nota_credito_nombre_archivo(self):
        assert _detect_doc_type("", "NC-001.pdf") == "Nota Crédito"

    def test_mandato(self):
        assert _detect_doc_type("mandato de cobro autopistas", "") == "Mandato/Peaje"

    def test_peaje(self):
        assert _detect_doc_type("peaje ruta del sol", "") == "Mandato/Peaje"

    def test_documento_soporte(self):
        assert _detect_doc_type("documento soporte", "") == "Documento Soporte"

    def test_factura_default(self):
        assert _detect_doc_type("factura electronica de venta", "") == "Factura Electrónica"


# ─────────────────────────────────────────────
# _calc_retencion
# ─────────────────────────────────────────────

class TestCalcRetencion:
    def test_normal_2_5_pct(self):
        assert _calc_retencion(291_400.0, "899999143") == 7_285.0

    def test_retencion_eb_33355(self):
        # EB-33355 real: 601603.36 × 2.5% = 15040.08
        assert _calc_retencion(601_603.36, "901073241") == pytest.approx(15_040.08, abs=0.01)

    def test_autorretenedor_cero(self):
        if not _AUTORRETENEDORES:
            pytest.skip("autorretenedores.txt no disponible")
        nit_auto = next(iter(_AUTORRETENEDORES))
        assert _calc_retencion(1_000_000.0, nit_auto) == 0.0

    def test_bavaria_autorretenedor(self):
        # BAVARIA S.A. NIT 860005224 — autorretenedor histórico DIAN
        if "860005224" not in _AUTORRETENEDORES:
            pytest.skip("Bavaria no en el listado cargado")
        assert _calc_retencion(500_000.0, "860005224") == 0.0

    def test_base_cero(self):
        assert _calc_retencion(0.0, "123456789") == 0.0


# ─────────────────────────────────────────────
# _split_iva_bases
# ─────────────────────────────────────────────

class TestSplitIvaBases:
    def test_todo_no_gravado(self):
        b19, b5, no_grav = _split_iva_bases(291_400.0, 0.0, 0.0)
        assert b19 == 0.0
        assert b5 == 0.0
        assert no_grav == 291_400.0

    def test_todo_gravado_19(self):
        b19, b5, no_grav = _split_iva_bases(601_603.36, 114_305.64, 0.0)
        assert b19 == pytest.approx(601_603.36, abs=1.0)
        assert no_grav == 0.0

    def test_mixto_19_y_no_gravado(self):
        # 100k gravado al 19%, 100k no gravado → subtotal 200k, IVA 19k
        b19, b5, no_grav = _split_iva_bases(200_000.0, 19_000.0, 0.0)
        assert b19 == pytest.approx(100_000.0, abs=1.0)
        assert no_grav == pytest.approx(100_000.0, abs=1.0)

    def test_iva_5(self):
        b19, b5, no_grav = _split_iva_bases(100_000.0, 0.0, 5_000.0)
        assert b19 == 0.0
        assert b5 == pytest.approx(100_000.0, abs=1.0)
        assert no_grav == 0.0

    def test_base_direct_xml(self):
        # XML provee TaxableAmount exacto
        b19, b5, no_grav = _split_iva_bases(
            601_603.36, 114_305.64, 0.0,
            base19_direct=601_603.36,
        )
        assert b19 == 601_603.36
        assert no_grav == 0.0

    def test_no_genera_negativos(self):
        # Si redondeo hace que base > subtotal, no_gravado queda en 0
        b19, b5, no_grav = _split_iva_bases(100.0, 19.5, 0.0)
        assert no_grav >= 0.0


# ─────────────────────────────────────────────
# _search_money_near — regex de montos
# ─────────────────────────────────────────────

class TestSearchMoneyNear:
    def test_total_bruto_factura(self):
        text = "Total Bruto Factura 601.603,36"
        assert _search_money_near(text, "Total Bruto Factura") == pytest.approx(601_603.36)

    def test_total_con_espacios_unicode(self):
        # Caso real: "Total factura (=) ㅤㅤ COP $ 1.191.999,83"
        text = "Total factura (=) ㅤㅤㅤ COP $ 1.191.999,83"
        assert _search_money_near(text, "Total factura") == pytest.approx(1_191_999.83)

    def test_iva_line_start_evita_calle(self):
        # Bug histórico: "Responsabilidad tributaria: 01 - IVA Dirección: CALLE 26"
        # capturaba el número de calle. Con line_start=True no debe ocurrir.
        text = (
            "Responsabilidad tributaria: 01 - IVA Dirección: AVENIDA CALLE 26 # 103\n"
            "IVA 0,00 IVA 0,00"
        )
        assert _search_money_near(text, "IVA", line_start=True) == 0.0

    def test_iva_line_start_captura_totales(self):
        text = (
            "Responsabilidad tributaria: 01 - IVA Dirección: CALLE 33\n"
            "IVA IVA 114.305,64"
        )
        assert _search_money_near(text, "IVA", line_start=True) == pytest.approx(114_305.64)

    def test_no_match_retorna_cero(self):
        assert _search_money_near("texto sin etiqueta", "Total Bruto Factura") == 0.0

    def test_subtotal_antes_de_descuentos_no_se_usa(self):
        # "Subtotal" es ANTES de descuentos; "Total Bruto Factura" tiene prioridad
        text = "Subtotal 664.033,61\nTotal Bruto Factura 601.603,36"
        assert _search_money_near(text, "Total Bruto Factura") == pytest.approx(601_603.36)


# ─────────────────────────────────────────────
# extract_pdf — con texto sintético mockeado
# ─────────────────────────────────────────────

TEXTO_FACTURA_DIAN = """\
FACTURA ELECTRÓNICA DE VENTA
Código Único de Factura - CUFE :
{cufe}
Número de Factura: FE-999 Forma de pago: Contado
Fecha de Emisión: 15/03/2026
Razón Social: EMPRESA DEMO SAS
Nit del Emisor: 900100200
Nombre o Razón Social: CLIENTE EJEMPLO LTDA
Número Documento: 800500600
Responsabilidad tributaria: 01 - IVA Dirección: CALLE 10 # 20-30
Subtotal 1.000.000,00
Total Bruto Factura 950.000,00
IVA IVA 180.500,00
Total factura (=) ㅤㅤ COP $ 1.130.500,00
""".format(cufe="a" * 96)


def _mock_pdf(text: str):
    """Crea un mock de pdfplumber.open que devuelve text."""
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


class TestExtractPdf:
    def test_campos_basicos(self, tmp_path):
        p = tmp_path / "FE-999.pdf"
        p.write_bytes(b"")
        with patch("pipeline.extractor.pdfplumber.open", return_value=_mock_pdf(TEXTO_FACTURA_DIAN)):
            row = extract_pdf(p)

        assert row["folio"] == "FE-999"
        assert row["nit_emisor"] == "900100200"
        assert row["nit_receptor"] == "800500600"
        assert row["fecha"] == "2026-03-15"
        assert row["fuente"] == "PDF"

    def test_montos_extraidos(self, tmp_path):
        p = tmp_path / "FE-999.pdf"
        p.write_bytes(b"")
        with patch("pipeline.extractor.pdfplumber.open", return_value=_mock_pdf(TEXTO_FACTURA_DIAN)):
            row = extract_pdf(p)

        assert row["subtotal"] == pytest.approx(950_000.0, abs=1)
        assert row["iva_19"] == pytest.approx(180_500.0, abs=1)
        assert row["total"] == pytest.approx(1_130_500.0, abs=1)

    def test_retencion_calculada(self, tmp_path):
        p = tmp_path / "FE-999.pdf"
        p.write_bytes(b"")
        with patch("pipeline.extractor.pdfplumber.open", return_value=_mock_pdf(TEXTO_FACTURA_DIAN)):
            row = extract_pdf(p)
        # 950_000 × 2.5% = 23_750
        assert row["retencion_fuente"] == pytest.approx(23_750.0, abs=1)

    def test_nota_credito_valores_negativos(self, tmp_path):
        texto_nc = TEXTO_FACTURA_DIAN.replace(
            "FACTURA ELECTRÓNICA DE VENTA",
            "NOTA CRÉDITO ELECTRÓNICA"
        )
        p = tmp_path / "NC-001.pdf"
        p.write_bytes(b"")
        with patch("pipeline.extractor.pdfplumber.open", return_value=_mock_pdf(texto_nc)):
            row = extract_pdf(p)

        assert row["tipo"] == "Nota Crédito"
        assert row["subtotal"] < 0
        assert row["total"] < 0

    def test_cufe_capturado(self, tmp_path):
        p = tmp_path / "FE-999.pdf"
        p.write_bytes(b"")
        with patch("pipeline.extractor.pdfplumber.open", return_value=_mock_pdf(TEXTO_FACTURA_DIAN)):
            row = extract_pdf(p)
        assert row["cufe"] == "a" * 96
