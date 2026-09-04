import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))  # agents/ — para importar _shared
from _shared.testing import cargar_modulo_agente  # noqa: E402

agent = cargar_modulo_agente(Path(__file__).parent, "agent")


def test_run_calls_run_agent_with_built_prompts(monkeypatch):
    captured = {}

    def fake_run_agent(system_prompt, user_prompt, agent_dir):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return "reporte de prueba"

    monkeypatch.setattr(agent, "run_agent", fake_run_agent)

    config = {"keywords": ["IVA", "renta"], "client_name": "Firma X"}
    result = agent.run(config)

    assert result == "reporte de prueba"
    assert "Firma X" in captured["system_prompt"]
    assert "IVA, renta" in captured["system_prompt"]


def test_run_ignores_unknown_overrides(monkeypatch):
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: "ok")
    result = agent.run({}, sector="no aplica acá")
    assert result == "ok"
