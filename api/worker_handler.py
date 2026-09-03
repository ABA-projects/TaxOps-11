"""api/worker_handler.py — Lambda handler triggered by SQS for renta document jobs.

Consumes the batch messages published by `routers/renta_documentos.py::upload_documentos`
(one SQS message = one full `upload_documentos` batch, see message contract in
docs/superpowers/plans/2026-08-05-taxops11-aws-migration.md, Chunk 2, Task 2.3) and runs
`services.renta.job_processor.process_documento_job` for every document in the batch,
then updates the parent job's aggregate progress in DynamoDB (via `job_store`).

Imports mirror `services/renta/job_processor.py` (absolute `api.core`/`services.*`
from the repo root) rather than the short `core`-relative style used inside
`api/routers/*.py` — this file has no guarantee of running with `api/` as its cwd
(unlike `uvicorn main:app` invoked from `api/`), so the same sys.path bootstrap used
by `api/main.py` is applied here to make the repo root importable regardless of how
the Lambda runtime resolves this module.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.core import job_store  # noqa: E402

log = logging.getLogger("taxops.worker")


def handler(event: dict, context: Any = None) -> None:
    """Lambda entry point — one invocation may carry several SQS records."""
    for record in event["Records"]:
        body = json.loads(record["body"])
        # mensajes viejos (ya en vuelo) no tienen "tipo" — default preserva compatibilidad
        tipo = body.get("tipo", "renta")
        try:
            if tipo == "renta":
                _process_renta_batch(body)
            elif tipo == "exogenas":
                _process_exogenas_batch(body)
            elif tipo == "agente_contable":
                _process_agente_contable(body)
            else:
                log.error("Tipo de mensaje SQS desconocido: %s", tipo)
        except Exception:
            # Un record fallando no debe abortar el resto del batch ni forzar el
            # reintento de records ya procesados exitosamente en esta misma invocación.
            log.error("worker_handler: fallo procesando record (tipo=%s): %s", tipo, body, exc_info=True)


def _process_exogenas_batch(body: dict) -> None:
    from services.exogenas.job_processor import process_exogenas_job

    process_exogenas_job(
        job_id=body["job_id"],
        org_id=body["org_id"],
        s3_keys=body["s3_keys"],
    )


def _process_renta_batch(body: dict) -> None:
    import logging

    from services.renta.job_processor import process_documento_job

    log = logging.getLogger("taxops.renta")

    job_id = body["job_id"]
    contrib_id = body["contrib_id"]
    org_id = body["org_id"]
    año = body["año"]
    documentos = body["documentos"]

    total = len(documentos)
    for i, doc in enumerate(documentos, 1):
        # process_documento_job already catches its own errors internally and
        # records them on the per-document job (status="error"), so it should
        # not raise under normal operation. This try/except is a second line
        # of defense: if it *does* raise unexpectedly, one bad document must
        # not abort the rest of the batch or the whole Lambda invocation.
        try:
            process_documento_job(
                job_id=f"{job_id}_{i}",
                doc_id=doc["doc_id"],
                s3_key=doc["s3_key"],
                filename=doc["filename"],
                mime_type=doc["mime_type"],
                contrib_id=contrib_id,
                org_id=org_id,
                año=año,
            )
        except Exception as exc:
            log.error(
                "worker_handler: process_documento_job raised for doc %s (job %s): %s",
                doc.get("doc_id"), job_id, exc, exc_info=True,
            )

        job = job_store.get_job(job_id) or {}
        job["completados"] = i
        job["progreso"] = round(i / total * 100)
        job_store.put_job(job_id, job.get("status", "processing"), job)

    job = job_store.get_job(job_id) or {}
    job["status"] = "done"
    job_store.put_job(job_id, "done", job)


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

    try:
        # No se usa agent_module.load_config: esa función hace sys.exit() si falta el
        # archivo (pensada para un CLI, no para un worker de larga vida) — SystemExit
        # es BaseException, así que un `except Exception` no la captura y mataría el
        # proceso del Lambda en vez de dejar el job en "error". Se carga el YAML acá
        # directo para que cualquier fallo sea una excepción normal.
        config_path = agent_dir / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Falta {config_path}")
        config = yaml.safe_load(config_path.read_text())

        agent_module = _load_module(agent_dir / "agent.py", f"agente_contable_{agente}_agent")
        report = agent_module.run(config, **overrides)
        publish_module = _load_module(agent_dir / "publish.py", f"agente_contable_{agente}_publish")
        publish_module.publish(report)
        job_store.put_job(job_id, "done", {"agente": agente})
    except Exception as exc:
        log.error(
            "worker_handler: _process_agente_contable falló para agente %s (job %s): %s",
            agente, job_id, exc, exc_info=True,
        )
        job_store.put_job(job_id, "error", {"agente": agente, "error": str(exc)})
