"""Tests for services/processor.py DB persistence path (Task 6).

All tests run without a live database by patching db.database.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_fake_row():
    return {
        "tipo": "Factura Electrónica",
        "cufe": "a" * 96,
        "folio": "FE-001",
        "fecha": "2026-04-01",
        "nit_emisor": "900123456",
        "nombre_emisor": "Empresa S.A.",
        "nit_receptor": "800987654",
        "nombre_receptor": "Cliente S.A.",
        "subtotal": 1000.0,
        "base_iva_19": 1000.0,
        "iva_19": 190.0,
        "base_iva_5": 0.0,
        "iva_5": 0.0,
        "no_gravado": 0.0,
        "total": 1190.0,
        "retencion_fuente": 0.0,
        "fuente": "test.pdf",
    }


class TestProcesarDBPersistence:
    """procesar() must call insert_invoices_batch when org_id and db_available()."""

    def test_insert_called_when_org_id_and_db_available(self):
        """When org_id is set and db_available() returns True, insert must be called."""
        fake_row = _make_fake_row()

        with (
            patch("pipeline.extractor.extract_one", return_value=fake_row),
            patch("db.database.db_available", return_value=True),
            patch("db.database.get_existing_cufes", return_value=set()),
            patch("db.database.insert_invoices_batch", return_value=(1, 0)) as mock_insert,
        ):
            from services.processor import procesar
            import importlib, services.processor
            importlib.reload(services.processor)
            from services.processor import procesar as procesar_fresh

            resultado = procesar_fresh(
                [Path("fake.pdf")],
                org_id="org-uuid-1234",
            )

        mock_insert.assert_called_once()
        assert resultado.db_guardado is True
        assert resultado.db_nuevas == 1
        assert resultado.db_duplicadas == 0

    def test_insert_not_called_when_no_org_id(self):
        """When org_id is None, insert must NOT be called."""
        fake_row = _make_fake_row()

        with (
            patch("pipeline.extractor.extract_one", return_value=fake_row),
            patch("db.database.db_available", return_value=True),
            patch("db.database.insert_invoices_batch", return_value=(1, 0)) as mock_insert,
        ):
            from services.processor import procesar
            resultado = procesar([Path("fake.pdf")])

        mock_insert.assert_not_called()
        assert resultado.db_guardado is False

    def test_insert_not_called_when_db_unavailable(self):
        """When db_available() returns False, insert must NOT be called."""
        fake_row = _make_fake_row()

        with (
            patch("pipeline.extractor.extract_one", return_value=fake_row),
            patch("db.database.db_available", return_value=False),
            patch("db.database.insert_invoices_batch", return_value=(1, 0)) as mock_insert,
        ):
            from services.processor import procesar
            resultado = procesar([Path("fake.pdf")], org_id="org-uuid-1234")

        mock_insert.assert_not_called()
        assert resultado.db_guardado is False

    def test_db_error_does_not_raise(self):
        """If insert_invoices_batch raises, procesar() must still return a result."""
        fake_row = _make_fake_row()

        with (
            patch("pipeline.extractor.extract_one", return_value=fake_row),
            patch("db.database.db_available", return_value=True),
            patch("db.database.get_existing_cufes", return_value=set()),
            patch("db.database.insert_invoices_batch", side_effect=Exception("DB down")),
        ):
            from services.processor import procesar
            resultado = procesar([Path("fake.pdf")], org_id="org-uuid-1234")

        assert resultado.df_base is not None
        assert resultado.db_guardado is False
