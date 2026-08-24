"""agents/contabilidad/vencimientos-tributarios/publish.py — Extrae el bloque JSON del reporte,
lo valida, y hace merge por id contra el calendario ya existente en S3 (no reemplaza la lista
completa — preserva eventos curados a mano o de otras fuentes)."""
import json
import os
import re
import sys
from pathlib import Path

import boto3

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))

_JSON_BLOCK = re.compile(r"```json\s*(\[.*?\])\s*```", re.DOTALL)
# Mismo bucket/key que usa api/routers/calendario.py (Settings.S3_BUCKET_JOB_ARTIFACTS) — acá
# hardcodeado porque este script standalone no importa la app FastAPI, pero configurable por
# env var (mismo nombre) para no divergir entre entornos.
_BUCKET = os.environ.get("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
_KEY = "config/calendario_2026.json"
_REQUIRED_FIELDS = {"id", "fecha", "titulo", "descripcion", "tipo", "urgencia"}


def extract_eventos(report: str) -> list[dict]:
    match = _JSON_BLOCK.search(report)
    if not match:
        raise ValueError("El reporte no contiene un bloque ```json``` con los vencimientos")
    eventos = json.loads(match.group(1))
    if not isinstance(eventos, list):
        raise ValueError("El bloque JSON no es una lista")
    for e in eventos:
        faltantes = _REQUIRED_FIELDS - e.keys()
        if faltantes:
            raise ValueError(f"Evento sin campos obligatorios {faltantes}: {e}")
    return eventos


def merge_eventos(existentes: list[dict], nuevos: list[dict]) -> list[dict]:
    por_id = {e["id"]: e for e in existentes}
    for evento in nuevos:
        por_id[evento["id"]] = evento
    return sorted(por_id.values(), key=lambda e: e["fecha"])


def publish(report: str) -> int:
    nuevos = extract_eventos(report)

    s3 = boto3.client("s3", region_name="us-east-1")
    try:
        obj = s3.get_object(Bucket=_BUCKET, Key=_KEY)
        existentes = json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        existentes = []

    merged = merge_eventos(existentes, nuevos)
    s3.put_object(
        Bucket=_BUCKET, Key=_KEY,
        Body=json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return len(nuevos)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    n = publish(content)
    print(f"{n} vencimiento(s) mergeados en el Calendario DIAN.")
