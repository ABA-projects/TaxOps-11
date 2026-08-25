"""
Vencimientos Tributarios — oficina contable Colombia.

Busca el calendario tributario vigente de la DIAN y genera un reporte con las obligaciones
que vencen en los próximos 30 días, filtrado por tipo de contribuyente configurado.

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
    tipo = config.get("tipo_contribuyente", "PYME / régimen ordinario")
    obligaciones = ", ".join(config.get("obligaciones", []))
    cliente = config.get("client_name", "el cliente")
    today = date.today().isoformat()

    return f"""Eres un experto en obligaciones tributarias colombianas. Tu tarea es encontrar las
fechas de vencimiento vigentes para el año fiscal actual y generar una alerta con los vencimientos
de los próximos 30 días desde hoy ({today}).

Cliente: {cliente}
Tipo de contribuyente: {tipo}
Obligaciones a monitorear: {obligaciones}

Busca el calendario tributario oficial de la DIAN para el año en curso. Queries sugeridos:
- "calendario tributario DIAN 2026 grandes contribuyentes personas jurídicas"
- "site:dian.gov.co calendario tributario 2026"
- "vencimientos IVA retención renta 2026 Colombia DIAN"
- "actualicese.com calendario tributario 2026"

Solo reporta fechas reales encontradas en fuentes oficiales o especializadas. Responde ÚNICAMENTE
con el reporte en Markdown con este formato:

# Vencimientos Tributarios — próximos 30 días ({today})

## ⚠️ Vencimientos urgentes (próximos 7 días)
| Obligación | Fecha límite | Aplica a | Fuente |
|-----------|-------------|----------|--------|

## 📅 Vencimientos del mes
| Obligación | Fecha límite | Aplica a | Fuente |
|-----------|-------------|----------|--------|

## 📌 Notas importantes
Cualquier observación relevante sobre el calendario o cambios recientes.

Si no encuentras fechas concretas, indica la fuente consultada y recomienda verificar directamente.

⚠️ OBLIGATORIO — sin excepción, incluso si la búsqueda no dio resultados concretos: tu respuesta
SIEMPRE termina con un bloque ```json (lista vacía [] si no encontraste vencimientos verificables).
Sin este bloque el resultado se descarta automáticamente — no lo omitas por brevedad ni lo
reemplaces solo por la tabla en Markdown de arriba.

Formato exacto del bloque (mismo shape que usa el Calendario Tributario DIAN de la plataforma):

```json
[
  {{
    "id": "vencimiento-2026-09-iva-bimestral",
    "fecha": "2026-09-15",
    "titulo": "Vencimiento IVA bimestral",
    "descripcion": "Declaración y pago IVA período jul-ago 2026",
    "tipo": "iva",
    "urgencia": "alta",
    "articulo": null,
    "link": null,
    "alertaDias": 5
  }}
]
```

El campo "id" debe ser estable y descriptivo (no un UUID aleatorio) para que corridas futuras
puedan actualizar el mismo evento en vez de duplicarlo."""


def build_user_prompt(config: dict) -> str:
    return "Busca el calendario tributario DIAN vigente y genera el reporte de vencimientos."


def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run_agent(build_system_prompt(config), build_user_prompt(config), AGENT_DIR)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"vencimientos-{today}.md", report)
    print(f"Reporte escrito en {output_path}")

    from publish import publish
    publish(report)


if __name__ == "__main__":
    main()
