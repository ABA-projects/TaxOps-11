import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))  # agents/
from _shared.testing import cargar_modulo_agente  # noqa: E402

publish_mod = cargar_modulo_agente(Path(__file__).parent, "publish")
extract_leads = publish_mod.extract_leads

_VALID_REPORT = """
## Leads encontrados
Encontré 2 empresas.

```json
[
  {"empresa": "Restaurante A", "sector": "restaurantes", "ciudad": "Medellín",
   "contacto": "a@a.com", "fuente_url": "https://a.com"},
  {"empresa": "Consultorio B", "sector": "salud", "ciudad": "Envigado", "contacto": "", "fuente_url": ""}
]
```
"""


def test_extract_leads_valid_json():
    leads = extract_leads(_VALID_REPORT)
    assert len(leads) == 2
    assert leads[0]["empresa"] == "Restaurante A"


def test_extract_leads_no_json_block_raises():
    with pytest.raises(ValueError, match="no contiene un bloque"):
        extract_leads("Reporte sin bloque json.")


def test_extract_leads_empty_list_is_valid():
    leads = extract_leads("```json\n[]\n```")
    assert leads == []
