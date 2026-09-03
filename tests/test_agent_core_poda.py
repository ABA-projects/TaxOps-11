"""Poda de contexto en agents/_shared/agent_core.py.

Vive en tests/ (y no junto al módulo) a propósito: pytest.ini fija `testpaths = tests` y CI corre
`pytest tests/`, así que cualquier test bajo agents/ NUNCA se ejecuta en CI. Ver la nota sobre esa
brecha en docs/evidencias/2026-09-03-agentes-on-demand/.

Cubre el fallo real de producción del 2026-09-03: Groq devolvió 413 "Request too large"
(8097 tokens contra un tope de 8000 TPM) porque run_agent() acumulaba cada resultado de búsqueda
en el historial sin podarlo nunca.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT / "agents") not in sys.path:
    sys.path.insert(0, str(_ROOT / "agents"))

from _shared.agent_core import (  # noqa: E402
    _MAX_TOOL_RESULTS_EN_CONTEXTO,
    _podar_historial,
    web_search,
)
import _shared.agent_core as core  # noqa: E402


def _historial(n_tools: int) -> list[dict]:
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
    for i in range(n_tools):
        msgs.append({"role": "assistant", "tool_calls": [{"id": f"c{i}"}]})
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": f"resultado {i}"})
    return msgs


def test_podar_no_toca_historial_corto():
    msgs = _historial(_MAX_TOOL_RESULTS_EN_CONTEXTO)
    assert _podar_historial(msgs) == msgs


def test_podar_conserva_los_ultimos_y_marca_los_viejos():
    n = _MAX_TOOL_RESULTS_EN_CONTEXTO + 3
    podado = _podar_historial(_historial(n))

    tools = [m for m in podado if m.get("role") == "tool"]
    # el total no cambia: cada tool_call necesita su respuesta o la API rechaza el historial
    assert len(tools) == n
    intactos = [m for m in tools if not m["content"].startswith("[resultado antiguo")]
    assert len(intactos) == _MAX_TOOL_RESULTS_EN_CONTEXTO
    assert intactos[-1]["content"] == f"resultado {n - 1}"   # sobreviven los más recientes
    assert podado[0]["content"] == "sys"
    assert podado[1]["content"] == "usr"


def test_podar_preserva_el_tool_call_id():
    """Si se rompe la correspondencia tool_call -> respuesta, la API rechaza el historial."""
    podado = _podar_historial(_historial(_MAX_TOOL_RESULTS_EN_CONTEXTO + 2))
    for m in podado:
        if m.get("role") == "tool":
            assert m.get("tool_call_id"), "toda respuesta de tool debe conservar su tool_call_id"


def test_web_search_trunca_snippets_largos(monkeypatch):
    import types

    class _FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results):
            return [{"title": "t", "href": "u", "body": "x" * 5000}]

    mod = types.ModuleType("ddgs")
    mod.DDGS = _FakeDDGS
    exc = types.ModuleType("ddgs.exceptions")
    exc.DDGSException = Exception
    monkeypatch.setitem(sys.modules, "ddgs", mod)
    monkeypatch.setitem(sys.modules, "ddgs.exceptions", exc)
    monkeypatch.setattr(core, "load_dead_end_queries", lambda d: set())

    res = web_search("q", Path("/tmp"))
    assert len(res[0]["snippet"]) == core._MAX_SNIPPET_CHARS
