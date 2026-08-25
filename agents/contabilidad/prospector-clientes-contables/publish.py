"""agents/contabilidad/prospector-clientes-contables/publish.py — Extrae el bloque JSON del
reporte del agente y lo inserta en leads_comerciales (dedup por empresa+ciudad, ver Task 2)."""
import json
import re
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent.parent))

from agents._shared.db_publish import insert_lead  # noqa: E402

_JSON_BLOCK = re.compile(r"```json\s*(\[.*?\])\s*```", re.DOTALL)


def extract_leads(report: str) -> list[dict]:
    match = _JSON_BLOCK.search(report)
    if not match:
        raise ValueError("El reporte no contiene un bloque ```json``` con la lista de leads")
    leads = json.loads(match.group(1))
    if not isinstance(leads, list):
        raise ValueError("El bloque JSON no es una lista")
    return leads


def publish(report: str) -> int:
    leads = extract_leads(report)
    today = date.today()
    for lead in leads:
        insert_lead(
            empresa=lead["empresa"],
            sector=lead.get("sector", ""),
            ciudad=lead.get("ciudad", ""),
            contacto=lead.get("contacto", ""),
            fuente_url=lead.get("fuente_url", ""),
            fecha_generado=today,
        )
    return len(leads)


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not report_path:
        print("Uso: python publish.py <ruta-al-reporte.md>", file=sys.stderr)
        sys.exit(1)
    content = Path(report_path).read_text(encoding="utf-8")
    n = publish(content)
    print(f"{n} lead(s) publicados en leads_comerciales.")
