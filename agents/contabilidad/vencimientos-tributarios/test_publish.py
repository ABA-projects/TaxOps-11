import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent))
from publish import _BUCKET, _KEY, extract_eventos, merge_eventos, publish  # noqa: E402

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
