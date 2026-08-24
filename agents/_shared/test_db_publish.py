"""Tests para db_publish.py — usa una DB Postgres real de test (no mockeable fácilmente,
psycopg2 no tiene un equivalente directo a moto). Requiere DATABASE_URL apuntando a una
DB de test vacía o con las tablas de la migración 007 ya aplicadas."""
import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from _shared.db_publish import insert_lead, insert_novedad  # noqa: E402

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ, reason="requiere DATABASE_URL de una DB de test"
)


@pytest.fixture
def clean_tables():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("DELETE FROM novedades WHERE titulo LIKE 'TEST %'")
        cur.execute("DELETE FROM leads_comerciales WHERE empresa LIKE 'TEST %'")
    conn.commit()
    conn.close()
    yield


def test_insert_novedad(clean_tables):
    insert_novedad("dian", "TEST Resolución nueva", "Resumen de prueba", date(2026, 8, 23))

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("SELECT tipo, titulo, resumen FROM novedades WHERE titulo = 'TEST Resolución nueva'")
        row = cur.fetchone()
    conn.close()
    assert row == ("dian", "TEST Resolución nueva", "Resumen de prueba")


def test_insert_lead_dedups_by_empresa_ciudad(clean_tables):
    insert_lead(
        "TEST Restaurante XYZ", "restaurantes", "Medellín", "contacto@xyz.com", "https://x.com", date(2026, 8, 23)
    )
    insert_lead(
        "TEST Restaurante XYZ", "restaurantes", "Medellín", "otro@xyz.com", "https://y.com", date(2026, 8, 24)
    )

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM leads_comerciales WHERE empresa = 'TEST Restaurante XYZ'")
        count = cur.fetchone()[0]
    conn.close()
    assert count == 1  # la segunda inserción no duplicó — ON CONFLICT DO NOTHING
