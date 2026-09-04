import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))  # agents/ — para importar _shared
from _shared.testing import cargar_modulo_agente  # noqa: E402

agent = cargar_modulo_agente(Path(__file__).parent, "agent")


def test_run_calls_run_agent_with_built_prompts(monkeypatch):
    captured = {}

    def fake_run_agent(system_prompt, user_prompt, agent_dir):
        captured["system_prompt"] = system_prompt
        return "reporte niif de prueba"

    monkeypatch.setattr(agent, "run_agent", fake_run_agent)

    config = {"grupo_niif": "Grupo 2 (NIIF PYMES)", "normas_a_monitorear": ["Sección 23"]}
    result = agent.run(config)

    assert result == "reporte niif de prueba"
    assert "Grupo 2 (NIIF PYMES)" in captured["system_prompt"]


def test_run_ignores_unknown_overrides(monkeypatch):
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: "ok")
    assert agent.run({}, ciudad="no aplica acá") == "ok"
