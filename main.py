"""
Sistema de gestión de facturas electrónicas DIAN.

Uso:
    python main.py
    python main.py --carpeta C:/ruta/facturas --ingresos "2026-04:5000000"
    python main.py --workers 8
"""

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.extractor import extract_one
from pipeline.validator import validate, build_validation_sheet
from pipeline.prorateo import calcular_prorateo, calcular_prorateo_simple
from pipeline.excel_writer import write_excel

# ── Logging ────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"proceso_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

_file_handler   = logging.FileHandler(log_file, encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setLevel(logging.WARNING)   # stdout solo muestra warnings/errores

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_file_handler, _stream_handler],
)
logger = logging.getLogger(__name__)


def parse_ingresos(raw: str) -> tuple[dict, dict]:
    grav, excl = {}, {}
    if not raw:
        return grav, excl
    for parte in raw.split(","):
        parte = parte.strip()
        if ":" in parte:
            mes, val = parte.split(":", 1)
            grav[mes.strip()] = float(val.strip().replace(".", "").replace(",", "."))
    return grav, excl


def _resolver_archivos(carpeta: Path) -> list[Path]:
    """
    Escaneo recursivo con deduplicación: si existe par PDF+XML para el mismo
    documento, conserva solo el XML (más confiable). O(n) en un solo pase.
    """
    candidatos: dict[str, Path] = {}
    for p in carpeta.rglob("*"):
        if p.suffix.lower() not in (".pdf", ".xml", ".docx"):
            continue
        key = str(p.with_suffix("")).lower()
        existente = candidatos.get(key)
        # XML gana sobre PDF
        if existente is None or p.suffix.lower() == ".xml":
            candidatos[key] = p
    return sorted(candidatos.values())


def procesar(carpeta: Path, ingresos_raw: str = "", workers: int = 2) -> Path:
    archivos = _resolver_archivos(carpeta)
    total = len(archivos)
    if not total:
        logger.warning("No se encontraron PDF/XML en %s", carpeta)
        sys.exit(0)

    print(f"Procesando {total} documentos con {workers} workers...")

    filas: list[dict] = []
    errores_extraccion = 0

    # Submitimos en lotes de 20 para no acumular todos los futures en RAM
    BATCH = 20
    done = 0
    for batch_start in range(0, total, BATCH):
        lote = archivos[batch_start:batch_start + BATCH]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(extract_one, p): p for p in lote}
            for future in as_completed(futures):
                done += 1
                row = future.result()
                if row:
                    filas.append(row)
                else:
                    errores_extraccion += 1
                if done % 50 == 0 or done == total:
                    pct = 100 * done // total
                    print(f"  {done}/{total} ({pct}%) — {errores_extraccion} errores", flush=True)

    if not filas:
        logger.error("No se extrajeron datos.")
        sys.exit(1)

    df = pd.DataFrame(filas)
    df = validate(df)

    n_err = int((df["validacion"] == "ERROR").sum())
    n_ok  = len(df) - n_err
    print(f"Validacion: {n_ok} OK | {n_err} ERROR de cuadre contable")
    logger.info("Validacion: %d OK | %d ERROR", n_ok, n_err)

    df_val = build_validation_sheet(df)

    grav, excl = parse_ingresos(ingresos_raw)
    if grav:
        df_pror = calcular_prorateo(df, grav, excl)
    else:
        df_pror = calcular_prorateo_simple(df)
        logger.warning("Ingresos no proporcionados — prorrateo al 100%%")

    cols_base = [
        "tipo", "cufe", "folio", "fecha",
        "nit_emisor", "nombre_emisor", "nit_receptor", "nombre_receptor",
        "subtotal", "base_iva_19", "iva_19", "base_iva_5", "iva_5",
        "no_gravado", "total", "retencion_fuente", "fuente",
    ]
    df_base = df[[c for c in cols_base if c in df.columns]]

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"facturas_{stamp}.xlsx"

    write_excel(df_base, df_val, df_pror, out_path)
    logger.info("Excel generado: %s", out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Procesador DIAN de facturas electronicas")
    parser.add_argument("--carpeta",  default="facturas")
    parser.add_argument("--ingresos", default="")
    parser.add_argument(
        "--workers", type=int,
        default=2,
        help="Hilos paralelos para extraccion (default: 2 — limitado por RAM, no por CPU)",
    )
    args = parser.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.exists():
        print(f"ERROR: Carpeta no encontrada: {carpeta}")
        sys.exit(1)

    out = procesar(carpeta, args.ingresos, args.workers)
    print(f"\nListo: {out}")


if __name__ == "__main__":
    main()
