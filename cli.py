"""cli.py — Punto de entrada para ejecutar TaxOps como comando instalado."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Lanza `streamlit run Home.py` desde la ubicación de instalación."""
    home = Path(__file__).parent / "Home.py"
    if not home.exists():
        print(f"ERROR: No se encontró Home.py en {home.parent}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, "-m", "streamlit", "run", str(home)] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
