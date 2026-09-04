import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))  # agents/ — para importar _shared
from _shared.testing import cargar_modulo_agente  # noqa: E402

agent = cargar_modulo_agente(Path(__file__).parent, "agent")


def test_run_without_overrides_uses_config(monkeypatch):
    captured = {}

    def fake_run_agent(system_prompt, user_prompt, agent_dir):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return "reporte de config"

    monkeypatch.setattr(agent, "run_agent", fake_run_agent)

    config = {"sectores_objetivo": ["restaurantes"], "ciudades": ["Medellín"]}
    result = agent.run(config)

    assert result == "reporte de config"
    assert "restaurantes" in captured["system_prompt"]
    assert "Medellín" in captured["user_prompt"]


def test_run_with_overrides_uses_override_sector_ciudad(monkeypatch):
    captured = {}

    def fake_run_agent(system_prompt, user_prompt, agent_dir):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return "reporte on-demand"

    monkeypatch.setattr(agent, "run_agent", fake_run_agent)

    config = {"sectores_objetivo": ["restaurantes"], "ciudades": ["Medellín"]}
    result = agent.run(config, sector="veterinarias", ciudad="Bucaramanga")

    assert result == "reporte on-demand"
    assert "veterinarias" in captured["system_prompt"]
    assert "veterinarias" in captured["user_prompt"]
    assert "Bucaramanga" in captured["user_prompt"]
    # el override reemplaza, no se mezcla con lo de config.yaml
    assert "restaurantes" not in captured["system_prompt"]
