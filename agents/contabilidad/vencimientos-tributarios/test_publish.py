import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parents[2]))  # agents/
from _shared.testing import cargar_modulo_agente  # noqa: E402

publish_mod = cargar_modulo_agente(Path(__file__).parent, "publish")
_BUCKET = publish_mod._BUCKET
_KEY = publish_mod._KEY
extract_eventos = publish_mod.extract_eventos
merge_eventos = publish_mod.merge_eventos
publish = publish_mod.publish

_VALID_REPORT = """
## Vencimientos

```json
[
  {"id": "v1", "fecha": "2026-09-15", "titulo": "IVA bimestral", "descripcion": "desc",
   "tipo": "iva", "urgencia": "alta"}
]
```
"""


def test_extract_eventos_valid():
    eventos = extract_eventos(_VALID_REPORT)
    assert eventos[0]["id"] == "v1"


def test_extract_eventos_missing_field_raises():
    bad = '```json\n[{"id": "v1", "fecha": "2026-09-15"}]\n```'
    with pytest.raises(ValueError, match="campos obligatorios"):
        extract_eventos(bad)


def test_extract_eventos_no_block_raises():
    with pytest.raises(ValueError, match="no contiene un bloque"):
        extract_eventos("sin bloque json")


def test_merge_eventos_updates_by_id_preserves_others():
    existentes = [
        {"id": "v1", "fecha": "2026-01-01", "titulo": "viejo"},
        {"id": "v2", "fecha": "2026-02-01", "titulo": "otro evento, no tocado"},
    ]
    nuevos = [{"id": "v1", "fecha": "2026-09-15", "titulo": "IVA bimestral actualizado"}]

    merged = merge_eventos(existentes, nuevos)

    assert len(merged) == 2
    v1 = next(e for e in merged if e["id"] == "v1")
    assert v1["titulo"] == "IVA bimestral actualizado"
    assert any(e["id"] == "v2" for e in merged)  # v2 se preservó intacto


def test_publish_repairs_report_missing_json_block(monkeypatch):
    """El modelo a veces genera el reporte completo pero se olvida de cerrar el bloque ```json```
    (visto en producción el 2026-08-25). publish() debe recuperarse con un llamado de reparación
    en vez de crashear el job entero."""
    import agents._shared.agent_core as agent_core

    reparado = '```json\n[{"id": "v1", "fecha": "2026-09-15", "titulo": "t", "descripcion": "d", "tipo": "iva", "urgencia": "alta"}]\n```'  # noqa: E501
    monkeypatch.setattr(agent_core, "run_llm_only", lambda *a, **k: reparado)

    eventos = publish_mod._repair_missing_json_block("## Vencimientos\n\nIVA bimestral el 15 de septiembre.")

    assert eventos[0]["id"] == "v1"


@mock_aws
def test_publish_end_to_end_writes_merged_to_s3():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=_BUCKET)
    import json
    s3.put_object(
        Bucket=_BUCKET, Key=_KEY,
        Body=json.dumps([{"id": "v2", "fecha": "2026-02-01", "titulo": "existente"}]).encode(),
    )

    n = publish(_VALID_REPORT)

    assert n == 1
    obj = s3.get_object(Bucket=_BUCKET, Key=_KEY)
    data = json.loads(obj["Body"].read())
    assert len(data) == 2  # el existente + el nuevo, ninguno se perdió
