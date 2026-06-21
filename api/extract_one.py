"""Script de extracción de un certificado de retención.

Usado por el router de exógenas vía asyncio.create_subprocess_exec
para aislar pdfplumber/pytesseract en un proceso separado que puede
ser matado con SIGKILL si se cuelga.

Uso:  python extract_one.py /path/to/archivo.pdf
Salida: JSON en stdout — lista de dicts o {"error": "..."}
"""
import json
import sys
from pathlib import Path

# Añadir raíz del proyecto al path (igual que api/main.py)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Falta argumento: ruta del archivo"}))
        sys.exit(0)

    path = Path(sys.argv[1])
    try:
        from exogenas.extractor import extract_many
        rows = extract_many(path)
        print(json.dumps(rows, default=str))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))


if __name__ == "__main__":
    main()
