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


# --- memoria de queries muertas en Lambda (/var/task es read-only) ---------------------------

def test_memoria_va_a_tmp_en_lambda(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "taxops-worker-prod")
    path = core._memory_path(Path("/var/task/agents/contabilidad/dian-monitor"))
    assert str(path).startswith("/tmp/"), "en Lambda solo /tmp es escribible"
    assert "dian-monitor" in path.name, "el nombre debe distinguir un agente de otro"


def test_memoria_va_junto_al_agente_fuera_de_lambda(monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    agent_dir = Path("/repo/agents/contabilidad/dian-monitor")
    assert core._memory_path(agent_dir) == agent_dir / "memory.json"


def test_remember_dead_end_no_revienta_si_el_fs_es_read_only(monkeypatch, tmp_path):
    """El caso real de producción: [Errno 30] Read-only file system.

    Se apunta la memoria a un directorio sin permiso de escritura en vez de parchear
    Path.write_text global, que rompería a pytest y a cualquier otra cosa que escriba.
    """
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    solo_lectura = tmp_path / "ro"
    solo_lectura.mkdir()
    solo_lectura.chmod(0o500)   # r-x: no se puede crear nada adentro
    try:
        core.remember_dead_end(solo_lectura, "una query cualquiera")   # no debe lanzar
    finally:
        solo_lectura.chmod(0o700)   # restaurar para que tmp_path se pueda limpiar


def test_load_dead_end_queries_ignora_archivo_corrupto(monkeypatch, tmp_path):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    (tmp_path / "memory.json").write_text("{no es json valido")
    assert core.load_dead_end_queries(tmp_path) == set()


# --- terminación del loop (corrida real 2026-09-04: 15 iteraciones sin entregar reporte) -----

class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none=False):
        return {"role": "assistant", "content": self.content}


class _FakeCall:
    def __init__(self, i):
        self.id = f"c{i}"
        self.function = type("F", (), {"arguments": '{"query": "q"}'})()


def test_ultima_iteracion_prohibe_buscar_y_exige_reporte(monkeypatch):
    """Sin esto el modelo explora hasta agotar el presupuesto y no entrega nada."""
    llamadas = []

    def _fake_chat(client, **kwargs):
        llamadas.append(kwargs)
        # siempre pide otra búsqueda, salvo que se lo prohíban
        if kwargs.get("tool_choice") == "none":
            return type("R", (), {"choices": [_FakeChoice(_FakeMessage(content="REPORTE FINAL"))]})()
        return type("R", (), {"choices": [_FakeChoice(_FakeMessage(tool_calls=[_FakeCall(0)]))]})()

    # run_agent hace `from groq import Groq` adentro, así que el cliente se construye de verdad:
    # basta una key ficticia porque _groq_chat_with_retry está mockeado y nunca sale a la red.
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_no_se_usa")
    monkeypatch.setattr(core, "_groq_chat_with_retry", _fake_chat)
    monkeypatch.setattr(core, "web_search", lambda q, d: [{"info": "x"}])
    monkeypatch.setattr(core, "MODEL", "fake-model")

    resultado = core.run_agent("sys", "usr", Path("/tmp"), max_iterations=4, debug=False)

    assert resultado == "REPORTE FINAL", "debe cerrar con un reporte, no con el fallback"
    assert llamadas[-1]["tool_choice"] == "none", "la última iteración no puede permitir búsquedas"
    assert all(c.get("tool_choice") == "auto" for c in llamadas[:-1]), "las previas sí buscan"
    # y se le dice explícitamente que escriba el reporte
    assert any("NO busques más" in (m.get("content") or "") for m in llamadas[-1]["messages"])


def test_publish_novedades_rechaza_el_texto_de_fallback():
    """No persistir SIN_REPORTE como si fuera una novedad real (pasó en producción)."""
    import importlib.util

    ruta = _ROOT / "agents" / "contabilidad" / "dian-monitor" / "publish.py"
    spec = importlib.util.spec_from_file_location("publish_dian_para_test", ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["publish_dian_para_test"] = mod
    spec.loader.exec_module(mod)

    import pytest
    with pytest.raises(ValueError, match="fallback"):
        mod.publish(core.SIN_REPORTE)
