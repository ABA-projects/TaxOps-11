"""Orquestación UI-agnóstica para procesamiento de exógenas (Formato 1003)."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

from exogenas.extractor import extract_many
from exogenas.municipios import buscar_municipio


@dataclass
class ResultadoExogenas:
    df_detalle:      pd.DataFrame
    df_1003:         pd.DataFrame
    total_archivos:  int
    errores:         int
    ica_excluidos:   int
    advertencias:    list[str] = field(default_factory=list)


def _agregar(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por (nit, concepto), suma base y retención."""
    df_clean = df[
        (df["concepto"] != "ICA") &
        (df["nit"].fillna("").astype(str).str.strip() != "") &
        (df["concepto"].fillna("").astype(str).str.strip() != "") &
        (df["base"].fillna(0) > 0)
    ].copy()
    if df_clean.empty:
        return pd.DataFrame(columns=[
            "concepto","tipo_doc","nit","dv","primer_apellido","segundo_apellido",
            "primer_nombre","otros_nombres","razon_social","direccion",
            "cod_dpto","cod_mpio","base","retencion","porcentaje",
        ])

    agg = (
        df_clean
        .groupby(["nit", "concepto"], as_index=False)
        .agg(
            razon_social     =("razon_social", "first"),
            dv               =("dv", "first"),
            tipo_doc         =("tipo_doc", "first"),
            primer_apellido  =("primer_apellido", "first"),
            segundo_apellido =("segundo_apellido", "first"),
            primer_nombre    =("primer_nombre", "first"),
            otros_nombres    =("otros_nombres", "first"),
            direccion        =("direccion", "first"),
            ciudad_retencion =("ciudad_retencion", "first"),
            cod_dpto         =("cod_dpto", "first"),
            cod_mpio         =("cod_mpio", "first"),
            base             =("base", "sum"),
            retencion        =("retencion", "sum"),
            porcentaje       =("porcentaje", "first"),
        )
    )

    # Para tipo_doc=31 limpiar campos de persona natural y viceversa
    mask_31 = agg["tipo_doc"] == "31"
    for col in ("primer_apellido", "segundo_apellido", "primer_nombre", "otros_nombres"):
        agg.loc[mask_31, col] = ""
    agg.loc[~mask_31, "razon_social"] = ""

    col_order = [
        "concepto","tipo_doc","nit","dv","primer_apellido","segundo_apellido",
        "primer_nombre","otros_nombres","razon_social","direccion",
        "ciudad_retencion","cod_dpto","cod_mpio","base","retencion","porcentaje",
    ]
    return agg[col_order]


