"""
Prospector Clientes Contables — oficina contable Colombia.

Busca empresas colombianas en directorios y LinkedIn que podrían necesitar servicios contables
(sin contador visible, en sectores objetivo, en ciudades configuradas). Genera un reporte semanal
con leads calificados.

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


def build_system_prompt(config: dict, sector: str | None = None, ciudad: str | None = None) -> str:
    agencia = config.get("agencia_nombre", "la firma contable")
    sectores = sector if sector else ", ".join(config.get("sectores_objetivo", []))
    ciudades = ciudad if ciudad else ", ".join(config.get("ciudades", []))
    servicios = ", ".join(config.get("servicios_ofrecidos", []))

    return f"""Eres un agente de prospección comercial para una firma contable colombiana.
Tu tarea es encontrar empresas que probablemente necesiten contratar servicios de contabilidad
externos.

Firma que prospecta: {agencia}
Ciudades objetivo: {ciudades}
Sectores objetivo: {sectores}
Servicios a ofrecer: {servicios}

Busca usando queries como:
- "empresas [sector] [ciudad] Colombia contacto"
- "site:linkedin.com/company [sector] [ciudad] Colombia"
- "directorio empresas [sector] [ciudad] Colombia"
- "camara comercio [ciudad] empresas registradas [sector]"
- "páginas amarillas [sector] [ciudad]"

Para cada lead encontrado, extrae: nombre de la empresa, sector, ciudad, contacto disponible
(email, teléfono, LinkedIn, sitio web). Solo incluye empresas reales con información verificable.

Responde ÚNICAMENTE con el reporte en Markdown con este formato:

# Leads Contables — <fecha>

## Resumen
X leads encontrados en Y sectores.

## Leads por sector

### [Nombre del sector]
| Empresa | Ciudad | Contacto disponible | Fuente |
|---------|--------|--------------------|---------|
| nombre | ciudad | email/web/linkedin | URL |

## Observaciones
Notas sobre la calidad de los leads o sectores con más oportunidad.

Al final de tu respuesta, agrega un bloque ```json con la lista de leads encontrados en este
formato exacto (lista vacía si no encontraste ninguno verificable):

```json
[
  {{"empresa": "...", "sector": "...", "ciudad": "...", "contacto": "...", "fuente_url": "..."}}
]
```
"""


def build_user_prompt(config: dict, sector: str | None = None, ciudad: str | None = None) -> str:
    sectores = [sector] if sector else config.get("sectores_objetivo", [])
    ciudades = [ciudad] if ciudad else config.get("ciudades", ["Medellín", "Bogotá"])
    return (
        f"Busca empresas en los sectores {sectores} ubicadas en {ciudades}, Colombia, "
        "que podrían necesitar servicios contables externos."
    )


def run(config: dict, **overrides) -> str:
    """A diferencia de los otros 3 agentes, sí usa overrides — sector/ciudad puntuales pedidos
    on-demand desde el chatbot reemplazan (no se mezclan con) config.yaml."""
    sector = overrides.get("sector")
    ciudad = overrides.get("ciudad")
    return run_agent(
        build_system_prompt(config, sector=sector, ciudad=ciudad),
        build_user_prompt(config, sector=sector, ciudad=ciudad),
        AGENT_DIR,
    )


def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run(config)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"leads-contables-{today}.md", report)
    print(f"Reporte escrito en {output_path}")

    from publish import publish
    publish(report)


if __name__ == "__main__":
    main()
