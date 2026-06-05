"""Tests for Task 7 — procesar_exogenas() org_id + insert_exogenas_batch.

All tests run without a live database by patching db.database.
NOTE: procesar_exogenas signature has NO anio param — only org_id is added.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _fake_extract(path):
    return [{
        "archivo": Path(path).name,
        "tipo_cert": "renta",
        "razon_social": "ACME S.A.",
        "nit": "900111222",
        "dv": "3",
        "tipo_doc": "31",
        "concepto": "1303",
        "base": 1_000_000.0,
        "retencion": 60_000.0,
        "porcentaje": 6.0,
        "ciudad_retencion": "Bogotá",
        "direccion": "Calle 1 # 2-3",
        "primer_apellido": "",
        "segundo_apellido": "",
        "primer_nombre": "",
        "otros_nombres": "",
        "error": None,
        "anio": 2025,
    }]


class TestProcesarExogenasDB:
    """procesar_exogenas() with org_id must call insert_exogenas_batch."""

    def test_insert_called_when_org_id_and_db_available(self):
        """When org_id is provided and DB is up, insert_exogenas_batch must be called."""
        with (
            patch("services.processor_exogenas.extract_many", side_effect=_fake_extract),
            patch("services.processor_exogenas.buscar_municipio", return_value=("11", "001")),
            patch("db.database.db_available", return_value=True),
            patch("db.database.insert_exogenas_batch") as mock_insert,
        ):
            from services.processor_exogenas import procesar_exogenas

            resultado = procesar_exogenas([Path("cert1.pdf")], org_id="org-uuid-exo")

        mock_insert.assert_called_once()
        # First positional arg is df_1003
        call_kwargs = mock_insert.call_args
        assert call_kwargs.kwargs.get("org_id") == "org-uuid-exo" or call_kwargs.args[1] == "org-uuid-exo"

    def test_insert_not_called_when_no_org_id(self):
        """When org_id is None (default), insert must NOT be called."""
        with (
            patch("services.processor_exogenas.extract_many", side_effect=_fake_extract),
            patch("services.processor_exogenas.buscar_municipio", return_value=("11", "001")),
            patch("db.database.db_available", return_value=True),
            patch("db.database.insert_exogenas_batch") as mock_insert,
        ):
            from services.processor_exogenas import procesar_exogenas
            resultado = procesar_exogenas([Path("cert1.pdf")])

        mock_insert.assert_not_called()

    def test_insert_not_called_when_db_unavailable(self):
        """When db_available() returns False, insert must NOT be called."""
        with (
            patch("services.processor_exogenas.extract_many", side_effect=_fake_extract),
            patch("services.processor_exogenas.buscar_municipio", return_value=("11", "001")),
            patch("db.database.db_available", return_value=False),
            patch("db.database.insert_exogenas_batch") as mock_insert,
        ):
            from services.processor_exogenas import procesar_exogenas
            resultado = procesar_exogenas([Path("cert1.pdf")], org_id="org-uuid-exo")

        mock_insert.assert_not_called()

    def test_db_error_does_not_raise(self):
        """If insert_exogenas_batch raises, procesar_exogenas() must still return a result."""
        with (
            patch("services.processor_exogenas.extract_many", side_effect=_fake_extract),
            patch("services.processor_exogenas.buscar_municipio", return_value=("11", "001")),
            patch("db.database.db_available", return_value=True),
            patch("db.database.insert_exogenas_batch", side_effect=Exception("DB down")),
        ):
            from services.processor_exogenas import procesar_exogenas
            resultado = procesar_exogenas([Path("cert1.pdf")], org_id="org-uuid-exo")

        assert resultado is not None
        assert resultado.total_archivos == 1

    def test_signature_has_no_anio_param(self):
        """procesar_exogenas must NOT accept an 'anio' parameter."""
        import inspect
        from services.processor_exogenas import procesar_exogenas
        params = inspect.signature(procesar_exogenas).parameters
        assert "anio" not in params, "anio must NOT be a parameter of procesar_exogenas"
        assert "org_id" in params, "org_id must be a parameter of procesar_exogenas"