def procesar_exogenas(
    paths: list[Path],
    on_progress: Callable[[int, int, str], None] | None = None,
    org_id: str | None = None,
    workers: int = 3,
) -> ResultadoExogenas:
    """
    Procesa una lista de certificados de retención PDF.
    Retorna ResultadoExogenas con DataFrames listos para UI y Excel.

    Args:
        paths: Lista de rutas a procesar.
        on_progress: Callback opcional (i, total, nombre) para reportar progreso.
        org_id: UUID de organización. Si se pasa, persiste en PostgreSQL.
        workers: Número de archivos a procesar en paralelo.
    """
    total = len(paths)
    shared: dict = {"filas": [], "errores": 0, "advertencias": [], "done": 0}
    lock = threading.Lock()

    def _process_one(p: Path) -> None:
        import time
        local_rows: list[dict] = []
        local_warn: list[str] = []
        local_err = 0
        t0 = time.time()
        try:
            rows = extract_many(p)
            elapsed = time.time() - t0
            for row in rows:
                row["_archivo"] = Path(p).name
                if row.get("error"):
                    local_err += 1
                    local_warn.append(f"⚠️ {Path(p).name}: {row['error']}")
                local_rows.append(row)
            if elapsed > 3:
                fuente = rows[0].get("fuente", "?") if rows else "?"
                escaneado = rows[0].get("es_escaneado", False) if rows else False
                local_warn.append(
                    f"⏱️ {Path(p).name}: {elapsed:.1f}s "
                    f"[{'OCR' if escaneado or fuente == 'IMAGEN' else fuente}]"
                )
        except Exception as e:
            elapsed = time.time() - t0
            local_err = 1
            local_warn = [f"❌ {Path(p).name}: {e} ({elapsed:.1f}s)"]
        with lock:
            shared["filas"].extend(local_rows)
            shared["errores"] += local_err
            shared["advertencias"].extend(local_warn)
            shared["done"] += 1
            if on_progress:
                on_progress(shared["done"], total, Path(p).name)

    effective_workers = min(workers, total) if total > 1 else 1
    if effective_workers > 1:
        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
            list(pool.map(_process_one, paths))
    else:
        for p in paths:
            _process_one(p)

    filas: list[dict] = shared["filas"]
    errores: int = shared["errores"]
    advertencias: list[str] = shared["advertencias"]

    if not filas:
        return ResultadoExogenas(
            df_detalle=pd.DataFrame(),
            df_1003=pd.DataFrame(),
            total_archivos=len(paths),
            errores=errores,
            ica_excluidos=0,
            advertencias=advertencias,
        )

    df = pd.DataFrame(filas)

    # Resolver códigos de municipio
    def _resolve_mpio(ciudad: str) -> pd.Series:
        dpto, mpio = buscar_municipio(str(ciudad))
        return pd.Series({"cod_dpto": dpto, "cod_mpio": mpio})

    mpio_df = df["ciudad_retencion"].apply(_resolve_mpio)
    df["cod_dpto"] = mpio_df["cod_dpto"]
    df["cod_mpio"] = mpio_df["cod_mpio"]

    ica_count = int((df["concepto"] == "ICA").sum())

    # Detectar filas que serán excluidas del Formato 1003 por datos incompletos
    mask_incompletas = (
        (df["concepto"].fillna("").astype(str).str.strip() == "") |
        (df["nit"].fillna("").astype(str).str.strip() == "") |
        (df["base"].fillna(0) <= 0)
    ) & (df["concepto"].fillna("") != "ICA")
    df_incompletas = df[mask_incompletas]
    if not df_incompletas.empty:
        for archivo, grupo in df_incompletas.groupby("_archivo"):
            for _, fila in grupo.iterrows():
                motivos = []
                if not str(fila.get("nit", "")).strip():
                    motivos.append("NIT vacío")
                if not str(fila.get("concepto", "")).strip():
                    motivos.append("concepto vacío")
                if not (fila.get("base") or 0) > 0:
                    motivos.append("base=0")
                advertencias.append(
                    f"⚠️ {archivo}: fila excluida del Formato 1003 "
                    f"({', '.join(motivos)}) — "
                    f"retenedor: '{fila.get('razon_social','') or fila.get('nit','') or '?'}'"
                )

    df_1003 = _agregar(df)

    # Advertir filas sin municipio detectado
    sin_mpio = df_1003[df_1003["cod_dpto"] == ""]
    for _, row in sin_mpio.iterrows():
        advertencias.append(
            f"ℹ️ No se encontró código DIAN para ciudad '{row.get('ciudad_retencion','')}' "
            f"({row.get('razon_social','')}). Completa manualmente."
        )

    # ── Persistir en PostgreSQL ───────────────────────────────────────────────
    if org_id and not df_1003.empty:
        try:
            from db.database import insert_exogenas_batch, db_available
            if db_available():
                insert_exogenas_batch(df_1003, org_id)
        except Exception:
            pass

    return ResultadoExogenas(
        df_detalle=df,
        df_1003=df_1003,
        total_archivos=len(paths),
        errores=errores,
        ica_excluidos=ica_count,
        advertencias=advertencias,
    )
