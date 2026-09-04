"""
Núcleo compartido de todos los agentes de este repo.

Antes, cada agente (agents/<categoria>/<nombre>/agent.py) copiaba ~180-260 líneas idénticas:
el loop de tool-calling contra Groq, la función de búsqueda web, la carga de config/.env. Solo
el prompt y la config cambiaban entre agentes. Este módulo es el motor compartido — cada
agente ahora es un archivo delgado (perfil + prompt) que importa esto. Es el mismo concepto de
"skill" que un SOP reutilizable: se corrige una vez aquí, se corrige para los 13 agentes.

Root cause investigado (no era límite de Groq — 0 errores 429 en 6 corridas de prueba):
DuckDuckGo (`ddgs`, scraping no oficial, sin key) rate-limita/degrada bajo el volumen de
búsquedas que genera una sola corrida (4-8+ llamadas), y eso se disfrazaba de "sin resultados".
Ver docs/superpowers/... para el detalle. Fix real: retry+backoff en cada búsqueda, límite de
iteraciones más bajo con guía explícita al modelo para no repetir variaciones de una query
fallida, y memoria entre corridas de qué (fuente, query) no vale la pena reintentar.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
import yaml

# Modelo por defecto: el gratuito de Groq (llama-3.3-70b-versatile fue deprecado por Groq).
# Configurable por entorno para poder pasar a un modelo de pago sin tocar código: basta con
# setear AGENTS_MODEL en las env vars de la Lambda (infra/modules/lambda-api, var.secrets) o en
# el .env local. Si el modelo nuevo NO es de Groq (p. ej. Claude), además hay que cambiar el
# cliente en run_agent()/run_llm_only() — hoy ambos instancian Groq() directo.
MODEL = os.environ.get("AGENTS_MODEL", "openai/gpt-oss-120b")
MEMORY_TTL_DAYS = 7  # cuánto tiempo se recuerda que una query no dio resultados

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Busca en la web y devuelve título, URL y resumen de cada resultado.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query de búsqueda, ej. 'site:upwork.com terraform kubernetes'",
                },
            },
            "required": ["query"],
        },
    },
}

# Guía compartida que se agrega al final de todo system prompt — ataca directamente el patrón de
# fallo real observado: el modelo repetía variaciones de la misma query fallida hasta agotar el
# límite de iteraciones, en vez de moverse a la siguiente fuente o cerrar con lo que tenía.
SEARCH_STRATEGY_SUFFIX = """

Estrategia de búsqueda (importante para no desperdiciar intentos):
- Máximo 2 queries por fuente. Si ninguna de las 2 da resultados útiles, pasa a la siguiente
  fuente — no sigas reformulando la misma búsqueda una tercera o cuarta vez.
- Empieza con queries amplias (2-3 palabras clave), no con frases entre comillas combinadas —
  las queries muy restrictivas (site: + varias frases exactas + números) casi nunca devuelven
  nada en la búsqueda web disponible.
