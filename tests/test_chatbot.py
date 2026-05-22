"""Tests para chatbot.py — no llaman a la API real de Claude."""
import pandas as pd
import pytest
from chatbot import (
    _tool_consultar_iva_mes,
    _tool_top_proveedores,
    _tool_buscar_factura,
    _tool_resumen_errores,
    _tool_resumen_general,
)


@pytest.fixture
def df_mock():
    return pd.DataFrame([
        {
            "tipo": "Factura Electrónica", "folio": "FE-001", "fecha": "2026-03-15",
            "nit_emisor": "900123456", "nombre_emisor": "Proveedor Alpha S.A.S",
            "nit_receptor": "901050311", "nombre_receptor": "Mi Empresa",
            "subtotal": 1_000_000, "base_iva_19": 1_000_000, "iva_19": 190_000,
            "base_iva_5": 0, "iva_5": 0, "no_gravado": 0,
            "total": 1_190_000, "retencion_fuente": 25_000, "fuente": "XML",
            "validacion": "OK", "observacion": "",
        },
        {
            "tipo": "Factura Electrónica", "folio": "FE-002", "fecha": "2026-03-20",
            "nit_emisor": "800987654", "nombre_emisor": "Proveedor Beta Ltda",
            "nit_receptor": "901050311", "nombre_receptor": "Mi Empresa",
            "subtotal": 2_000_000, "base_iva_19": 2_000_000, "iva_19": 380_000,
            "base_iva_5": 0, "iva_5": 0, "no_gravado": 0,
            "total": 2_380_000, "retencion_fuente": 50_000, "fuente": "PDF",
            "validacion": "ERROR", "observacion": "CUFE vacío",
        },
        {
            "tipo": "Mandato/Peaje", "folio": "MAN-001", "fecha": "2026-04-05",
            "nit_emisor": "700111222", "nombre_emisor": "Concesión Vial",
            "nit_receptor": "901050311", "nombre_receptor": "Mi Empresa",
            "subtotal": 500_000, "base_iva_19": 0, "iva_19": 0,
            "base_iva_5": 0, "iva_5": 0, "no_gravado": 500_000,
            "total": 500_000, "retencion_fuente": 0, "fuente": "PDF",
            "validacion": "OK", "observacion": "",
        },
    ])


def test_consultar_iva_mes_existente(df_mock):
    result = _tool_consultar_iva_mes(df_mock, "2026-03")
    assert "2026-03" in result
    assert "570" in result.replace(".", "").replace(",", "")


def test_consultar_iva_mes_sin_datos(df_mock):
    result = _tool_consultar_iva_mes(df_mock, "2025-01")
    assert "no hay" in result.lower()


def test_top_proveedores(df_mock):
    result = _tool_top_proveedores(df_mock, n=2)
    assert "Proveedor Beta" in result
    assert "Proveedor Alpha" in result


def test_top_proveedores_mandato_excluido(df_mock):
    result = _tool_top_proveedores(df_mock, n=10)
    # Beta tiene mayor subtotal (2M) → debe aparecer primero
    assert result.index("Beta") < result.index("Alpha")


def test_buscar_factura_por_folio(df_mock):
    result = _tool_buscar_factura(df_mock, "FE-001")
    assert "FE-001" in result
    assert "Proveedor Alpha" in result


def test_buscar_factura_por_nit(df_mock):
    result = _tool_buscar_factura(df_mock, "800987654")
    assert "FE-002" in result


def test_buscar_factura_sin_resultados(df_mock):
    result = _tool_buscar_factura(df_mock, "FE-999")
    assert "no se encontraron" in result.lower()


def test_resumen_errores(df_mock):
    result = _tool_resumen_errores(df_mock)
    assert "FE-002" in result
    assert "CUFE" in result


def test_resumen_errores_sin_errores():
    df = pd.DataFrame([{
        "tipo": "Factura Electrónica", "folio": "FE-OK", "fecha": "2026-03-01",
        "nit_emisor": "900000001", "nombre_emisor": "Ok S.A.S",
        "subtotal": 100_000, "iva_19": 19_000, "iva_5": 0, "total": 119_000,
        "validacion": "OK", "observacion": "",
    }])
    result = _tool_resumen_errores(df)
    assert "sin errores" in result.lower() or "todas las facturas" in result.lower()


def test_resumen_general(df_mock):
    result = _tool_resumen_general(df_mock)
    assert "3" in result
    assert "ERROR" in result or "error" in result.lower()


def test_resumen_general_totales(df_mock):
    result = _tool_resumen_general(df_mock)
    # total = 1_190_000 + 2_380_000 + 500_000 = 4_070_000
    assert "4,070,000" in result or "4.070.000" in result or "4070000" in result.replace(",", "").replace(".", "")
