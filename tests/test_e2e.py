"""
Pruebas end-to-end — requieren los PDFs reales en facturas/.
Se saltan automáticamente si los archivos no están disponibles
(están en .gitignore, cada desarrollador los descarga de la DIAN).
"""

import shutil
import pytest
import pandas as pd
from pathlib import Path

from pipeline.extractor import extract_one
from main import _resolver_archivos, procesar

# ── Localización de PDFs de prueba ────────────────────────────────────────────
_FACTURAS = Path(__file__).parent.parent / "facturas"
_STK = next(_FACTURAS.glob("3e7b57a7*.pdf"), None)
_EB  = next(_FACTURAS.glob("7732b1b3*.pdf"), None)

_pdfs_disponibles = pytest.mark.skipif(
    _STK is None or _EB is None,
    reason="PDFs de prueba no disponibles (descarga de la DIAN requerida)",
)


# ─────────────────────────────────────────────
# Extracción individual — valores reales conocidos
# ─────────────────────────────────────────────

@_pdfs_disponibles
class TestExtraccionSTK602558:
    """SATENA STK-602558: servicio aéreo sin IVA, todo no gravado."""

    def test_folio(self):
        assert extract_one(_STK)["folio"] == "STK-602558"

    def test_nit_emisor(self):
        assert extract_one(_STK)["nit_emisor"] == "899999143"

    def test_nombre_emisor(self):
        nombre = extract_one(_STK)["nombre_emisor"]
        assert "AEREO" in nombre.upper() or "SATENA" in nombre.upper()

    def test_nit_receptor(self):
        assert extract_one(_STK)["nit_receptor"] == "902012620"

    def test_fecha(self):
        assert extract_one(_STK)["fecha"] == "2026-02-23"

    def test_subtotal(self):
        assert extract_one(_STK)["subtotal"] == pytest.approx(291_400.0, abs=1)

    def test_iva_cero(self):
        row = extract_one(_STK)
        assert row["iva_19"] == 0.0
        assert row["iva_5"] == 0.0

    def test_no_gravado_igual_subtotal(self):
        row = extract_one(_STK)
        assert row["no_gravado"] == pytest.approx(291_400.0, abs=1)

    def test_total(self):
        assert extract_one(_STK)["total"] == pytest.approx(291_400.0, abs=1)

    def test_retencion_2_5_pct(self):
        # 291400 × 2.5% = 7285
        assert extract_one(_STK)["retencion_fuente"] == pytest.approx(7_285.0, abs=1)

    def test_cufe_96_hex(self):
        cufe = extract_one(_STK)["cufe"]
        assert len(cufe) == 96
        assert all(c in "0123456789abcdef" for c in cufe.lower())


@_pdfs_disponibles
class TestExtraccionEB33355:
    """AGROTECNICO EB-33355: factura con IVA 19% sobre toda la base."""

    def test_folio(self):
        assert extract_one(_EB)["folio"] == "EB-33355"

    def test_nit_emisor(self):
        assert extract_one(_EB)["nit_emisor"] == "901073241"

    def test_fecha(self):
        assert extract_one(_EB)["fecha"] == "2026-02-16"

    def test_subtotal(self):
        assert extract_one(_EB)["subtotal"] == pytest.approx(601_603.36, abs=1)

    def test_iva_19(self):
        assert extract_one(_EB)["iva_19"] == pytest.approx(114_305.64, abs=1)

    def test_base_iva_19_igual_subtotal(self):
        row = extract_one(_EB)
        assert row["base_iva_19"] == pytest.approx(601_603.36, abs=1)

    def test_no_gravado_cero(self):
        assert extract_one(_EB)["no_gravado"] == 0.0

    def test_total(self):
        assert extract_one(_EB)["total"] == pytest.approx(715_909.0, abs=1)

    def test_retencion_coincide_con_pdf(self):
        # El PDF informa "Rete fuente 15.040,08" — debe coincidir
        assert extract_one(_EB)["retencion_fuente"] == pytest.approx(15_040.08, abs=1)


# ─────────────────────────────────────────────
# _resolver_archivos — deduplicación PDF/XML
# ─────────────────────────────────────────────

