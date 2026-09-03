"""Guarda contra el drift de dependencias entre los agentes y la imagen Lambda.

El worker (api/worker_handler.py) ejecuta los agentes de agents/contabilidad/* IN-PROCESS, pero
api/Dockerfile-lambda solo instala api/requirements-api.txt — nunca los requirements.txt de los
agentes. Si un agente declara una dependencia que ese archivo no tiene, el import falla recién en
producción, dentro del Lambda, y solo se ve como un job en estado "error".

Pasó de verdad el 2026-09-03: faltaba `ddgs` y el primer job real murió con
"No module named 'ddgs'". Ni los tests ni tres rondas de review lo detectaron, porque en el
entorno de desarrollo la dependencia sí está instalada.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent


def _nombres(texto: str) -> set[str]:
    """Nombres de paquete normalizados (sin versión, sin comentarios, case-insensitive)."""
    nombres = set()
    for linea in texto.splitlines():
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        nombre = re.split(r"[><=!\[]", linea)[0].strip()
        if nombre:
            nombres.add(nombre.lower().replace("_", "-"))
    return nombres


def test_deps_de_agentes_estan_en_la_imagen_lambda():
    imagen = _nombres((_ROOT / "api" / "requirements-api.txt").read_text())

    faltantes: dict[str, set[str]] = {}
    for req in sorted((_ROOT / "agents" / "contabilidad").glob("*/requirements.txt")):
        falta = _nombres(req.read_text()) - imagen
        if falta:
            faltantes[req.parent.name] = falta

    assert not faltantes, (
        "Estos agentes declaran dependencias que api/requirements-api.txt no instala, así que el "
        "worker fallaría en producción al importarlas: "
        f"{faltantes}. Agregalas a api/requirements-api.txt."
    )
