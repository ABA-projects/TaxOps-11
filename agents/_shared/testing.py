"""Carga de módulos de agentes para los tests, sin colisión de nombres.

Los 4 agentes tienen cada uno su propio `agent.py` y su propio `publish.py`. Un `import agent`
normal cachea el PRIMERO que se cargue en `sys.modules["agent"]` y devuelve ese mismo para los
demás, así que correr los tests de más de un agente en la misma sesión de pytest fallaba en la
colección. Es exactamente la misma colisión que `api/worker_handler.py::_load_module` resuelve en
producción, y por eso se ataca igual: cargar por ruta explícita bajo un nombre único.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def cargar_modulo_agente(agent_dir: Path, nombre: str):
    """Carga `<agent_dir>/<nombre>.py` bajo una clave única en sys.modules.

    `agent_dir` es la carpeta del agente (normalmente `Path(__file__).parent` desde el test) y
    `nombre` el módulo sin extensión ("agent" o "publish").
    """
    clave = f"agente_{agent_dir.name}_{nombre}"
    if clave in sys.modules:
        return sys.modules[clave]

    # El propio agent.py hace sys.path.insert para resolver `from _shared.agent_core import ...`,
    # así que basta con ejecutarlo: no hace falta preparar el path acá.
    spec = importlib.util.spec_from_file_location(clave, agent_dir / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[clave] = modulo
    spec.loader.exec_module(modulo)
    return modulo
