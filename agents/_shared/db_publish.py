"""agents/_shared/db_publish.py — Escritura directa a Postgres (Neon) para los publish.py de
cada agente. Usa psycopg2 crudo (no SQLAlchemy/db.database.py del API) porque estos scripts
corren standalone en GitHub Actions, no como parte de la app FastAPI.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg2


def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está seteado")
    return psycopg2.connect(url)


def insert_novedad(tipo: str, titulo: str, resumen: str, fecha_generado: date) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO novedades (tipo, titulo, resumen, fecha_generado) "
                "VALUES (%s, %s, %s, %s)",
                (tipo, titulo, resumen, fecha_generado),
            )
        conn.commit()
    finally:
        conn.close()


def insert_lead(
    empresa: str, sector: str, ciudad: str, contacto: str, fuente_url: str, fecha_generado: date
) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO leads_comerciales (empresa, sector, ciudad, contacto, fuente_url, fecha_generado) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (empresa, ciudad) DO NOTHING",
                (empresa, sector, ciudad, contacto, fuente_url, fecha_generado),
            )
        conn.commit()
    finally:
        conn.close()
