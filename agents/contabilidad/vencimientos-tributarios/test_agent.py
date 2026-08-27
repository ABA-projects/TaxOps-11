import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import agent  # noqa: E402


def test_run_calls_run_agent_with_built_prompts(monkeypatch):
    captured = {}

    def fake_run_agent(system_prompt, user_prompt, agent_dir):
        captured["system_prompt"] = system_prompt
        return "reporte vencimientos de prueba"

    monkeypatch.setattr(agent, "run_agent", fake_run_agent)

    config = {"tipo_contribuyente": "Gran contribuyente", "obligaciones": ["IVA", "Renta"]}
    result = agent.run(config)

    assert result == "reporte vencimientos de prueba"
    assert "Gran contribuyente" in captured["system_prompt"]


def test_run_ignores_unknown_overrides(monkeypatch):
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: "ok")
    assert agent.run({}, sector="no aplica acá") == "ok"
