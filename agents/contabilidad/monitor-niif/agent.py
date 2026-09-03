"""
Monitor NIIF — oficina contable Colombia.

Monitorea actualizaciones a las Normas Internacionales de Información Financiera (NIIF/IFRS)
aplicables en Colombia según los Decretos 2420 y 2496, y cambios emitidos por el Consejo
Técnico de la Contaduría Pública (CTCP).

Usa el motor compartido en agents/_shared/agent_core.py.

Uso:
    cp config.example.yaml config.yaml
    echo "GROQ_API_KEY=gsk_..." > .env
    python agent.py
"""
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR.parent.parent))  # agents/ — para importar _shared

from _shared.agent_core import load_config, load_env, run_agent, write_report  # noqa: E402

load_env(AGENT_DIR)


def build_system_prompt(config: dict) -> str:
    grupo = config.get("grupo_niif", "Grupo 1 (NIIF Plenas)")
    normas = ", ".join(config.get("normas_a_monitorear", []))
    cliente = config.get("client_name", "el cliente")

    return f"""Eres un experto en Normas Internacionales de Información Financiera (NIIF/IFRS)
aplicadas en Colombia. Tu tarea es detectar actualizaciones, interpretaciones y cambios recientes
que afecten a empresas colombianas.

Cliente: {cliente}
Grupo NIIF aplicable: {grupo}
Normas a monitorear: {normas}

Fuentes a revisar:
- ctcp.gov.co (Consejo Técnico de la Contaduría Pública)
- ifrs.org (cambios en estándares internacionales)
- actualicese.com (NIIF Colombia)
- mincomercio.gov.co (decretos contables)
- gerencie.com (NIIF aplicación práctica)

Queries sugeridos:
- "site:ctcp.gov.co orientación concepto 2026"
- "NIIF Colombia cambio actualización 2026"
- "IFRS Colombia decreto 2026 ministerio comercio"
- "actualicese.com NIIF actualización 2026"

Solo reporta cambios REALES con fuente verificable. Responde ÚNICAMENTE con el reporte en
Markdown con este formato:

# Monitor NIIF — <fecha>

## Resumen ejecutivo
Estado general: cambios relevantes o sin novedades.

## Actualizaciones detectadas

### [Norma/Estándar afectado]
- **Fuente**: nombre + link
- **Tipo de cambio**: Interpretación / Modificación / Nuevo decreto
- **Fecha**: fecha de publicación
- **Aplica a**: {grupo}
- **Impacto práctico**: explicación en 2-3 líneas sobre cómo afecta los estados financieros.

## Sin cambios detectados en
Lista de normas monitoreadas sin novedades."""


def build_user_prompt(config: dict) -> str:
    return "Busca actualizaciones NIIF/IFRS recientes (últimos 30 días) aplicables en Colombia."


def run(config: dict, **overrides) -> str:
    """Ver dian-monitor/agent.py::run() — mismo contrato, no usa overrides."""
    return run_agent(build_system_prompt(config), build_user_prompt(config), AGENT_DIR)


def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run(config)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"monitor-niif-{today}.md", report)
    print(f"Reporte escrito en {output_path}")

    from publish import publish
    publish(report)


if __name__ == "__main__":
    main()
