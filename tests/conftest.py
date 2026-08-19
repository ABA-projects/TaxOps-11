"""tests/conftest.py — helpers/fixtures compartidos para tests que necesitan la app FastAPI.

El repo tiene DOS módulos "main" distintos: main.py en la raíz (CLI/Streamlit legacy) y
api/main.py (la app FastAPI). Un simple sys.path.insert no basta: pytest reinserta la
raíz del repo en sys.path en cada import de módulo de test (su "import mode" por
defecto, "prepend"), pisando cualquier orden que se fije de antemano — confirmado
reproduciendo el fallo (`from main import app` resolvía siempre al main.py de la raíz
incluso con api/ ya al frente de sys.path). La solución robusta: cargar api/main.py por
ruta explícita vía importlib, sin pasar por la resolución de nombres de sys.path/
sys.modules en absoluto.

`load_fastapi_app()` es una función plana, NO un fixture — se expone así a propósito
para que cada test decida CUÁNDO cargarla (normalmente después de `monkeypatch.setenv`
de las env vars que Settings() lee al importar, para que las tome bien desde el arranque
en vez de los defaults). Un fixture `fastapi_app` que dependiera de `monkeypatch` se
resolvería ANTES del cuerpo del fixture que lo consume — orden incorrecto.
"""
import importlib.util
import sys
from pathlib import Path

_API_DIR = Path(__file__).parent.parent / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def load_fastapi_app():
    """Carga api/main.py por ruta explícita y devuelve su objeto `app`.

    Llamar DESPUÉS de fijar cualquier env var relevante con monkeypatch.setenv —
    Settings() (pydantic-settings) los lee al instanciarse, dentro del import de main.py.
    """
    spec = importlib.util.spec_from_file_location("taxops_api_main", _API_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["taxops_api_main"] = module
    spec.loader.exec_module(module)
    return module.app
