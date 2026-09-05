"""agents/contabilidad/dian-monitor/publish.py — Valida el reporte del agente y lo inserta
en la tabla novedades. Falla (exit code != 0) si el reporte está vacío — eso hace que el job
de GitHub Actions se marque en rojo, visible, en vez de fallar en silencio."""
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))  # repo root, para "from agents._shared..."

from agents._shared.db_publish import insert_novedad  # noqa: E402
from agents._shared.agent_core import SIN_REPORTE  # noqa: E402


def publish(report: str) -> None:
    if not report or not report.strip():
        raise ValueError("El reporte del agente está vacío — no se publica nada")
    if report.strip() == SIN_REPORTE.strip():
        raise ValueError(
            "El agente agotó sus búsquedas sin producir un reporte — no se publica el texto de "
            "fallback como si fuera una novedad real"
        )

    today = date.today()
    titulo = f"Novedades DIAN — semana del {today.isoformat()}"
    insert_novedad(tipo="dian", titulo=titulo, resumen=report, fecha_generado=today)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    publish(content)
    print("Novedad DIAN publicada en la tabla novedades.")
