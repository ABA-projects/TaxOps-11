"""
DIAN Monitor — oficina contable Colombia.

Monitorea la web de la DIAN y fuentes tributarias colombianas buscando nuevas resoluciones,
circulares, decretos y cambios de tarifas. Genera un resumen semanal en Markdown con los puntos
que impactan a PYMEs.

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
    keywords = ", ".join(config.get("keywords", []))
    client = config.get("client_name", "el cliente")
    return f"""Eres un experto tributarista colombiano. Tu tarea es monitorear las fuentes oficiales
y especializadas en tributación colombiana para detectar cambios recientes (últimos 7 días) que
impacten a PYMEs.

Cliente: {client}
Temas prioritarios: {keywords}

Fuentes a revisar:
- dian.gov.co (resoluciones, circulares, comunicados)
- actualicese.com (noticias tributarias)
- gerencie.com (novedades fiscales Colombia)
- noticiascontables.com
- portafolio.co (sección impuestos)

Usa web_search con queries específicos como:
- "site:dian.gov.co resolución 2026"
- "DIAN Colombia cambio IVA retención renta 2026"
- "actualicese.com DIAN circular julio 2026"

Solo reporta cambios REALES encontrados — nunca inventes. Si no hay novedades relevantes esta
semana, indícalo claramente. Responde ÚNICAMENTE con el reporte final en Markdown, sin texto
adicional antes ni después, con este formato:

# Monitoreo DIAN — <fecha>

## Resumen ejecutivo
Una o dos líneas sobre el estado general.

## Novedades detectadas

### [Título del cambio]
- **Fuente**: nombre + link
- **Tipo**: Resolución / Circular / Decreto / Noticia
- **Fecha**: fecha de publicación
- **Impacto para PYMEs**: explicación práctica en 2-3 líneas.

## Sin novedades en
Lista de temas monitoreados sin cambios esta semana."""


def build_user_prompt(config: dict) -> str:
    return "Busca novedades tributarias de los últimos 7 días que impacten a PYMEs colombianas."


def run(config: dict, **overrides) -> str:
    """Corre el agente con un config ya cargado — usado por main() (CLI/cron) y por
    worker_handler.py (invocación on-demand desde el chatbot). Este agente no usa overrides
    (solo prospector-clientes-contables los usa) — se aceptan y se ignoran por firma
    consistente entre los 4 agentes."""
    return run_agent(build_system_prompt(config), build_user_prompt(config), AGENT_DIR)


def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run(config)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"reporte-dian-{today}.md", report)
    print(f"Reporte escrito en {output_path}")

    from publish import publish
    publish(report)


if __name__ == "__main__":
    main()