- Si una fuente no da nada en tus 2 intentos, repórtalo como "sin resultados en esa fuente" y
  sigue — no es un error, es información real que va en el reporte."""


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        sys.exit(f"Falta {config_path}. Copia config.example.yaml a config.yaml y ajusta el perfil.")
    return yaml.safe_load(config_path.read_text())


def load_env(agent_dir: Path) -> None:
    """Carga .env desde la carpeta del agente (no desde el cwd) — cada agente tiene el suyo."""
    load_dotenv(agent_dir / ".env")


# ---------------------------------------------------------------------------
# Memoria entre corridas — qué queries no valen la pena reintentar.
#
# Concepto tomado directamente de la idea de "memory.md" de agentes persistentes: el agente
# recuerda entre sesiones, no solo dentro de una. Aquí en versión mínima y con propósito
# operativo concreto (no memoria general, solo "esto no funcionó, no lo repitas todavía").
# ---------------------------------------------------------------------------

def _memory_path(agent_dir: Path) -> Path:
    """Dónde guardar la memoria de queries muertas.

    En Lambda el código vive en /var/task, que está montado de SOLO LECTURA: el único lugar
    escribible es /tmp. Escribir junto al agente funcionaba en CLI/cron pero reventaba en el
    worker con "[Errno 30] Read-only file system" (visto en producción el 2026-09-04).

    En /tmp la memoria es efímera: sobrevive entre invocaciones del mismo contenedor tibio y se
    pierde en el siguiente cold start. Es aceptable porque esto es una optimización (evitar
    repetir queries que no dieron resultados), no un dato de negocio.
    """
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp") / f"{agent_dir.name}-memory.json"
    return agent_dir / "memory.json"


def load_dead_end_queries(agent_dir: Path) -> set[str]:
    """Devuelve el set de queries que no dieron resultados recientemente (dentro de MEMORY_TTL_DAYS)."""
    path = _memory_path(agent_dir)
    if not path.exists():
        return set()

    try:
        entries = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        # Un archivo corrupto o ilegible no puede tumbar la corrida: es solo una optimización.
        print(f"[memoria] ignorando {path}: {e}", file=sys.stderr)
        return set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=MEMORY_TTL_DAYS)
    return {
        e["query"]
        for e in entries
        if datetime.fromisoformat(e["at"]) > cutoff
    }


def remember_dead_end(agent_dir: Path, query: str) -> None:
    """Registra una query sin resultados. Nunca propaga errores: no poder persistir una
    optimización no justifica abortar la corrida entera del agente."""
    path = _memory_path(agent_dir)
    try:
        entries = json.loads(path.read_text()) if path.exists() else []
        entries.append({"query": query, "at": datetime.now(timezone.utc).isoformat()})
        # Recorta a las últimas 200 para que el archivo no crezca indefinidamente
        path.write_text(json.dumps(entries[-200:], indent=2))
    except (OSError, ValueError) as e:
        print(f"[memoria] no se pudo guardar {path}: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Búsqueda web con retry + backoff — el fix real para el rate-limit de DuckDuckGo
# ---------------------------------------------------------------------------

# El tier gratuito de Groq permite 8000 tokens por minuto, y una request sola no puede pasarlo.
# run_agent() acumula CADA resultado de búsqueda en `messages` sin podar nunca, así que la
# conversación crecía de forma monotónica hasta que una request pesaba más que el tope y Groq
# respondía 413 "Request too large" (visto en producción el 2026-09-03: 8097 tokens vs 8000).
# A diferencia del 429 que arregló el PR #34, reintentar no ayuda: la request siempre sería igual
# de grande. Se ataca por los dos lados: snippets más cortos y ventana deslizante de resultados.
# Ambos son tunables por entorno: cuando se pase a un tier/modelo con más tokens, subirlos por
# env var recupera contexto (y calidad del reporte) sin tocar código.
_MAX_SNIPPET_CHARS = int(os.environ.get("AGENTS_MAX_SNIPPET_CHARS", "250"))
_MAX_TOOL_RESULTS_EN_CONTEXTO = int(os.environ.get("AGENTS_MAX_TOOL_RESULTS", "6"))


def _podar_historial(messages: list[dict]) -> list[dict]:
    """Deja el system+user intactos y conserva solo los últimos N resultados de búsqueda.

    Los mensajes de rol "tool" son los que pesan (JSON con varios snippets cada uno). Los más
    viejos se reemplazan por un marcador corto en vez de borrarse, porque cada tool_call del
    asistente necesita su respuesta correspondiente: si se elimina, la API rechaza el historial
    por inconsistente.
    """
    indices_tool = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    if len(indices_tool) <= _MAX_TOOL_RESULTS_EN_CONTEXTO:
        return messages

    a_podar = set(indices_tool[:-_MAX_TOOL_RESULTS_EN_CONTEXTO])
    return [
        {**m, "content": '[resultado antiguo omitido para no exceder el límite de tokens]'}
        if i in a_podar else m
        for i, m in enumerate(messages)
    ]


def web_search(query: str, agent_dir: Path, max_results: int = 5, retries: int = 2, backoff: float = 2.0) -> list[dict]:
    """Busca en DuckDuckGo (gratis, sin API key). Reintenta con backoff antes de rendirse —
    DDG rate-limita el scraping no oficial bajo uso repetido en poco tiempo, que es la causa
    real de los "sin resultados" que antes se veían, no un límite de Groq."""
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException

    dead_ends = load_dead_end_queries(agent_dir)
    if query in dead_ends:
        return [{"info": "Esta query no dio resultados recientemente (memoria de corridas previas) — prueba otra."}]

    last_error = None
    for attempt in range(retries + 1):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if results:
                return [
                    {
                        "title": r.get("title"),
                        "url": r.get("href"),
                        "snippet": (r.get("body") or "")[:_MAX_SNIPPET_CHARS],
                    }
                    for r in results
                ]
            remember_dead_end(agent_dir, query)
            return [{"info": "Sin resultados para esta query."}]
        except DDGSException as e:
            last_error = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))  # backoff exponencial simple
                continue

    remember_dead_end(agent_dir, query)
    return [{"error": f"Búsqueda fallida tras {retries + 1} intentos: {last_error}"}]


# ---------------------------------------------------------------------------
# Loop de tool-calling contra Groq
# ---------------------------------------------------------------------------

def _groq_chat_with_retry(client, *, retries: int = 3, backoff: float = 15.0, **kwargs):
    """Wrapper de client.chat.completions.create() con retry+backoff ante 429 RateLimitError.

    Groq comparte un límite de TPM (tokens/minuto) por cuenta entre TODAS las llamadas
    concurrentes — cuando varios agentes corren a la vez (o uno solo con muchas iteraciones
    de búsqueda) es fácil pisarlo. Sin este retry, un 429 tumbaba el job entero (visto en
    producción el 2026-08-25 corriendo los 4 agentes en paralelo)."""
    from groq import RateLimitError

    last_error = None
    for attempt in range(retries + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            last_error = e
            if attempt < retries:
                wait = backoff * (attempt + 1)
                print(f"[groq] rate limit — reintentando en {wait:.0f}s ({e})", file=sys.stderr)
                time.sleep(wait)
                continue
    raise last_error


def run_agent(
    system_prompt: str,
    user_prompt: str,
    agent_dir: Path,
    *,
    max_iterations: int = 15,
    debug: bool = True,
) -> str:
    """Corre el loop observar-pensar-actuar contra Groq hasta que el modelo entregue el
    reporte final (sin más tool_calls) o se agoten las iteraciones."""
    from groq import Groq

    client = Groq()  # lee GROQ_API_KEY del entorno (cargado por load_env())
    messages = [
        {"role": "system", "content": system_prompt + SEARCH_STRATEGY_SUFFIX},
        {"role": "user", "content": user_prompt},
    ]

    for i in range(max_iterations):
        response = _groq_chat_with_retry(
            client,
            model=MODEL,
            messages=_podar_historial(messages),
            tools=[WEB_SEARCH_TOOL],
        )
        choice = response.choices[0]
        messages.append(choice.message.model_dump(exclude_none=True))

        if not choice.message.tool_calls:
            return choice.message.content

        if debug:
            print(f"[iter {i}] {len(choice.message.tool_calls)} tool call(s)", file=sys.stderr)

        for call in choice.message.tool_calls:
            args = json.loads(call.function.arguments)
            query = args.get("query", "")
            if debug:
                print(f"  -> web_search({query!r})", file=sys.stderr)
            results = web_search(query, agent_dir)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(results)}
            )

    return (
        "No se pudo completar la búsqueda en el límite de iteraciones disponible. "
        "Esto normalmente significa que las fuentes configuradas no tienen resultados indexados "
        "para los criterios pedidos — revisar manualmente antes de asumir que el agente falló."
    )


def run_llm_only(system_prompt: str, user_prompt: str) -> str:
    """Para agentes que no necesitan buscar en la web — una sola llamada a Groq, sin tools ni
    loop (ej. generación de contenido a partir de datos ya dados en config.yaml)."""
    from groq import Groq

    client = Groq()
    response = _groq_chat_with_retry(
        client,
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def write_report(agent_dir: Path, output_dir_name: str, filename: str, content: str) -> Path:
    output_dir = agent_dir / output_dir_name
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(content)
    return output_path
