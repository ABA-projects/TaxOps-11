"""
Disparador automático — observa la carpeta facturas/ y procesa nuevos archivos.

Uso:
    python watcher.py
    python watcher.py --carpeta C:/ruta/facturas
    python watcher.py --ingresos 2026-04:5000000,2026-03:4500000

Al detectar un PDF o XML nuevo (o en subcarpeta), espera 5 s para que el
archivo termine de copiarse y luego re-procesa toda la carpeta.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("ERROR: instala watchdog para usar el watcher local: pip install watchdog>=4.0.0")
    sys.exit(1)

from main import procesar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHER] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

EXTENSIONES = {".pdf", ".xml"}
ESPERA_SEGUNDOS = 5  # Tiempo para que el SO termine de copiar el archivo


class FacturaHandler(FileSystemEventHandler):
    def __init__(self, carpeta: Path, ingresos_raw: str):
        self._carpeta = carpeta
        self._ingresos_raw = ingresos_raw
        self._ultimo_proceso = 0.0  # Evita reprocesar dos veces seguidas

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.suffix.lower() not in EXTENSIONES:
            return

        ahora = time.time()
        # Debounce: ignora eventos repetidos en menos de 10 s
        if ahora - self._ultimo_proceso < 10:
            return

        logger.info("Nuevo archivo detectado: %s — esperando %ss...", p.name, ESPERA_SEGUNDOS)
        time.sleep(ESPERA_SEGUNDOS)

        try:
            out = procesar(self._carpeta, self._ingresos_raw)
            logger.info("Excel generado: %s", out)
            self._ultimo_proceso = time.time()
        except SystemExit:
            pass
        except Exception as e:
            logger.error("Error al procesar: %s", e)

    # on_moved cubre cuando el SO mueve el archivo a la carpeta (ej. descarga terminada)
    on_moved = on_created


def main():
    parser = argparse.ArgumentParser(description="Observador automático de facturas DIAN")
    parser.add_argument("--carpeta",  default="facturas", help="Carpeta a observar")
    parser.add_argument("--ingresos", default="",         help="Ingresos gravados: YYYY-MM:valor,...")
    args = parser.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.exists():
        logger.error("Carpeta no encontrada: %s", carpeta)
        sys.exit(1)

    handler = FacturaHandler(carpeta, args.ingresos)
    observer = Observer()
    observer.schedule(handler, str(carpeta), recursive=True)
    observer.start()

    logger.info("Observando %s (Ctrl+C para detener)...", carpeta.resolve())
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        logger.info("Observador detenido.")


if __name__ == "__main__":
    main()
