# Agentes contables on-demand desde el chatbot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el chatbot de TaxOps pueda responder preguntas sobre novedades DIAN/NIIF,
vencimientos tributarios y leads comerciales consultando primero los datos ya persistidos, y
disparando una corrida on-demand del agente correspondiente (vía el mismo SQS+worker que ya usan
Exógenas/Renta) solo cuando ese dato está viejo o no existe.

**Architecture:** Cada `agent.py` gana una función `run(config, **overrides)` importable (hoy
solo son scripts CLI). `worker_handler.py` gana una rama `tipo == "agente_contable"` que carga el
`agent.py`/`publish.py` del agente pedido por ruta explícita (nombre único en `sys.modules`,
evita colisión entre los 4) y corre `run()` + `publish()`. `services/chatbot.py` gana 4 tools
nuevas que leen Postgres/S3 primero y encolan a SQS solo si el dato está viejo.

**Tech Stack:** Python, boto3 (SQS/S3), SQLAlchemy (Postgres vía `db.database`), pytest + moto +
monkeypatch (mismo patrón TDD que los PR #33/#34).

**Spec:** `docs/superpowers/specs/2026-08-25-agentes-contables-on-demand-design.md`

## Global Constraints

- El cron semanal (comentado desde el PR #34) no se toca en este plan.
- Reutiliza `Settings.SQS_QUEUE_URL` existente — sin infra nueva de Terraform.
- Las nuevas tools del chatbot leen env vars directo (`os.environ`), no `core.config.get_settings()`
  — `services/chatbot.py` puede correr fuera del contexto FastAPI (Streamlit legacy), donde `api/`
  no está garantizado en `sys.path`. Mismo criterio que ya usa `_get_key()` en este archivo.
  `db.database` sí es seguro de importar directo (vive en la raíz del repo, igual que `services/`).
- Política de staleness (aprobada en el spec):
  - dian-monitor / monitor-niif: fresco si `fecha_generado` de la última fila (por `tipo`) es
    ≤ 7 días.
  - vencimientos-tributarios: fresco si hay al menos un evento en el calendario S3 con `fecha`
    dentro de los próximos 30 días.
  - prospector-clientes-contables: fresco si ya existe al menos una fila en `leads_comerciales`
    para ese `sector`+`ciudad` exactos (sin importar antigüedad).
- Sector/ciudad de `prospector-clientes-contables` son texto libre, sin validar contra una lista
  fija.

---

### Task 1: `dian-monitor/agent.py` — extraer `run()` importable

**Files:**
- Modify: `agents/contabilidad/dian-monitor/agent.py`
- Test: `agents/contabilidad/dian-monitor/test_agent.py` (nuevo)

**Interfaces:**
- Produces: `run(config: dict, **overrides) -> str` — usado por Task 5 (`worker_handler.py`).
  `main()` sigue siendo el entry point de CLI/GitHub Actions, ahora delega a `run()`.

- [ ] **Step 1: Escribir el test que falla**

```python
# agents/contabilidad/dian-monitor/test_agent.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import agent  # noqa: E402


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
```

- [ ] **Step 2: Correr — debe fallar**

```bash
cd agents/contabilidad/dian-monitor && python -m pytest test_agent.py -v
```

Expected: FAIL (`AttributeError: module 'agent' has no attribute 'run'`).

- [ ] **Step 3: Extraer `run()` en `agent.py`**

Reemplazar el final del archivo (desde `def main()`):

```python
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
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/contabilidad/dian-monitor && python -m pytest test_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 5: flake8**

```bash
flake8 agents/contabilidad/dian-monitor/agent.py agents/contabilidad/dian-monitor/test_agent.py --max-line-length=120
```

- [ ] **Step 6: Commit**

```bash
git add agents/contabilidad/dian-monitor/agent.py agents/contabilidad/dian-monitor/test_agent.py
git commit -m "refactor: dian-monitor/agent.py expone run() importable"
```

---

### Task 2: `monitor-niif/agent.py` — extraer `run()` importable

**Files:**
- Modify: `agents/contabilidad/monitor-niif/agent.py`
- Test: `agents/contabilidad/monitor-niif/test_agent.py` (nuevo)

**Interfaces:**
- Produces: `run(config: dict, **overrides) -> str` — mismo contrato que Task 1.

- [ ] **Step 1: Escribir el test que falla**

```python
# agents/contabilidad/monitor-niif/test_agent.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import agent  # noqa: E402


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
```

- [ ] **Step 2: Correr — debe fallar**

```bash
cd agents/contabilidad/monitor-niif && python -m pytest test_agent.py -v
```

Expected: FAIL (`AttributeError: module 'agent' has no attribute 'run'`).

- [ ] **Step 3: Extraer `run()` en `agent.py`**

Leer primero el archivo completo para confirmar el nombre exacto del parámetro `agent_dir` de
`write_report` y el nombre del archivo de reporte (`monitor-niif-{today}.md`, distinto al de
dian-monitor). Reemplazar el final del archivo:

```python
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
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/contabilidad/monitor-niif && python -m pytest test_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 5: flake8**

```bash
flake8 agents/contabilidad/monitor-niif/agent.py agents/contabilidad/monitor-niif/test_agent.py --max-line-length=120
```

- [ ] **Step 6: Commit**

```bash
git add agents/contabilidad/monitor-niif/agent.py agents/contabilidad/monitor-niif/test_agent.py
git commit -m "refactor: monitor-niif/agent.py expone run() importable"
```

---

### Task 3: `vencimientos-tributarios/agent.py` — extraer `run()` importable

**Files:**
- Modify: `agents/contabilidad/vencimientos-tributarios/agent.py`
- Test: `agents/contabilidad/vencimientos-tributarios/test_agent.py` (nuevo)

**Interfaces:**
- Produces: `run(config: dict, **overrides) -> str` — mismo contrato que Task 1.

- [ ] **Step 1: Escribir el test que falla**

```python
# agents/contabilidad/vencimientos-tributarios/test_agent.py
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
```

- [ ] **Step 2: Correr — debe fallar**

```bash
cd agents/contabilidad/vencimientos-tributarios && python -m pytest test_agent.py -v
```

Expected: FAIL (`AttributeError: module 'agent' has no attribute 'run'`).

- [ ] **Step 3: Extraer `run()` en `agent.py`**

```python
def run(config: dict, **overrides) -> str:
    """Ver dian-monitor/agent.py::run() — mismo contrato, no usa overrides."""
    return run_agent(build_system_prompt(config), build_user_prompt(config), AGENT_DIR)


def main() -> None:
    config = load_config(AGENT_DIR / "config.yaml")
    report = run(config)

    today = date.today().isoformat()
    output_path = write_report(AGENT_DIR, config.get("output_dir", "output"), f"vencimientos-{today}.md", report)
    print(f"Reporte escrito en {output_path}")

    from publish import publish
    publish(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/contabilidad/vencimientos-tributarios && python -m pytest test_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Suite de este agente completa (incluye test_publish.py del PR #34) + flake8**

```bash
cd agents/contabilidad/vencimientos-tributarios && python -m pytest -v
cd /path/al/repo && flake8 agents/contabilidad/vencimientos-tributarios/ --max-line-length=120
```

Expected: 8 passed (2 nuevos + 6 de `test_publish.py`).

- [ ] **Step 6: Commit**

```bash
git add agents/contabilidad/vencimientos-tributarios/agent.py agents/contabilidad/vencimientos-tributarios/test_agent.py
git commit -m "refactor: vencimientos-tributarios/agent.py expone run() importable"
```

---

### Task 4: `prospector-clientes-contables/agent.py` — `run()` con overrides de sector/ciudad

**Files:**
- Modify: `agents/contabilidad/prospector-clientes-contables/agent.py`
- Test: `agents/contabilidad/prospector-clientes-contables/test_agent.py` (nuevo)

**Interfaces:**
- Produces: `run(config: dict, **overrides) -> str` — a diferencia de los otros 3, SÍ usa
  `overrides["sector"]`/`overrides["ciudad"]` (texto libre) cuando vienen del chatbot, en vez de
  `config["sectores_objetivo"]`/`config["ciudades"]`.

- [ ] **Step 1: Escribir el test que falla**

```python
# agents/contabilidad/prospector-clientes-contables/test_agent.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import agent  # noqa: E402


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
```

- [ ] **Step 2: Correr — debe fallar**

```bash
cd agents/contabilidad/prospector-clientes-contables && python -m pytest test_agent.py -v
```

Expected: FAIL — `agent.run` no existe todavía (y `build_system_prompt`/`build_user_prompt`
tampoco aceptan `sector`/`ciudad` como parámetros).

- [ ] **Step 3: Modificar `build_system_prompt`/`build_user_prompt` y agregar `run()`**

Reemplazar desde `def build_system_prompt` hasta el final del archivo:

```python
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
```

- [ ] **Step 4: Correr — debe pasar**

```bash
cd agents/contabilidad/prospector-clientes-contables && python -m pytest test_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Suite de este agente completa (incluye test_publish.py) + flake8**

```bash
cd agents/contabilidad/prospector-clientes-contables && python -m pytest -v
cd /path/al/repo && flake8 agents/contabilidad/prospector-clientes-contables/ --max-line-length=120
```

Expected: 5 passed (2 nuevos + 3 de `test_publish.py`).

- [ ] **Step 6: Commit**

```bash
git add agents/contabilidad/prospector-clientes-contables/agent.py agents/contabilidad/prospector-clientes-contables/test_agent.py
git commit -m "refactor: prospector-clientes-contables/agent.py acepta sector/ciudad on-demand"
```

---

### Task 5: `worker_handler.py` — despachar `tipo == "agente_contable"`

**Files:**
- Modify: `api/worker_handler.py`
- Test: `tests/test_worker_handler.py`

**Interfaces:**
- Consumes: `run(config, **overrides)` de los 4 agentes (Tasks 1-4), `publish(report)` de cada
  `publish.py` (ya existente desde el PR #33/#34).
- Produces: dispatch `tipo == "agente_contable"` con mensaje
  `{"tipo": "agente_contable", "agente": "<nombre-carpeta>", "job_id": "...", "overrides": {...}}`
  — usado por las tools del chatbot (Task 7-9).

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `tests/test_worker_handler.py`:

```python
def test_handler_dispatches_agente_contable(dynamodb_table, monkeypatch):
    from api.core import job_store
    import api.worker_handler as worker_handler

    calls = {}

    def _fake_process(body):
        calls["body"] = body

    monkeypatch.setattr(worker_handler, "_process_agente_contable", _fake_process)

    body = {"tipo": "agente_contable", "job_id": "j3", "agente": "dian-monitor", "overrides": {}}
    worker_handler.handler(_sqs_event(body), context=None)

    assert calls["body"]["agente"] == "dian-monitor"


def test_process_agente_contable_runs_agent_and_marks_job_done(dynamodb_table, monkeypatch):
    from api.core import job_store
    import api.worker_handler as worker_handler

    fake_agent_module = type("FakeAgent", (), {
        "load_config": staticmethod(lambda path: {"keywords": []}),
        "run": staticmethod(lambda config, **overrides: "reporte fake"),
    })
    fake_publish_module = type("FakePublish", (), {
        "publish": staticmethod(lambda report: None),
    })

    # OJO: los nombres son "agente_contable_<agente>_agent" y "..._publish" — ambos empiezan
    # con "agente_contable", así que un "agent" in name matchea los dos (bug real detectado en
    # autorevisión). Distinguir por el sufijo exacto, no por substring.
    monkeypatch.setattr(
        worker_handler, "_load_module",
        lambda path, name: fake_agent_module if name.endswith("_agent") else fake_publish_module,
    )

    body = {"job_id": "job-agente-1", "agente": "dian-monitor", "overrides": {}}
    worker_handler._process_agente_contable(body)

    job = job_store.get_job("job-agente-1")
    assert job["status"] == "done"
    assert job["agente"] == "dian-monitor"


def test_process_agente_contable_marks_job_error_on_failure(dynamodb_table, monkeypatch):
    from api.core import job_store
    import api.worker_handler as worker_handler

    def _raise(*a, **k):
        raise RuntimeError("groq se cayó")

    fake_agent_module = type("FakeAgent", (), {
        "load_config": staticmethod(lambda path: {}),
        "run": staticmethod(_raise),
    })

    monkeypatch.setattr(worker_handler, "_load_module", lambda path, name: fake_agent_module)

    body = {"job_id": "job-agente-2", "agente": "monitor-niif", "overrides": {}}
    worker_handler._process_agente_contable(body)

    job = job_store.get_job("job-agente-2")
    assert job["status"] == "error"
    assert "groq se cayó" in job["error"]
```

- [ ] **Step 2: Correr — debe fallar**

```bash
python -m pytest tests/test_worker_handler.py -v
```

Expected: FAIL — `worker_handler` no tiene `_process_agente_contable` ni `_load_module`.

- [ ] **Step 3: Implementar en `worker_handler.py`**

Agregar `import importlib.util` al bloque de imports (junto a `import json`, `import sys`).
Agregar la rama de dispatch en `handler()`:

```python
        elif tipo == "exogenas":
            _process_exogenas_batch(body)
        elif tipo == "agente_contable":
            _process_agente_contable(body)
        else:
```

Agregar al final del archivo:

```python
def _load_module(path: Path, unique_name: str):
    """Carga un módulo por ruta explícita bajo un nombre único en sys.modules — necesario
    porque los 4 agentes tienen cada uno su propio agent.py/publish.py: un import_module("agent")
    normal cachearía el PRIMER agente cargado en sys.modules["agent"] y lo devolvería para los
    siguientes, aunque sea un Lambda tibio reusado procesando dos agentes en records distintos
    de la misma invocación."""
    spec = importlib.util.spec_from_file_location(unique_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _process_agente_contable(body: dict) -> None:
    agente = body["agente"]
    job_id = body["job_id"]
    overrides = body.get("overrides", {})

    agent_dir = _ROOT / "agents" / "contabilidad" / agente
    agent_module = _load_module(agent_dir / "agent.py", f"agente_contable_{agente}_agent")

    try:
        config = agent_module.load_config(agent_dir / "config.yaml")
        report = agent_module.run(config, **overrides)
        publish_module = _load_module(agent_dir / "publish.py", f"agente_contable_{agente}_publish")
        publish_module.publish(report)
        job_store.put_job(job_id, "done", {"agente": agente})
    except Exception as exc:
        job_store.put_job(job_id, "error", {"agente": agente, "error": str(exc)})
```

- [ ] **Step 4: Correr — debe pasar**

```bash
python -m pytest tests/test_worker_handler.py -v
```

Expected: 8 passed (5 existentes + 3 nuevos).

- [ ] **Step 5: Suite completa + flake8**

```bash
python -m pytest -q
flake8 api/worker_handler.py --max-line-length=120
```

Expected: mismo conteo que baseline (202) + 3 nuevos en `test_worker_handler.py` = 205.

- [ ] **Step 6: Commit**

```bash
git add api/worker_handler.py tests/test_worker_handler.py
git commit -m "feat: worker_handler.py despacha tipo=agente_contable (invocación on-demand)"
```

---

### Task 6: `services/chatbot.py` — `_es_reciente()` (política de staleness)

**Files:**
- Modify: `services/chatbot.py`
- Test: `tests/test_chatbot_agentes.py` (nuevo)

**Interfaces:**
- Produces: `_es_reciente(fecha_generado: date, dias: int = 7) -> bool` — usado por Task 7.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_chatbot_agentes.py
"""Tests para las tools on-demand de agentes contables en services/chatbot.py."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.chatbot import _es_reciente  # noqa: E402


def test_es_reciente_hoy_es_fresco():
    assert _es_reciente(date.today()) is True


def test_es_reciente_dentro_del_limite():
    assert _es_reciente(date.today() - timedelta(days=7)) is True


def test_es_reciente_fuera_del_limite():
    assert _es_reciente(date.today() - timedelta(days=8)) is False


def test_es_reciente_limite_configurable():
    assert _es_reciente(date.today() - timedelta(days=10), dias=30) is True
```

- [ ] **Step 2: Correr — debe fallar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: FAIL (`ImportError: cannot import name '_es_reciente'`).

- [ ] **Step 3: Agregar `_es_reciente()` a `services/chatbot.py`**

Agregar después de los imports existentes (junto a `_fmt_cop`, sección "Tool implementations"):

```python
from datetime import date


def _es_reciente(fecha_generado: date, dias: int = 7) -> bool:
    """True si fecha_generado está dentro de los últimos `dias` días desde hoy."""
    return (date.today() - fecha_generado).days <= dias
```

- [ ] **Step 4: Correr — debe pasar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add services/chatbot.py tests/test_chatbot_agentes.py
git commit -m "feat: _es_reciente() — política de staleness para tools on-demand"
```

---

### Task 7: Tools `consultar_novedades_dian` / `consultar_novedades_niif`

**Files:**
- Modify: `services/chatbot.py`
- Test: `tests/test_chatbot_agentes.py`

**Interfaces:**
- Consumes: `_es_reciente()` (Task 6), tabla `novedades` (Postgres, ya existe desde el PR #33).
- Produces: `_tool_consultar_novedades_dian() -> str`, `_tool_consultar_novedades_niif() -> str`,
  helper interno `_disparar_agente(agente: str, overrides: dict | None = None) -> str` (job_id) —
  reutilizado por Tasks 8 y 9.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_chatbot_agentes.py`:

```python
from datetime import timedelta
from unittest.mock import MagicMock

import services.chatbot as chatbot  # noqa: E402


def test_disparar_agente_encola_sqs_y_devuelve_job_id(monkeypatch):
    fake_sqs = MagicMock()
    monkeypatch.setattr(chatbot.boto3, "client", lambda *a, **k: fake_sqs)
    monkeypatch.setenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/q")

    job_id = chatbot._disparar_agente("dian-monitor")

    assert job_id
    fake_sqs.send_message.assert_called_once()
    kwargs = fake_sqs.send_message.call_args.kwargs
    assert kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123/q"
    import json
    body = json.loads(kwargs["MessageBody"])
    assert body == {"tipo": "agente_contable", "agente": "dian-monitor", "job_id": job_id, "overrides": {}}


def test_tool_consultar_novedades_dian_devuelve_cache_si_fresco(monkeypatch):
    reciente = {
        "tipo": "dian", "titulo": "Novedades DIAN — semana del 2026-08-20",
        "resumen": "Resumen de prueba", "fecha_generado": date.today(),
    }
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: reciente)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda *a, **k: disparos.append(a) or "job-x")

    resultado = chatbot._tool_consultar_novedades_dian()

    assert "Resumen de prueba" in resultado
    assert disparos == []  # no disparó nada, el cache estaba fresco


def test_tool_consultar_novedades_dian_dispara_si_viejo(monkeypatch):
    vieja = {
        "tipo": "dian", "titulo": "vieja", "resumen": "vieja",
        "fecha_generado": date.today() - timedelta(days=30),
    }
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: vieja)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    resultado = chatbot._tool_consultar_novedades_dian()

    assert disparos == ["dian-monitor"]
    assert "arrancó" in resultado.lower() or "arranqué" in resultado.lower()


def test_tool_consultar_novedades_dian_dispara_si_no_existe(monkeypatch):
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: None)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    chatbot._tool_consultar_novedades_dian()

    assert disparos == ["dian-monitor"]


def test_tool_consultar_novedades_niif_usa_tipo_niif(monkeypatch):
    consultados = []
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: consultados.append(tipo) or None)
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: "job-x")

    chatbot._tool_consultar_novedades_niif()

    assert consultados == ["niif"]
```

- [ ] **Step 2: Correr — debe fallar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: FAIL — `_disparar_agente`/`_ultima_novedad`/`_tool_consultar_novedades_dian`/
`_tool_consultar_novedades_niif` no existen todavía.

- [ ] **Step 3: Implementar en `services/chatbot.py`**

Agregar `import boto3`, `import json` (si no está ya — `json` ya está importado; agregar
`import uuid` y `import os` si no están) al inicio del archivo. `os` ya está importado; agregar
`import boto3` y `import uuid`. Agregar después de `_es_reciente()`:

```python
def _disparar_agente(agente: str, overrides: dict | None = None) -> str:
    """Encola una corrida on-demand del agente correspondiente en SQS — mismo mecanismo que ya
    usan exogenas/renta (ver api/routers/exogenas.py). Lee la config de AWS de env vars directo
    (no core.config.get_settings()) porque este archivo puede correr fuera del contexto FastAPI
    (Streamlit legacy), donde 'api/' no está garantizado en sys.path."""
    job_id = str(uuid.uuid4())
    region = os.environ.get("AWS_REGION", "us-east-1")
    queue_url = os.environ.get("SQS_QUEUE_URL", "")
    sqs = boto3.client("sqs", region_name=region)
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "tipo": "agente_contable",
            "agente": agente,
            "job_id": job_id,
            "overrides": overrides or {},
        }),
    )
    return job_id


def _ultima_novedad(tipo: str) -> dict | None:
    """Última fila de `novedades` para ese tipo. None si no hay datos o la DB no está disponible
    — mismo criterio de degradación que api/routers/novedades.py."""
    from db.database import db_available, get_db

    if not db_available():
        return None

    from sqlalchemy import text

    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT tipo, titulo, resumen, fecha_generado FROM novedades "
                    "WHERE tipo = :tipo ORDER BY fecha_generado DESC LIMIT 1"
                ),
                {"tipo": tipo},
            ).mappings().fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _tool_consultar_novedades(tipo: str, nombre_amigable: str, agente: str) -> str:
    novedad = _ultima_novedad(tipo)
    if novedad and _es_reciente(novedad["fecha_generado"]):
        return f"{novedad['titulo']} ({novedad['fecha_generado']}):\n\n{novedad['resumen']}"
    _disparar_agente(agente)
    return (
        f"No tengo novedades {nombre_amigable} recientes (últimos 7 días) — ya arranqué la "
        f"búsqueda, va a tardar unos minutos. Revisá la página de Novedades en un rato."
    )


def _tool_consultar_novedades_dian() -> str:
    return _tool_consultar_novedades(tipo="dian", nombre_amigable="DIAN", agente="dian-monitor")


def _tool_consultar_novedades_niif() -> str:
    return _tool_consultar_novedades(tipo="niif", nombre_amigable="NIIF", agente="monitor-niif")
```

- [ ] **Step 4: Correr — debe pasar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: 9 passed (4 de `_es_reciente` + 5 nuevos).

- [ ] **Step 5: flake8**

```bash
flake8 services/chatbot.py tests/test_chatbot_agentes.py --max-line-length=120
```

- [ ] **Step 6: Commit**

```bash
git add services/chatbot.py tests/test_chatbot_agentes.py
git commit -m "feat: tools consultar_novedades_dian/niif — cache-first con disparo on-demand"
```

---

### Task 8: Tool `consultar_vencimientos_tributarios`

**Files:**
- Modify: `services/chatbot.py`
- Test: `tests/test_chatbot_agentes.py`

**Interfaces:**
- Consumes: `_disparar_agente()` (Task 7).
- Produces: `_tool_consultar_vencimientos_tributarios() -> str`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_chatbot_agentes.py`:

```python
def test_tool_vencimientos_devuelve_cache_si_hay_evento_proximo(monkeypatch):
    eventos = [
        {"id": "v1", "fecha": (date.today() + timedelta(days=10)).isoformat(), "titulo": "IVA bimestral"},
    ]
    monkeypatch.setattr(chatbot, "_leer_calendario", lambda: eventos)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda *a, **k: disparos.append(a) or "job-x")

    resultado = chatbot._tool_consultar_vencimientos_tributarios()

    assert "IVA bimestral" in resultado
    assert disparos == []


def test_tool_vencimientos_dispara_si_no_hay_evento_en_30_dias(monkeypatch):
    eventos = [
        {"id": "v1", "fecha": (date.today() + timedelta(days=60)).isoformat(), "titulo": "muy lejos"},
    ]
    monkeypatch.setattr(chatbot, "_leer_calendario", lambda: eventos)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    chatbot._tool_consultar_vencimientos_tributarios()

    assert disparos == ["vencimientos-tributarios"]


def test_tool_vencimientos_dispara_si_calendario_vacio(monkeypatch):
    monkeypatch.setattr(chatbot, "_leer_calendario", lambda: [])
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    chatbot._tool_consultar_vencimientos_tributarios()

    assert disparos == ["vencimientos-tributarios"]
```

- [ ] **Step 2: Correr — debe fallar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: FAIL — `_leer_calendario`/`_tool_consultar_vencimientos_tributarios` no existen.

- [ ] **Step 3: Implementar en `services/chatbot.py`**

```python
def _leer_calendario() -> list[dict]:
    """Lee el Calendario Tributario DIAN desde S3 — mismo bucket/key que
    api/routers/calendario.py. [] si no hay datos o S3 no está disponible. Usa el `boto3` ya
    importado a nivel de módulo (agregado en Task 7 para _disparar_agente)."""
    bucket = os.environ.get("S3_BUCKET_JOB_ARTIFACTS", "taxops-job-artifacts-prod")
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)
    try:
        obj = s3.get_object(Bucket=bucket, Key="config/calendario_2026.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return []


def _tool_consultar_vencimientos_tributarios() -> str:
    hoy = date.today()
    eventos = _leer_calendario()
    proximos = [
        e for e in eventos
        if 0 <= (date.fromisoformat(e["fecha"]) - hoy).days <= 30
    ]
    if proximos:
        proximos.sort(key=lambda e: e["fecha"])
        lineas = [f"- {e['fecha']}: {e['titulo']}" for e in proximos]
        return "Vencimientos tributarios en los próximos 30 días:\n" + "\n".join(lineas)
    _disparar_agente("vencimientos-tributarios")
    return (
        "No tengo vencimientos cargados para los próximos 30 días — ya arranqué la búsqueda, "
        "va a tardar unos minutos. Revisá el Calendario DIAN en un rato."
    )
```

- [ ] **Step 4: Correr — debe pasar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: 12 passed (9 anteriores + 3 nuevos).

- [ ] **Step 5: flake8**

```bash
flake8 services/chatbot.py tests/test_chatbot_agentes.py --max-line-length=120
```

- [ ] **Step 6: Commit**

```bash
git add services/chatbot.py tests/test_chatbot_agentes.py
git commit -m "feat: tool consultar_vencimientos_tributarios — cache-first con disparo on-demand"
```

---

### Task 9: Tool `buscar_leads_comerciales`

**Files:**
- Modify: `services/chatbot.py`
- Test: `tests/test_chatbot_agentes.py`

**Interfaces:**
- Consumes: `_disparar_agente()` (Task 7).
- Produces: `_tool_buscar_leads_comerciales(sector: str, ciudad: str) -> str`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_chatbot_agentes.py`:

```python
def test_tool_buscar_leads_devuelve_cache_si_existen(monkeypatch):
    leads = [
        {"empresa": "Restaurante A", "sector": "restaurantes", "ciudad": "Medellín",
         "contacto": "a@a.com", "fuente_url": "https://a.com", "fecha_generado": date.today()},
    ]
    monkeypatch.setattr(chatbot, "_leads_existentes", lambda sector, ciudad: leads)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda *a, **k: disparos.append(a) or "job-x")

    resultado = chatbot._tool_buscar_leads_comerciales("restaurantes", "Medellín")

    assert "Restaurante A" in resultado
    assert disparos == []


def test_tool_buscar_leads_dispara_si_no_existe_esa_combinacion(monkeypatch):
    monkeypatch.setattr(chatbot, "_leads_existentes", lambda sector, ciudad: [])
    disparos = []
    monkeypatch.setattr(
        chatbot, "_disparar_agente",
        lambda agente, overrides=None: disparos.append((agente, overrides)) or "job-x",
    )

    resultado = chatbot._tool_buscar_leads_comerciales("veterinarias", "Bucaramanga")

    assert disparos == [("prospector-clientes-contables", {"sector": "veterinarias", "ciudad": "Bucaramanga"})]
    assert "arrancó" in resultado.lower() or "arranqué" in resultado.lower()
```

- [ ] **Step 2: Correr — debe fallar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: FAIL — `_leads_existentes`/`_tool_buscar_leads_comerciales` no existen.

- [ ] **Step 3: Implementar en `services/chatbot.py`**

```python
def _leads_existentes(sector: str, ciudad: str) -> list[dict]:
    """Leads ya guardados para ese sector+ciudad exactos. [] si no hay o la DB no disponible."""
    from db.database import db_available, get_db

    if not db_available():
        return []

    from sqlalchemy import text

    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    "SELECT empresa, sector, ciudad, contacto, fuente_url, fecha_generado "
                    "FROM leads_comerciales WHERE sector = :sector AND ciudad = :ciudad "
                    "ORDER BY fecha_generado DESC"
                ),
                {"sector": sector, "ciudad": ciudad},
            ).mappings().fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def _tool_buscar_leads_comerciales(sector: str, ciudad: str) -> str:
    leads = _leads_existentes(sector, ciudad)
    if leads:
        lineas = [f"- {lead['empresa']} ({lead['contacto'] or 'sin contacto'})" for lead in leads]
        return f"Leads de {sector} en {ciudad}:\n" + "\n".join(lineas)
    _disparar_agente("prospector-clientes-contables", overrides={"sector": sector, "ciudad": ciudad})
    return (
        f"No tengo leads de {sector} en {ciudad} todavía — ya arranqué la búsqueda, va a tardar "
        f"unos minutos. Revisá la página de Leads en un rato."
    )
```

- [ ] **Step 4: Correr — debe pasar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: 14 passed (12 anteriores + 2 nuevos).

- [ ] **Step 5: flake8**

```bash
flake8 services/chatbot.py tests/test_chatbot_agentes.py --max-line-length=120
```

- [ ] **Step 6: Commit**

```bash
git add services/chatbot.py tests/test_chatbot_agentes.py
git commit -m "feat: tool buscar_leads_comerciales — cache-first con disparo on-demand"
```

---

### Task 10: Registrar las 4 tools en `TOOLS`/`_ejecutar_herramienta` — end-to-end

**Files:**
- Modify: `services/chatbot.py`
- Test: `tests/test_chatbot_agentes.py`

**Interfaces:**
- Consumes: las 4 `_tool_*` de Tasks 7-9.
- Produces: entradas nuevas en `TOOLS` (formato OpenAI-compatible) + ramas nuevas en
  `_ejecutar_herramienta()` — a partir de acá el chatbot puede invocarlas de verdad.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_chatbot_agentes.py`:

```python
def test_ejecutar_herramienta_despacha_las_4_tools_nuevas(monkeypatch):
    monkeypatch.setattr(chatbot, "_tool_consultar_novedades_dian", lambda: "dian ok")
    monkeypatch.setattr(chatbot, "_tool_consultar_novedades_niif", lambda: "niif ok")
    monkeypatch.setattr(chatbot, "_tool_consultar_vencimientos_tributarios", lambda: "venc ok")
    monkeypatch.setattr(
        chatbot, "_tool_buscar_leads_comerciales",
        lambda sector, ciudad: f"leads {sector} {ciudad} ok",
    )

    assert chatbot._ejecutar_herramienta("consultar_novedades_dian", {}, None) == "dian ok"
    assert chatbot._ejecutar_herramienta("consultar_novedades_niif", {}, None) == "niif ok"
    assert chatbot._ejecutar_herramienta("consultar_vencimientos_tributarios", {}, None) == "venc ok"
    assert chatbot._ejecutar_herramienta(
        "buscar_leads_comerciales", {"sector": "salud", "ciudad": "Cali"}, None
    ) == "leads salud Cali ok"


def test_tools_list_incluye_las_4_nuevas():
    nombres = {t["function"]["name"] for t in chatbot.TOOLS}
    assert {
        "consultar_novedades_dian", "consultar_novedades_niif",
        "consultar_vencimientos_tributarios", "buscar_leads_comerciales",
    } <= nombres
```

- [ ] **Step 2: Correr — debe fallar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: FAIL — `_ejecutar_herramienta` no reconoce los nombres nuevos, `TOOLS` no los tiene.

- [ ] **Step 3: Agregar a `TOOLS` (formato OpenAI-compatible)**

Agregar al final de la lista `TOOLS`, antes del `]` de cierre:

```python
    {
        "type": "function",
        "function": {
            "name": "consultar_novedades_dian",
            "description": (
                "Consulta las últimas novedades tributarias DIAN (resoluciones, circulares, "
                "decretos). Si no hay datos recientes, dispara una búsqueda nueva."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_novedades_niif",
            "description": (
                "Consulta las últimas novedades NIIF. Si no hay datos recientes, dispara una "
                "búsqueda nueva."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_vencimientos_tributarios",
            "description": (
                "Consulta los próximos vencimientos tributarios (IVA, renta, retención, etc.) "
                "en los siguientes 30 días. Si no hay datos, dispara una búsqueda nueva."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_leads_comerciales",
            "description": (
                "Busca empresas de un sector y ciudad que podrían necesitar servicios "
                "contables. Si no hay leads guardados para esa combinación, dispara una "
                "búsqueda nueva."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Sector económico, ej. 'restaurantes'"},
                    "ciudad": {"type": "string", "description": "Ciudad colombiana, ej. 'Medellín'"},
                },
                "required": ["sector", "ciudad"],
            },
        },
    },
```

- [ ] **Step 4: Agregar las ramas a `_ejecutar_herramienta()`**

```python
def _ejecutar_herramienta(nombre: str, args: dict, df: pd.DataFrame) -> str:
    if nombre == "consultar_iva_mes":
        return _tool_consultar_iva_mes(df, args.get("mes", ""))
    if nombre == "top_proveedores":
        return _tool_top_proveedores(df, args.get("n", 10))
    if nombre == "buscar_factura":
        return _tool_buscar_factura(df, args.get("query", ""))
    if nombre == "resumen_errores":
        return _tool_resumen_errores(df)
    if nombre == "resumen_general":
        return _tool_resumen_general(df)
    if nombre == "resumen_exogenas":
        return _tool_resumen_exogenas(df)
    if nombre == "top_agentes_retension":
        return _tool_top_agentes_retencion(df, args.get("n", 10))
    if nombre == "consultar_novedades_dian":
        return _tool_consultar_novedades_dian()
    if nombre == "consultar_novedades_niif":
        return _tool_consultar_novedades_niif()
    if nombre == "consultar_vencimientos_tributarios":
        return _tool_consultar_vencimientos_tributarios()
    if nombre == "buscar_leads_comerciales":
        return _tool_buscar_leads_comerciales(args.get("sector", ""), args.get("ciudad", ""))
    return f"Herramienta '{nombre}' no reconocida."
```

- [ ] **Step 5: Correr — debe pasar**

```bash
python -m pytest tests/test_chatbot_agentes.py -v
```

Expected: 16 passed (14 anteriores + 2 nuevos).

- [ ] **Step 6: Suite completa + flake8 + verificación de que las 7 tools viejas no se rompieron**

```bash
python -m pytest -q
flake8 services/chatbot.py --max-line-length=120
```

Expected: baseline (205 tras Task 5) + 16 de `test_chatbot_agentes.py` = 221 passed, 0
regresiones. Nota: `_ejecutar_herramienta` ahora recibe `df=None` en las 4 tools nuevas (no lo
usan) — confirmar que las 7 tools viejas, que sí dependen de `df`, siguen intactas (no se tocó su
código, solo se agregaron ramas nuevas al final del `if/elif`).

- [ ] **Step 7: Commit**

```bash
git add services/chatbot.py tests/test_chatbot_agentes.py
git commit -m "feat: registrar las 4 tools de agentes contables en TOOLS/_ejecutar_herramienta"
```

---

## Verificación final

1. `python -m pytest -q` — suite completa, 221 passed, 0 regresiones vs. baseline (205 tras
   Task 5).
2. `flake8 api/ pipeline/ services/ agents/_shared agents/contabilidad --max-line-length=120`
   (no usar `agents/` a secas — barre `agents/empleo/*.venv`, fuera de alcance, ver PR #33/#34).
3. `cd taxops-web && npx tsc --noEmit && npm run lint` — este plan no toca el frontend, no debería
   haber diffs ahí; correr igual como chequeo de que nada se rompió.
4. `terraform plan` — este plan no toca `infra/`, no debería haber diff de Terraform en absoluto.
5. Prueba manual end-to-end (requiere `DATABASE_URL`/`SQS_QUEUE_URL`/`GROQ_API_KEY` reales, fuera
   del sandbox de desarrollo): preguntarle al chatbot "¿hay novedades de la DIAN?" con la tabla
   `novedades` vacía, confirmar que dispara el job (`gh run list` o revisar `taxops-jobs-prod` en
   DynamoDB), esperar a que termine, y volver a preguntar — la segunda vez debe responder desde
   cache sin disparar nada nuevo.