class TestResolverArchivos:
    def test_solo_pdf(self, tmp_path):
        (tmp_path / "FE-001.pdf").write_bytes(b"")
        archivos = _resolver_archivos(tmp_path)
        assert len(archivos) == 1
        assert archivos[0].suffix == ".pdf"

    def test_par_pdf_xml_queda_xml(self, tmp_path):
        (tmp_path / "FE-001.pdf").write_bytes(b"")
        (tmp_path / "FE-001.xml").write_bytes(b"")
        archivos = _resolver_archivos(tmp_path)
        assert len(archivos) == 1
        assert archivos[0].suffix == ".xml"

    def test_mismo_nombre_subcarpetas_no_se_deduplicar(self, tmp_path):
        (tmp_path / "2026-03").mkdir()
        (tmp_path / "2026-04").mkdir()
        (tmp_path / "2026-03" / "FE-001.pdf").write_bytes(b"")
        (tmp_path / "2026-04" / "FE-001.pdf").write_bytes(b"")
        archivos = _resolver_archivos(tmp_path)
        assert len(archivos) == 2

    def test_ignora_extensiones_no_validas(self, tmp_path):
        (tmp_path / "FE-001.pdf").write_bytes(b"")
        (tmp_path / "FE-001.xlsx").write_bytes(b"")
        (tmp_path / "notas.txt").write_bytes(b"")
        archivos = _resolver_archivos(tmp_path)
        assert len(archivos) == 1

    def test_recursivo_subcarpetas(self, tmp_path):
        sub = tmp_path / "2026-03"
        sub.mkdir()
        (tmp_path / "FE-001.pdf").write_bytes(b"")
        (sub / "FE-002.pdf").write_bytes(b"")
        archivos = _resolver_archivos(tmp_path)
        assert len(archivos) == 2

    def test_carpeta_vacia(self, tmp_path):
        archivos = _resolver_archivos(tmp_path)
        assert archivos == []


# ─────────────────────────────────────────────
# Pipeline completo — Excel con 3 hojas
# ─────────────────────────────────────────────

@_pdfs_disponibles
class TestPipelineCompleto:
    def test_genera_excel_con_3_hojas(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        carpeta = tmp_path / "facturas"
        carpeta.mkdir()
        shutil.copy(_STK, carpeta / _STK.name)
        shutil.copy(_EB,  carpeta / _EB.name)

        out = procesar(carpeta, workers=2)

        assert out.exists()
        xl = pd.ExcelFile(out)
        assert set(xl.sheet_names) == {"BASE_DATOS", "VALIDACION", "PRORRATEO_IVA"}

    def test_base_datos_columnas_correctas(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        carpeta = tmp_path / "facturas"
        carpeta.mkdir()
        shutil.copy(_STK, carpeta / _STK.name)
        shutil.copy(_EB,  carpeta / _EB.name)

        out = procesar(carpeta, workers=2)
        df = pd.read_excel(out, sheet_name="BASE_DATOS")

        esperadas = {
            "tipo", "cufe", "folio", "fecha",
            "nit_emisor", "nombre_emisor", "nit_receptor", "nombre_receptor",
            "subtotal", "base_iva_19", "iva_19", "base_iva_5", "iva_5",
            "no_gravado", "total", "retencion_fuente", "fuente",
        }
        assert esperadas.issubset(set(df.columns))
        assert "archivo" not in df.columns      # eliminada por requerimiento
        assert "validacion" not in df.columns   # solo en hoja VALIDACION

    def test_validacion_ok_ambas_facturas(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        carpeta = tmp_path / "facturas"
        carpeta.mkdir()
        shutil.copy(_STK, carpeta / _STK.name)
        shutil.copy(_EB,  carpeta / _EB.name)

        out = procesar(carpeta, workers=2)
        df_val = pd.read_excel(out, sheet_name="VALIDACION")
        assert (df_val["validacion"] == "OK").all(), df_val[["folio", "observacion"]].to_string()

    def test_prorrateo_tiene_columnas_requeridas(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        carpeta = tmp_path / "facturas"
        carpeta.mkdir()
        shutil.copy(_STK, carpeta / _STK.name)

        out = procesar(carpeta, workers=1)
        df_pror = pd.read_excel(out, sheet_name="PRORRATEO_IVA")

        for col in ("mes", "iva_total", "iva_descontable", "iva_no_descontable", "pct_prorateo"):
            assert col in df_pror.columns

    def test_dos_facturas_procesadas(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        carpeta = tmp_path / "facturas"
        carpeta.mkdir()
        shutil.copy(_STK, carpeta / _STK.name)
        shutil.copy(_EB,  carpeta / _EB.name)

        out = procesar(carpeta, workers=2)
        df = pd.read_excel(out, sheet_name="BASE_DATOS")
        assert len(df) == 2
        folios = set(df["folio"].tolist())
        assert "STK-602558" in folios
        assert "EB-33355" in folios
