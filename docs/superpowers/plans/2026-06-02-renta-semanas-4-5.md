# Renta Semanas 4-5 — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar entrada manual de datos tributarios, cédulas separadas (dividendos + ganancias ocasionales), validaciones bloqueantes/suaves, editor post-cálculo y generación de borrador PDF Formulario 210 DIAN para el módulo de renta personas naturales.

**Architecture:** Backend FastAPI en Cloud Run + frontend Next.js 15 en Vercel. Migración Alembic aditiva (ALTER TABLE ADD COLUMN IF NOT EXISTS). Motor de cálculo en `services/renta/tax_engine.py`. PDF generado server-side con WeasyPrint y servido como StreamingResponse.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy · Alembic · WeasyPrint · Next.js 15 · TypeScript · Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-06-02-renta-semanas-4-5-design.md`

---

## Observaciones sobre el código existente (leer antes de implementar)

- Las migraciones están en `api/alembic/versions/`, NO en `db/migrations/`.
- La tabla `renta_declaraciones` ya tiene `rentas_capital`, `rentas_no_laborales`, `dividendos`, `ganancias_ocasionales`. La migración 005 agrega los campos que FALTAN.
- Usar `dividendos` (ya existente) para dividendos_gravados y `ganancias_ocasionales` (ya existente) para ganancia_ocasional — no crear columnas duplicadas.
- `upsert_declaracion()` está en `db/database_renta.py` y usa `CAST(:param AS jsonb)` para JSONB.
- Los tests de pytest corren desde la raíz: `python -m pytest tests/`.
- El frontend usa `useApi()` hook (`taxops-web/lib/api.ts`) — `get`, `post`, `patch`, `del`.

---

## Chunk 1: Base de datos y schemas

### Task 1: Migración Alembic 005

**Files:**
- Create: `api/alembic/versions/005_renta_cedulas.py`

- [ ] **Step 1: Crear la migración**

```python
# api/alembic/versions/005_renta_cedulas.py
"""Add new fields to renta_declaraciones for Semana 4.

Revision ID: 005
Revises: 004
Create Date: 2026-06-02
"""
from __future__ import annotations
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [
        ("aportes_pension",    "NUMERIC(18,2)", "0"),
        ("afc_fvp",            "NUMERIC(18,2)", "0"),
        ("intereses_vivienda", "NUMERIC(18,2)", "0"),
        ("medicina_prepagada", "NUMERIC(18,2)", "0"),
        ("dependientes",       "INTEGER",        "0"),
        ("tipo_ganancia",      "TEXT",           "NULL"),
        ("pasivos",            "NUMERIC(18,2)", "0"),
        ("ajuste_manual",      "JSONB",          "NULL"),
    ]
    for col, tipo, default in cols:
        default_sql = f"DEFAULT {default}" if default != "NULL" else ""
        op.execute(
            f"ALTER TABLE renta_declaraciones "
            f"ADD COLUMN IF NOT EXISTS {col} {tipo} {default_sql};"
        )


def downgrade() -> None:
    for col in [
        "aportes_pension", "afc_fvp", "intereses_vivienda",
        "medicina_prepagada", "dependientes", "tipo_ganancia",
        "pasivos", "ajuste_manual",
    ]:
        op.execute(
            f"ALTER TABLE renta_declaraciones DROP COLUMN IF EXISTS {col};"
        )
```

- [ ] **Step 2: Verificar que la migración aplica localmente (si hay DB local)**

```bash
cd api && alembic upgrade head
```
Si no hay DB local, continuar — la migración corre automáticamente en startup de Cloud Run.

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/005_renta_cedulas.py
git commit -m "feat(renta): migración 005 — campos S4 (aportes_pension, afc_fvp, pasivos, ajuste_manual, etc.)"
```

---

### Task 2: Extender schemas_renta.py

**Files:**
- Modify: `api/schemas_renta.py`

- [ ] **Step 1: Agregar campos nuevos a `DeclaracionOut` y crear `DatosTributariosIn`**

En `api/schemas_renta.py`, localizar la clase `DeclaracionOut` y agregar los campos nuevos:

```python
class DeclaracionOut(BaseModel):
    id: UUID
    contribuyente_id: UUID
    año_gravable: int
    patrimonio_bruto: float
    patrimonio_liquido: float
    ingresos_laborales: float
    rentas_capital: float
    rentas_no_laborales: float
    dividendos: float
    ganancias_ocasionales: float
    rentas_exentas: float
    deducciones: float
    retenciones: float
    impuesto_cargo: float
    saldo_pagar: float
    saldo_favor: float
    # Campos nuevos Semana 4:
    aportes_pension: float = 0.0
    afc_fvp: float = 0.0
    intereses_vivienda: float = 0.0
    medicina_prepagada: float = 0.0
    dependientes: int = 0
    tipo_ganancia: Optional[str] = None
    pasivos: float = 0.0
    ajuste_manual: Optional[dict[str, Any]] = None
    estado: str
    pdf_path: Optional[str]
    inconsistencias: list[Any]
    detalle_calculo: dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True
```

Agregar al final del archivo el schema `DatosTributariosIn`:

```python
# ─── Datos tributarios (PATCH /datos) ─────────────────────────────────────────

class DatosTributariosIn(BaseModel):
    ingresos_laborales: Optional[float] = None
    rentas_capital: Optional[float] = None
    rentas_no_laborales: Optional[float] = None
    aportes_pension: Optional[float] = None
    afc_fvp: Optional[float] = None
    retenciones: Optional[float] = None
    intereses_vivienda: Optional[float] = None
    medicina_prepagada: Optional[float] = None
    dependientes: Optional[int] = None
    dividendos: Optional[float] = None
    ganancias_ocasionales: Optional[float] = None
    tipo_ganancia: Optional[str] = Field(None, pattern=r"^(venta_activo|herencia|loteria)$")
    pasivos: Optional[float] = None
    patrimonio_bruto: Optional[float] = None
    ajuste_manual: Optional[dict[str, Any]] = None
    estado: Optional[str] = Field(None, pattern=r"^(borrador|revision|presentado)$")
```

- [ ] **Step 2: Commit**

```bash
git add api/schemas_renta.py
git commit -m "feat(renta): DeclaracionOut + DatosTributariosIn con campos S4"
```

---

### Task 3: Extender upsert_declaracion() en database_renta.py

**Files:**
- Modify: `db/database_renta.py`

- [ ] **Step 1: Extender upsert_declaracion() para incluir campos nuevos**

Localizar la función `upsert_declaracion()` en `db/database_renta.py`. El UPDATE SET debe incluir los campos nuevos. Añadir al SQL existente:

```python
def upsert_declaracion(contribuyente_id: str, año: int, data: dict) -> dict:
    from sqlalchemy import text
    from db.database import get_db
    with get_db() as db:
        row = db.execute(
            text("""
                INSERT INTO renta_declaraciones (
                    contribuyente_id, año_gravable,
                    patrimonio_bruto, patrimonio_liquido,
                    ingresos_laborales, rentas_capital, rentas_no_laborales,
                    dividendos, ganancias_ocasionales,
                    rentas_exentas, deducciones, retenciones,
                    impuesto_cargo, saldo_pagar, saldo_favor, estado,
                    inconsistencias, detalle_calculo,
                    aportes_pension, afc_fvp, intereses_vivienda,
                    medicina_prepagada, dependientes, tipo_ganancia,
                    pasivos, ajuste_manual
                ) VALUES (
                    :cid, :año,
                    :patrimonio_bruto, :patrimonio_liquido,
                    :ingresos_laborales, :rentas_capital, :rentas_no_laborales,
                    :dividendos, :ganancias_ocasionales,
                    :rentas_exentas, :deducciones, :retenciones,
                    :impuesto_cargo, :saldo_pagar, :saldo_favor, :estado,
                    CAST(:inconsistencias AS jsonb), CAST(:detalle_calculo AS jsonb),
                    :aportes_pension, :afc_fvp, :intereses_vivienda,
                    :medicina_prepagada, :dependientes, :tipo_ganancia,
                    :pasivos, CAST(:ajuste_manual AS jsonb)
                )
                ON CONFLICT (contribuyente_id, año_gravable) DO UPDATE SET
                    patrimonio_bruto      = EXCLUDED.patrimonio_bruto,
                    patrimonio_liquido    = EXCLUDED.patrimonio_liquido,
                    ingresos_laborales    = EXCLUDED.ingresos_laborales,
                    rentas_capital        = EXCLUDED.rentas_capital,
                    rentas_no_laborales   = EXCLUDED.rentas_no_laborales,
                    dividendos            = EXCLUDED.dividendos,
                    ganancias_ocasionales = EXCLUDED.ganancias_ocasionales,
                    rentas_exentas        = EXCLUDED.rentas_exentas,
                    deducciones           = EXCLUDED.deducciones,
                    retenciones           = EXCLUDED.retenciones,
                    impuesto_cargo        = EXCLUDED.impuesto_cargo,
                    saldo_pagar           = EXCLUDED.saldo_pagar,
                    saldo_favor           = EXCLUDED.saldo_favor,
                    estado                = EXCLUDED.estado,
                    inconsistencias       = EXCLUDED.inconsistencias,
                    detalle_calculo       = EXCLUDED.detalle_calculo,
                    aportes_pension       = EXCLUDED.aportes_pension,
                    afc_fvp               = EXCLUDED.afc_fvp,
                    intereses_vivienda    = EXCLUDED.intereses_vivienda,
                    medicina_prepagada    = EXCLUDED.medicina_prepagada,
                    dependientes          = EXCLUDED.dependientes,
                    tipo_ganancia         = EXCLUDED.tipo_ganancia,
                    pasivos               = EXCLUDED.pasivos,
                    ajuste_manual         = EXCLUDED.ajuste_manual,
                    updated_at            = NOW()
                RETURNING *
            """),
            {
                "cid":                 contribuyente_id,
                "año":                 año,
                "patrimonio_bruto":    data.get("patrimonio_bruto", 0),
                "patrimonio_liquido":  data.get("patrimonio_liquido", 0),
                "ingresos_laborales":  data.get("ingresos_laborales", 0),
                "rentas_capital":      data.get("rentas_capital", 0),
                "rentas_no_laborales": data.get("rentas_no_laborales", 0),
                "dividendos":          data.get("dividendos", 0),
                "ganancias_ocasionales": data.get("ganancias_ocasionales", 0),
                "rentas_exentas":      data.get("rentas_exentas", 0),
                "deducciones":         data.get("deducciones", 0),
                "retenciones":         data.get("retenciones", 0),
                "impuesto_cargo":      data.get("impuesto_cargo", 0),
                "saldo_pagar":         data.get("saldo_pagar", 0),
                "saldo_favor":         data.get("saldo_favor", 0),
                "estado":              data.get("estado", "borrador"),
                "inconsistencias":     json.dumps(data.get("inconsistencias", [])),
                "detalle_calculo":     json.dumps(data.get("detalle_calculo", {})),
                "aportes_pension":     data.get("aportes_pension", 0),
                "afc_fvp":             data.get("afc_fvp", 0),
                "intereses_vivienda":  data.get("intereses_vivienda", 0),
                "medicina_prepagada":  data.get("medicina_prepagada", 0),
                "dependientes":        data.get("dependientes", 0),
                "tipo_ganancia":       data.get("tipo_ganancia"),
                "pasivos":             data.get("pasivos", 0),
                "ajuste_manual":       json.dumps(data.get("ajuste_manual")) if data.get("ajuste_manual") else None,
            },
        )
        return dict(row.mappings().one())
```

También agregar función `patch_datos_declaracion()` para el endpoint PATCH que solo actualiza los campos enviados:

```python
def patch_datos_declaracion(contribuyente_id: str, año: int, data: dict) -> dict:
    """Upsert parcial — solo actualiza los campos presentes en data."""
    # Mapeo de campos permitidos
    ALLOWED = {
        "ingresos_laborales", "rentas_capital", "rentas_no_laborales",
        "aportes_pension", "afc_fvp", "retenciones", "intereses_vivienda",
        "medicina_prepagada", "dependientes", "dividendos", "ganancias_ocasionales",
        "tipo_ganancia", "pasivos", "patrimonio_bruto", "ajuste_manual", "estado",
    }
    campos = {k: v for k, v in data.items() if k in ALLOWED and v is not None}
    if not campos:
        # Nada que actualizar — devolver la declaración existente o crear vacía
        from db.database_renta import get_declaracion
        existing = get_declaracion(contribuyente_id, año)
        if existing:
            return existing
        return upsert_declaracion(contribuyente_id, año, {"estado": "borrador"})

    # Construir SET dinámico
    from sqlalchemy import text
    from db.database import get_db
    import json

    set_parts = []
    params: dict = {"cid": contribuyente_id, "año": año}
    jsonb_fields = {"ajuste_manual"}

    for k, v in campos.items():
        if k in jsonb_fields:
            set_parts.append(f"{k} = CAST(:{k} AS jsonb)")
            params[k] = json.dumps(v)
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v

    set_parts.append("updated_at = NOW()")
    set_sql = ", ".join(set_parts)

    with get_db() as db:
        row = db.execute(
            text(f"""
                INSERT INTO renta_declaraciones (contribuyente_id, año_gravable, estado)
                VALUES (:cid, :año, 'borrador')
                ON CONFLICT (contribuyente_id, año_gravable) DO UPDATE SET {set_sql}
                RETURNING *
            """),
            params,
        )
        return dict(row.mappings().one())
```

- [ ] **Step 2: Verificar que `get_declaracion()` existe (función para leer la declaración existente)**

Si no existe, agregar al mismo archivo:

```python
def get_declaracion(contribuyente_id: str, año: int) -> dict | None:
    from sqlalchemy import text
    from db.database import get_db
    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM renta_declaraciones WHERE contribuyente_id = :cid AND año_gravable = :año"),
            {"cid": contribuyente_id, "año": año},
        ).one_or_none()
        return dict(row._mapping) if row else None
```

- [ ] **Step 3: Commit**

```bash
git add db/database_renta.py
git commit -m "feat(renta): upsert_declaracion + patch_datos_declaracion con campos S4"
```

---

## Chunk 2: Motor de cálculo

### Task 4: Actualizar tax_engine.py

**Files:**
- Modify: `services/renta/tax_engine.py`
- Create: `tests/test_renta_engine.py`

- [ ] **Step 1: Escribir tests que deben FALLAR con el motor actual**

Crear `tests/test_renta_engine.py`:

```python
"""Tests para services/renta/tax_engine.py — Semana 4."""
import pytest
from unittest.mock import patch, MagicMock


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_reglas(uvt=49799):
    from services.renta.tax_engine import _tabla_art241_default
    return {
        "uvt": uvt,
        "tabla_art241": _tabla_art241_default(),
    }


# ── Test límite 40% / 1.340 UVT (Art. 336 ET) ───────────────────────────────

def test_limite_40pct_aplicado():
    """Rentas exentas brutas > 40% ingresos → se recortan al 40%."""
    from services.renta.tax_engine import _consolidar_datos
    # Ingresos laborales 100M, exentas brutas = 50M (> 40M = 40%)
    docs = [{
        "id": "1", "categoria": "ingresos", "confianza": 0.9,
        "datos": {"total_ingresos": 100_000_000, "total_retencion": 0},
    }]
    reglas = _make_reglas()
    # Sobreescribir con datos que fuercen exentas altas
    result = _consolidar_datos(docs, reglas)
    ingresos_netos = result["ingresos_laborales"] - result.get("aportes_pension", 0)
    tope = min(ingresos_netos * 0.40, 1340 * 49799)
    assert result["rentas_exentas"] <= tope + 1  # +1 por redondeo float


def test_limite_1340_uvt():
    """Con ingresos muy altos, el tope es 1.340 UVT, no 40%."""
    from services.renta.tax_engine import _consolidar_datos
    uvt = 49799
    # Ingresos de 1.000 UVT × uvt → 40% = 400 UVT, pero el mínimo entre 400 y 1340 es 400
    # Con ingresos de 5.000 UVT → 40% = 2000 UVT > 1340 → tope = 1340 UVT
    docs = [{
        "id": "1", "categoria": "ingresos", "confianza": 0.9,
        "datos": {"total_ingresos": 5000 * uvt, "total_retencion": 0},
    }]
    result = _consolidar_datos(docs, _make_reglas(uvt))
    assert result["rentas_exentas"] <= 1340 * uvt + 1


# ── Test cédula dividendos (Art. 242 ET) ────────────────────────────────────

def test_dividendos_bajo_300_uvt_exentos():
    """Dividendos ≤ 300 UVT → impuesto_dividendos = 0."""
    from services.renta.tax_engine import _calcular_impuesto_dividendos
    uvt = 49799
    dividendos = 299 * uvt  # justo por debajo del límite
    assert _calcular_impuesto_dividendos(dividendos, uvt) == 0.0


def test_dividendos_sobre_300_uvt_gravados():
    """Dividendos > 300 UVT → impuesto = (exceso) × 15%."""
    from services.renta.tax_engine import _calcular_impuesto_dividendos
    uvt = 49799
    dividendos = 400 * uvt  # 100 UVT sobre el límite
    expected = round(100 * uvt * 0.15, 2)
    assert _calcular_impuesto_dividendos(dividendos, uvt) == expected


# ── Test ganancias ocasionales (Art. 299-316 ET) ────────────────────────────

def test_ganancia_venta_activo_10pct():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(10_000_000, "venta_activo") == 1_000_000.0


def test_ganancia_herencia_10pct():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(10_000_000, "herencia") == 1_000_000.0


def test_ganancia_loteria_20pct():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(10_000_000, "loteria") == 2_000_000.0


def test_ganancia_negativa_es_cero():
    from services.renta.tax_engine import _calcular_impuesto_ocasional
    assert _calcular_impuesto_ocasional(-1_000_000, "venta_activo") == 0.0


# ── Test patrimonio líquido ──────────────────────────────────────────────────

def test_patrimonio_liquido_con_pasivos():
    """patrimonio_liquido = patrimonio_bruto - pasivos (mín 0)."""
    from services.renta.tax_engine import _calcular_patrimonio_liquido
    assert _calcular_patrimonio_liquido(100_000_000, 30_000_000) == 70_000_000.0


def test_patrimonio_liquido_nunca_negativo():
    from services.renta.tax_engine import _calcular_patrimonio_liquido
    assert _calcular_patrimonio_liquido(10_000_000, 50_000_000) == 0.0


# ── Test overrides ajuste_manual ─────────────────────────────────────────────

def test_ajuste_manual_override_ingresos():
    """ajuste_manual sobreescribe el valor consolidado antes de calcular."""
    from services.renta.tax_engine import _aplicar_overrides
    consolidado = {"ingresos_laborales": 50_000_000, "retenciones": 0}
    ajuste = {"ingresos_laborales": 80_000_000}
    result = _aplicar_overrides(consolidado, ajuste)
    assert result["ingresos_laborales"] == 80_000_000


def test_ajuste_manual_key_invalida_ignorada():
    from services.renta.tax_engine import _aplicar_overrides
    consolidado = {"ingresos_laborales": 50_000_000}
    ajuste = {"campo_inventado": 999}
    result = _aplicar_overrides(consolidado, ajuste)
    assert "campo_inventado" not in result


def test_ajuste_manual_none_no_cambia_nada():
    from services.renta.tax_engine import _aplicar_overrides
    consolidado = {"ingresos_laborales": 50_000_000}
    result = _aplicar_overrides(consolidado, None)
    assert result["ingresos_laborales"] == 50_000_000
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
python -m pytest tests/test_renta_engine.py -v 2>&1 | head -40
```
Esperado: `ImportError` o `FAILED` — las funciones `_calcular_impuesto_dividendos`, `_calcular_impuesto_ocasional`, `_calcular_patrimonio_liquido`, `_aplicar_overrides` no existen aún.

- [ ] **Step 3: Implementar las funciones nuevas en tax_engine.py**

Agregar al final de `services/renta/tax_engine.py` (antes del bloque `_detectar_inconsistencias`):

```python
# ─── Cédula dividendos (Art. 242 ET) ─────────────────────────────────────────

def _calcular_impuesto_dividendos(dividendos: float, uvt: float) -> float:
    limite = 300 * uvt
    if dividendos <= limite:
        return 0.0
    return round((dividendos - limite) * 0.15, 2)


# ─── Ganancias ocasionales (Art. 299-316 ET) ──────────────────────────────────

def _calcular_impuesto_ocasional(ganancia: float, tipo: str | None) -> float:
    if ganancia <= 0:
        return 0.0
    tarifa = 0.20 if tipo == "loteria" else 0.10
    return round(ganancia * tarifa, 2)


# ─── Patrimonio líquido ───────────────────────────────────────────────────────

def _calcular_patrimonio_liquido(bruto: float, pasivos: float) -> float:
    return max(0.0, bruto - pasivos)


# ─── Overrides manuales ───────────────────────────────────────────────────────

_OVERRIDE_ALLOWED = frozenset({
    "ingresos_laborales", "rentas_capital", "rentas_no_laborales",
    "dividendos", "ganancias_ocasionales", "rentas_exentas", "deducciones",
    "retenciones", "patrimonio_bruto", "patrimonio_liquido",
    "aportes_pension", "afc_fvp", "intereses_vivienda", "medicina_prepagada", "pasivos",
})


def _aplicar_overrides(consolidado: dict, ajuste_manual: dict | None) -> dict:
    if not ajuste_manual:
        return consolidado
    result = dict(consolidado)
    aplicados = []
    for k, v in ajuste_manual.items():
        if k not in _OVERRIDE_ALLOWED:
            continue
        # Rechazar negativos en campos que no los admiten
        if k != "rentas_no_laborales" and isinstance(v, (int, float)) and v < 0:
            continue
        result[k] = float(v)
        aplicados.append(k)
    result["_ajustados_manualmente"] = aplicados
    return result
```

Modificar la función `calcular_declaracion()` para usar las nuevas funciones. Reemplazar el bloque de cálculo final:

```python
def calcular_declaracion(contribuyente_id: str, año: int, ajuste_manual: dict | None = None) -> dict:
    from sqlalchemy import text
    from db.database import get_db

    with get_db() as db:
        reglas = _cargar_reglas(db, año)
        docs = _cargar_documentos(db, contribuyente_id)
        # Cargar datos guardados previamente (formulario de datos tributarios)
        datos_guardados = _cargar_datos_guardados(db, contribuyente_id, año)

    consolidado = _consolidar_datos(docs, reglas, datos_guardados)

    # Aplicar overrides del editor post-cálculo
    override = ajuste_manual or datos_guardados.get("ajuste_manual")
    consolidado = _aplicar_overrides(consolidado, override)

    uvt = reglas.get("uvt", 49799)

    # Patrimonio líquido
    pasivos = float(datos_guardados.get("pasivos", 0))
    patrimonio_liquido = _calcular_patrimonio_liquido(consolidado["patrimonio_bruto"], pasivos)

    impuesto_general = _calcular_impuesto(consolidado["renta_gravable"], reglas)
    impuesto_dividendos = _calcular_impuesto_dividendos(consolidado.get("dividendos", 0), uvt)
    impuesto_ocasional = _calcular_impuesto_ocasional(
        consolidado.get("ganancias_ocasionales", 0),
        datos_guardados.get("tipo_ganancia"),
    )

    impuesto_cargo = round(impuesto_general + impuesto_dividendos + impuesto_ocasional, 2)
    retenciones = consolidado["retenciones"]
    saldo_pagar = max(0.0, impuesto_cargo - retenciones)
    saldo_favor = max(0.0, retenciones - impuesto_cargo)

    inconsistencias = _detectar_inconsistencias(consolidado, docs)

    detalle = {
        "uvt":                    uvt,
        "consolidado":            consolidado,
        "impuesto_cedula_general": impuesto_general,
        "impuesto_dividendos":    impuesto_dividendos,
        "impuesto_ocasional":     impuesto_ocasional,
        "tramo_aplicado":         _tramo_aplicado(consolidado["renta_gravable"], reglas),
        "ajustados_manualmente":  consolidado.get("_ajustados_manualmente", []),
    }

    return {
        "año_gravable":          año,
        "patrimonio_bruto":      consolidado["patrimonio_bruto"],
        "patrimonio_liquido":    patrimonio_liquido,
        "ingresos_laborales":    consolidado["ingresos_laborales"],
        "rentas_capital":        consolidado["rentas_capital"],
        "rentas_no_laborales":   consolidado["rentas_no_laborales"],
        "dividendos":            consolidado.get("dividendos", 0),
        "ganancias_ocasionales": consolidado.get("ganancias_ocasionales", 0),
        "rentas_exentas":        consolidado["rentas_exentas"],
        "deducciones":           consolidado["deducciones"],
        "retenciones":           retenciones,
        "impuesto_cargo":        impuesto_cargo,
        "saldo_pagar":           saldo_pagar,
        "saldo_favor":           saldo_favor,
        "estado":                "borrador",
        "inconsistencias":       inconsistencias,
        "detalle_calculo":       detalle,
        # Campos S4
        "aportes_pension":       float(datos_guardados.get("aportes_pension", 0)),
        "afc_fvp":               float(datos_guardados.get("afc_fvp", 0)),
        "intereses_vivienda":    float(datos_guardados.get("intereses_vivienda", 0)),
        "medicina_prepagada":    float(datos_guardados.get("medicina_prepagada", 0)),
        "dependientes":          int(datos_guardados.get("dependientes", 0)),
        "tipo_ganancia":         datos_guardados.get("tipo_ganancia"),
        "pasivos":               pasivos,
        "ajuste_manual":         override,
    }
```

Agregar helper `_cargar_datos_guardados()` para leer la declaración existente (campos manuales):

```python
def _cargar_datos_guardados(db, contribuyente_id: str, año: int) -> dict:
    from sqlalchemy import text
    row = db.execute(
        text("SELECT * FROM renta_declaraciones WHERE contribuyente_id = :cid AND año_gravable = :año"),
        {"cid": contribuyente_id, "año": año},
    ).one_or_none()
    if not row:
        return {}
    d = dict(row._mapping)
    # ajuste_manual viene como dict o None
    if d.get("ajuste_manual") and isinstance(d["ajuste_manual"], str):
        import json
        d["ajuste_manual"] = json.loads(d["ajuste_manual"])
    return d
```

Modificar `_consolidar_datos()` para tomar en cuenta `datos_guardados` (aportes_pension, rentas_capital manuales, etc.). Si el campo manual es > 0, tiene prioridad sobre lo extraído de docs. Agregar parámetro `datos_guardados: dict | None = None`:

```python
def _consolidar_datos(docs: list[dict], reglas: dict, datos_guardados: dict | None = None) -> dict:
    datos_guardados = datos_guardados or {}
    uvt = reglas.get("uvt", 49799)
    # ... código existente de extracción de docs ...

    # Prioridad: valor manual si > 0, si no el extraído de docs
    def _manual_or_ocr(campo: str, ocr_val: float) -> float:
        manual = float(datos_guardados.get(campo) or 0)
        return manual if manual > 0 else ocr_val

    ingresos_laborales = _manual_or_ocr("ingresos_laborales", ingresos_laborales)
    rentas_capital     = _manual_or_ocr("rentas_capital", rentas_capital)
    rentas_no_lab      = _manual_or_ocr("rentas_no_laborales", rentas_no_lab)
    retenciones        = _manual_or_ocr("retenciones", retenciones)
    patrimonio_bruto   = _manual_or_ocr("patrimonio_bruto", patrimonio_bruto)
    dividendos         = float(datos_guardados.get("dividendos") or 0)
    ganancias_oc       = float(datos_guardados.get("ganancias_ocasionales") or 0)
    aportes_pension    = float(datos_guardados.get("aportes_pension") or 0)

    # Límite 40% / 1.340 UVT (Art. 336 ET)
    ingresos_netos = max(0.0,
        ingresos_laborales - aportes_pension
        + rentas_capital
        + rentas_no_lab
    )
    tope_limitadas = min(ingresos_netos * 0.40, 1340 * uvt)

    # Rentas exentas laborales — Art. 206 num 10: 25% con límite 240 UVT/mes
    limite_exento_anual = 240 * 12 * uvt
    afc_fvp_val = float(datos_guardados.get("afc_fvp") or 0)
    exento_laboral_bruto = min(ingresos_laborales * 0.25, limite_exento_anual) + afc_fvp_val

    # Deducciones
    intereses_viv   = float(datos_guardados.get("intereses_vivienda") or 0)
    medicina_prep   = float(datos_guardados.get("medicina_prepagada") or 0)
    num_dependientes = int(datos_guardados.get("dependientes") or 0)
    deduccion_dep   = min(num_dependientes, 4) * 72 * uvt
    deducciones_brutas = intereses_viv + medicina_prep + deduccion_dep

    # Aplicar tope global
    exentas_y_deduc_aplicar = min(exento_laboral_bruto + deducciones_brutas, tope_limitadas)
    # Distribuir proporcionalmente entre exentas y deducciones
    total_bruto = exento_laboral_bruto + deducciones_brutas
    if total_bruto > 0:
        factor = exentas_y_deduc_aplicar / total_bruto
        rentas_exentas_final = round(exento_laboral_bruto * factor, 2)
        deducciones_final    = round(deducciones_brutas * factor, 2)
    else:
        rentas_exentas_final = 0.0
        deducciones_final    = 0.0

    renta_gravable = max(0.0, ingresos_netos - rentas_exentas_final - deducciones_final)

    return {
        "ingresos_laborales":    round(ingresos_laborales, 2),
        "rentas_capital":        round(rentas_capital, 2),
        "rentas_no_laborales":   round(rentas_no_lab, 2),
        "dividendos":            round(dividendos, 2),
        "ganancias_ocasionales": round(ganancias_oc, 2),
        "retenciones":           round(retenciones, 2),
        "patrimonio_bruto":      round(patrimonio_bruto, 2),
        "rentas_exentas":        rentas_exentas_final,
        "deducciones":           deducciones_final,
        "renta_gravable":        round(renta_gravable, 2),
    }
```

- [ ] **Step 4: Correr tests — deben pasar**

```bash
python -m pytest tests/test_renta_engine.py -v
```
Esperado: todos PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/renta/tax_engine.py tests/test_renta_engine.py
git commit -m "feat(renta): motor S4 — límite 40% Art.336, cédula dividendos, ganancias ocasionales, overrides, patrimonio líquido"
```

---

## Chunk 3: API Endpoints

### Task 5: PATCH /datos y GET /pdf en renta.py

**Files:**
- Modify: `api/routers/renta.py`
- Create: `services/renta/pdf_formulario210.py`

- [ ] **Step 1: Agregar PATCH /datos al router**

En `api/routers/renta.py`, después del endpoint `calcular_declaracion_endpoint`, agregar:

```python
@router.patch("/contribuyentes/{id}/declaracion/datos", response_model=DeclaracionOut)
async def patch_datos_declaracion_endpoint(
    id: UUID,
    body: DatosTributariosIn,
    user=Depends(get_current_user),
):
    from db.database_renta import get_contribuyente, patch_datos_declaracion
    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")
    data = body.model_dump(exclude_none=True)
    try:
        return patch_datos_declaracion(str(id), contrib["año_gravable"], data)
    except Exception as e:
        raise HTTPException(500, f"Error guardando datos: {e}")
```

Asegurarse de importar `DatosTributariosIn` al inicio del router:
```python
from api.schemas_renta import (
    ContribuyenteCreate, ContribuyenteUpdate, ContribuyenteOut,
    DocumentoOut, DeclaracionOut, RiesgoOut, DatosTributariosIn,
)
```

También actualizar el endpoint `calcular_declaracion_endpoint` para aceptar `ajuste_manual` opcional:

```python
@router.post("/contribuyentes/{id}/declaracion/calcular", response_model=DeclaracionOut)
async def calcular_declaracion_endpoint(
    id: UUID,
    body: dict = Body(default={}),
    user=Depends(get_current_user),
):
    from db.database_renta import get_contribuyente, upsert_declaracion
    from services.renta.tax_engine import calcular_declaracion
    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")
    try:
        ajuste_manual = body.get("ajuste_manual") if body else None
        data = calcular_declaracion(str(id), contrib["año_gravable"], ajuste_manual)
        return upsert_declaracion(str(id), contrib["año_gravable"], data)
    except Exception as e:
        raise HTTPException(500, f"Error calculando declaración: {e}")
```

- [ ] **Step 2: Crear pdf_formulario210.py**

```python
# services/renta/pdf_formulario210.py
"""Genera borrador del Formulario 210 DIAN como PDF usando WeasyPrint."""
from __future__ import annotations


def generar_pdf(declaracion: dict, contribuyente: dict) -> bytes:
    from weasyprint import HTML
    html = _render_html(declaracion, contribuyente)
    return HTML(string=html, base_url=None).write_pdf()


def _fmt(v) -> str:
    try:
        return f"$ {float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "$ 0"


def _render_html(decl: dict, contrib: dict) -> str:
    uvt = (decl.get("detalle_calculo") or {}).get("uvt", 49799)
    tramo = ((decl.get("detalle_calculo") or {}).get("tramo_aplicado") or {})
    ajustados = ((decl.get("detalle_calculo") or {}).get("ajustados_manualmente") or [])

    def cas(num: str, campo: str, label: str) -> str:
        val = decl.get(campo, 0) or 0
        manual = "⚠️" if campo in ajustados else ""
        return f"""
        <tr>
          <td class="cas-num">{num}</td>
          <td class="cas-label">{label} {manual}</td>
          <td class="cas-val">{_fmt(val)}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ font-family: Arial, sans-serif; font-size: 9pt; color: #111; }}
  h1 {{ font-size: 13pt; text-align: center; margin: 0 0 4px; }}
  h2 {{ font-size: 10pt; text-align: center; color: #444; margin: 0 0 12px; }}
  .header-box {{ border: 2px solid #222; padding: 8px 12px; margin-bottom: 14px; }}
  .seccion {{ margin-bottom: 12px; }}
  .seccion h3 {{ font-size: 9pt; background: #1e3a5f; color: white; padding: 3px 6px; margin: 0 0 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 2px 4px; border-bottom: 1px solid #ddd; vertical-align: top; }}
  .cas-num {{ width: 30px; font-weight: bold; color: #1e3a5f; }}
  .cas-label {{ width: 60%; }}
  .cas-val {{ text-align: right; font-weight: bold; }}
  .total-row td {{ background: #f0f4ff; font-weight: bold; border-top: 2px solid #1e3a5f; }}
  .saldo-pagar td {{ background: #fff0f0; color: #b00; font-weight: bold; }}
  .saldo-favor td {{ background: #f0fff4; color: #090; font-weight: bold; }}
  .watermark {{
    position: fixed; top: 40%; left: 10%; width: 80%;
    font-size: 72pt; color: rgba(200,0,0,0.08);
    transform: rotate(-35deg); text-align: center;
    font-weight: 900; pointer-events: none; z-index: 0;
  }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; }}
  .info-item {{ font-size: 8pt; }}
  .info-item span {{ font-weight: bold; }}
</style>
</head>
<body>
<div class="watermark">BORRADOR</div>

<div class="header-box">
  <h1>DECLARACIÓN DE RENTA Y COMPLEMENTARIO</h1>
  <h2>Personas Naturales y Asimiladas Residentes — Formulario 210</h2>
  <div class="info-grid">
    <div class="info-item">Año gravable: <span>{decl.get("año_gravable", "")}</span></div>
    <div class="info-item">Estado: <span>{decl.get("estado", "borrador").upper()}</span></div>
    <div class="info-item">Nombre: <span>{contrib.get("nombre_completo", "")}</span></div>
    <div class="info-item">NIT/Cédula: <span>{contrib.get("numero_doc", "")}</span></div>
    <div class="info-item">Ciudad: <span>{contrib.get("ciudad", "")}</span></div>
    <div class="info-item">UVT: <span>{_fmt(uvt)}</span></div>
  </div>
</div>

<div class="seccion">
  <h3>PATRIMONIO</h3>
  <table>
    {cas("29", "patrimonio_bruto", "Total patrimonio bruto")}
    {cas("30", "pasivos", "Deudas")}
    {cas("31", "patrimonio_liquido", "Total patrimonio líquido")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA GENERAL — RENTAS DE TRABAJO (Art. 103 ET)</h3>
  <table>
    {cas("32", "ingresos_laborales", "Ingresos brutos rentas de trabajo")}
    {cas("33", "aportes_pension", "Ingresos no constitutivos — aportes pensión")}
    {cas("35", "afc_fvp", "Rentas exentas — AFC / FVP / AVC")}
    {cas("36", "rentas_exentas", "Rentas exentas — 25% num. 10 Art. 206 ET")}
    {cas("38", "intereses_vivienda", "Deducciones — Intereses crédito vivienda")}
    {cas("39", "deducciones", "Deducciones — Salud y dependientes")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA GENERAL — RENTAS DE CAPITAL (Art. 58 ET)</h3>
  <table>
    {cas("58", "rentas_capital", "Ingresos brutos rentas de capital")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA GENERAL — RENTAS NO LABORALES (Art. 74 ET)</h3>
  <table>
    {cas("74", "rentas_no_laborales", "Ingresos brutos rentas no laborales")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA DE DIVIDENDOS Y PARTICIPACIONES (Art. 242 ET)</h3>
  <table>
    {cas("107", "dividendos", "Dividendos gravados 2017 y siguientes")}
  </table>
</div>

<div class="seccion">
  <h3>GANANCIAS OCASIONALES (Art. 299-316 ET)</h3>
  <table>
    {cas("111", "ganancias_ocasionales", f"Ingresos ganancias ocasionales ({decl.get('tipo_ganancia') or 'venta_activo'})")}
  </table>
</div>

<div class="seccion">
  <h3>LIQUIDACIÓN</h3>
  <table>
    <tr class="total-row">
      <td class="cas-num">116</td>
      <td class="cas-label">Total impuesto sobre rentas líquidas gravables</td>
      <td class="cas-val">{_fmt(decl.get("impuesto_cargo", 0))}</td>
    </tr>
    {cas("132", "retenciones", "Retenciones en la fuente año gravable")}
    {"".join([f'<tr class="saldo-pagar"><td class="cas-num">138</td><td class="cas-label">Saldo a pagar</td><td class="cas-val">{_fmt(decl.get("saldo_pagar",0))}</td></tr>' if (decl.get("saldo_pagar") or 0) > 0 else f'<tr class="saldo-favor"><td class="cas-num">137</td><td class="cas-label">Saldo a favor</td><td class="cas-val">{_fmt(decl.get("saldo_favor",0))}</td></tr>'])}
  </table>
</div>

{"".join([f'<p style="font-size:7pt;color:orange;margin:2px 0">⚠️ Campo ajustado manualmente: {", ".join(ajustados)}</p>' if ajustados else ""])}
<p style="font-size:7pt;color:#888;margin-top:16px;text-align:center">
  Borrador generado por TaxOps · {decl.get("updated_at","")[:10]} · No válido como declaración ante DIAN
</p>
</body>
</html>"""
```

- [ ] **Step 3: Agregar endpoint GET /pdf al router**

```python
@router.get("/contribuyentes/{id}/declaracion/pdf")
async def descargar_formulario_210(id: UUID, user=Depends(get_current_user)):
    from db.database_renta import get_contribuyente, get_declaracion
    from services.renta.pdf_formulario210 import generar_pdf
    from fastapi.responses import Response

    contrib = get_contribuyente(str(id), user["org_id"])
    if not contrib:
        raise HTTPException(404, "Contribuyente no encontrado")

    decl = get_declaracion(str(id), contrib["año_gravable"])
    if not decl:
        raise HTTPException(404, "No existe declaración calculada para este contribuyente")

    try:
        pdf_bytes = generar_pdf(decl, contrib)
    except Exception as e:
        raise HTTPException(500, f"Error generando PDF: {e}")

    filename = f"Formulario210_{contrib['año_gravable']}_{contrib['numero_doc']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Agregar weasyprint a requirements y Dockerfile**

En `api/requirements-api.txt`, agregar al final:
```
weasyprint>=62.0
```

En `api/Dockerfile-api`, en el bloque `apt-get install`, agregar las dependencias del sistema de WeasyPrint:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    tesseract-ocr tesseract-ocr-spa \
    libgl1 libglib2.0-0 \
    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 5: Commit**

```bash
git add api/routers/renta.py services/renta/pdf_formulario210.py \
        api/requirements-api.txt api/Dockerfile-api
git commit -m "feat(renta): PATCH /datos + GET /pdf Formulario 210 + WeasyPrint"
```

- [ ] **Step 6: Push para desplegar API en Cloud Run**

```bash
git push origin main
```
Verificar en GitHub Actions que el workflow `deploy-cloud-run.yml` se dispara (cambios en `api/` y `services/`).

---

## Chunk 4: Frontend

### Task 6: Zona A — Formulario de datos tributarios

**Files:**
- Modify: `taxops-web/app/(app)/renta/page.tsx`

- [ ] **Step 1: Agregar tipos y estado**

Agregar el tipo `DatosTributarios` y el estado del formulario después del estado `declError`:

```typescript
type DatosTributarios = {
  ingresos_laborales: string;
  rentas_capital: string;
  rentas_no_laborales: string;
  aportes_pension: string;
  afc_fvp: string;
  retenciones: string;
  intereses_vivienda: string;
  medicina_prepagada: string;
  dependientes: string;
  dividendos: string;
  ganancias_ocasionales: string;
  tipo_ganancia: string;
  patrimonio_bruto: string;
  pasivos: string;
};

const DATOS_EMPTY: DatosTributarios = {
  ingresos_laborales: "", rentas_capital: "", rentas_no_laborales: "",
  aportes_pension: "", afc_fvp: "", retenciones: "",
  intereses_vivienda: "", medicina_prepagada: "", dependientes: "",
  dividendos: "", ganancias_ocasionales: "", tipo_ganancia: "venta_activo",
  patrimonio_bruto: "", pasivos: "",
};
```

En el estado del componente agregar:
```typescript
const [datosForm, setDatosForm] = useState<DatosTributarios>(DATOS_EMPTY);
const [datosTab, setDatosTab] = useState<"general" | "dividendos" | "ganancias" | "patrimonio">("general");
const [datosOpen, setDatosOpen] = useState(false);
const [datosSaving, setDatosSaving] = useState(false);
const [datosError, setDatosError] = useState("");
```

Poblar `datosForm` desde la declaración cuando se carga:
```typescript
// En handleSelect, después de setDecl(result):
if (result) {
  setDatosForm({
    ingresos_laborales:    String(result.ingresos_laborales || ""),
    rentas_capital:        String(result.rentas_capital || ""),
    rentas_no_laborales:   String(result.rentas_no_laborales || ""),
    aportes_pension:       String((result as any).aportes_pension || ""),
    afc_fvp:               String((result as any).afc_fvp || ""),
    retenciones:           String(result.retenciones || ""),
    intereses_vivienda:    String((result as any).intereses_vivienda || ""),
    medicina_prepagada:    String((result as any).medicina_prepagada || ""),
    dependientes:          String((result as any).dependientes || ""),
    dividendos:            String(result.dividendos || ""),
    ganancias_ocasionales: String(result.ganancias_ocasionales || ""),
    tipo_ganancia:         (result as any).tipo_ganancia || "venta_activo",
    patrimonio_bruto:      String(result.patrimonio_bruto || ""),
    pasivos:               String((result as any).pasivos || ""),
  });
}
```

- [ ] **Step 2: Agregar handleGuardarDatos()**

```typescript
async function handleGuardarDatos() {
  if (!selected) return;
  setDatosSaving(true); setDatosError("");
  try {
    const num = (v: string) => v === "" ? undefined : parseFloat(v.replace(/[^0-9.-]/g, ""));
    const body: Record<string, unknown> = {
      ingresos_laborales:    num(datosForm.ingresos_laborales),
      rentas_capital:        num(datosForm.rentas_capital),
      rentas_no_laborales:   num(datosForm.rentas_no_laborales),
      aportes_pension:       num(datosForm.aportes_pension),
      afc_fvp:               num(datosForm.afc_fvp),
      retenciones:           num(datosForm.retenciones),
      intereses_vivienda:    num(datosForm.intereses_vivienda),
      medicina_prepagada:    num(datosForm.medicina_prepagada),
      dependientes:          datosForm.dependientes ? parseInt(datosForm.dependientes) : undefined,
      dividendos:            num(datosForm.dividendos),
      ganancias_ocasionales: num(datosForm.ganancias_ocasionales),
      tipo_ganancia:         datosForm.ganancias_ocasionales ? datosForm.tipo_ganancia : undefined,
      patrimonio_bruto:      num(datosForm.patrimonio_bruto),
      pasivos:               num(datosForm.pasivos),
    };
    // Remover undefined
    Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);
    const result = await patch<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/datos`, body);
    setDecl(result);
  } catch (e: unknown) {
    setDatosError(e instanceof Error ? e.message : "Error guardando datos");
  } finally { setDatosSaving(false); }
}
```

Verificar que `useApi` tiene `patch`. Si no existe, agregar al hook:
```typescript
// En taxops-web/lib/api.ts — si falta:
patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
```

- [ ] **Step 3: Agregar JSX de Zona A**

Insertar el panel antes del panel de liquidación (`{/* ─── Declaración panel ─── */}`):

```tsx
{/* ─── Zona A: Formulario datos tributarios ─── */}
<div className="rounded-xl border border-gray-200 bg-white p-4">
  <button
    onClick={() => setDatosOpen(p => !p)}
    className="flex w-full items-center justify-between text-sm font-semibold text-gray-800"
  >
    <span className="flex items-center gap-2">
      <FileText size={15} /> Datos tributarios
    </span>
    <ChevronRight size={14} className={`transition-transform ${datosOpen ? "rotate-90" : ""}`} />
  </button>

  {datosOpen && (
    <div className="mt-3">
      {/* Pestañas */}
      <div className="flex gap-1 mb-3 border-b border-gray-200">
        {(["general", "dividendos", "ganancias", "patrimonio"] as const).map(tab => (
          <button key={tab} onClick={() => setDatosTab(tab)}
            className={`px-3 py-1.5 text-xs font-medium rounded-t transition-colors ${datosTab === tab ? "bg-[#E05519] text-white" : "text-gray-500 hover:text-gray-800"}`}>
            {tab === "general" ? "Cédula General" : tab === "dividendos" ? "Dividendos" : tab === "ganancias" ? "Gan. Ocasionales" : "Patrimonio"}
          </button>
        ))}
      </div>

      {datosTab === "general" && (
        <div className="grid grid-cols-2 gap-2">
          {[
            ["ingresos_laborales",  "Ingresos laborales"],
            ["rentas_capital",      "Rentas de capital"],
            ["rentas_no_laborales", "Rentas no laborales"],
            ["aportes_pension",     "Aportes pensión (INCR)"],
            ["afc_fvp",             "AFC / FVP / AVC"],
            ["retenciones",         "Retenciones del año"],
            ["intereses_vivienda",  "Intereses vivienda"],
            ["medicina_prepagada",  "Medicina prepagada"],
          ].map(([k, label]) => (
            <div key={k}>
              <label className="block text-[10px] text-gray-500 mb-0.5">{label}</label>
              <input type="number" value={(datosForm as any)[k]}
                onChange={e => setDatosForm(p => ({ ...p, [k]: e.target.value }))}
                className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                placeholder="0" />
            </div>
          ))}
          <div>
            <label className="block text-[10px] text-gray-500 mb-0.5">Dependientes económicos</label>
            <input type="number" min="0" max="4" value={datosForm.dependientes}
              onChange={e => setDatosForm(p => ({ ...p, dependientes: e.target.value }))}
              className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
              placeholder="0" />
          </div>
        </div>
      )}

      {datosTab === "dividendos" && (
        <div>
          <label className="block text-[10px] text-gray-500 mb-0.5">Dividendos gravados 2017+ (cas. 107)</label>
          <input type="number" value={datosForm.dividendos}
            onChange={e => setDatosForm(p => ({ ...p, dividendos: e.target.value }))}
            className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
            placeholder="0" />
          <p className="mt-2 text-[10px] text-gray-400">Tarifa: 0% hasta 300 UVT · 15% sobre el exceso (Art. 242 ET)</p>
        </div>
      )}

      {datosTab === "ganancias" && (
        <div className="space-y-2">
          <div>
            <label className="block text-[10px] text-gray-500 mb-0.5">Tipo de ganancia</label>
            <select value={datosForm.tipo_ganancia}
              onChange={e => setDatosForm(p => ({ ...p, tipo_ganancia: e.target.value }))}
              className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]">
              <option value="venta_activo">Venta activo fijo &gt;2 años — 10%</option>
              <option value="herencia">Herencia / donación — 10%</option>
              <option value="loteria">Lotería / rifa — 20%</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 mb-0.5">Valor ganancia ocasional</label>
            <input type="number" value={datosForm.ganancias_ocasionales}
              onChange={e => setDatosForm(p => ({ ...p, ganancias_ocasionales: e.target.value }))}
              className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
              placeholder="0" />
          </div>
        </div>
      )}

      {datosTab === "patrimonio" && (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] text-gray-500 mb-0.5">Patrimonio bruto (cas. 29)</label>
            <input type="number" value={datosForm.patrimonio_bruto}
              onChange={e => setDatosForm(p => ({ ...p, patrimonio_bruto: e.target.value }))}
              className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
              placeholder="0" />
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 mb-0.5">Pasivos / deudas (cas. 30)</label>
            <input type="number" value={datosForm.pasivos}
              onChange={e => setDatosForm(p => ({ ...p, pasivos: e.target.value }))}
              className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
              placeholder="0" />
          </div>
        </div>
      )}

      {datosError && (
        <p className="mt-2 flex items-center gap-1 text-xs text-red-500"><AlertCircle size={12} /> {datosError}</p>
      )}

      <button onClick={handleGuardarDatos} disabled={datosSaving}
        className="mt-3 w-full rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">
        {datosSaving ? "Guardando…" : "Guardar datos tributarios"}
      </button>
    </div>
  )}
</div>
```

- [ ] **Step 4: Commit**

```bash
git add taxops-web/app/\(app\)/renta/page.tsx
git commit -m "feat(renta): Zona A — formulario datos tributarios con pestañas"
```

---

### Task 7: Zona B (editor post-cálculo) + Zona C (validaciones) + botón PDF

- [ ] **Step 1: Agregar estado para overrides**

```typescript
const [overrides, setOverrides] = useState<Record<string, number>>({});
const [editingField, setEditingField] = useState<string | null>(null);
```

- [ ] **Step 2: Modificar handleCalcular para enviar overrides**

```typescript
async function handleCalcular() {
  if (!selected) return;
  setDeclLoading(true); setDeclError("");
  try {
    const body = Object.keys(overrides).length > 0 ? { ajuste_manual: overrides } : {};
    const result = await post<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/calcular`, body);
    setDecl(result);
    try { setInfo(await get<ContribuyenteInfo>(`/renta/contribuyentes/${selected.id}/info`)); } catch { /* optional */ }
  } catch (e: unknown) {
    setDeclError(e instanceof Error ? e.message : "Error calculando declaración");
  } finally { setDeclLoading(false); }
}
```

- [ ] **Step 3: Actualizar DeclRow para soportar edición**

Reemplazar el componente `DeclRow` al final del archivo:

```tsx
function DeclRow({
  label, value, campo, negative, overrides, editingField, onEdit, onSave, onOverrideChange,
}: {
  label: string; value: number; campo: string; negative?: boolean;
  overrides: Record<string, number>;
  editingField: string | null;
  onEdit: (campo: string) => void;
  onSave: () => void;
  onOverrideChange: (campo: string, val: number) => void;
}) {
  if (value === 0 && !overrides[campo]) return null;
  const isOverridden = campo in overrides;
  const isEditing = editingField === campo;
  const displayVal = isOverridden ? overrides[campo] : value;

  return (
    <tr className="group">
      <td className="py-1 text-gray-500">{label}</td>
      <td className={`py-1 text-right font-medium ${negative ? "text-red-600" : "text-gray-800"}`}>
        {isEditing ? (
          <input
            type="number"
            autoFocus
            defaultValue={displayVal}
            onBlur={e => { onOverrideChange(campo, parseFloat(e.target.value) || 0); onSave(); }}
            onKeyDown={e => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="w-28 rounded border border-[#E05519] bg-white px-1 py-0.5 text-xs text-right text-gray-900 focus:outline-none"
          />
        ) : (
          <span className="flex items-center justify-end gap-1">
            {isOverridden && (
              <span className="rounded bg-orange-100 px-1 py-0.5 text-[9px] font-semibold text-orange-700">manual</span>
            )}
            {fmtCOP(displayVal)}
            <button onClick={() => onEdit(campo)}
              className="ml-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-[#E05519] transition-opacity">
              <Pencil size={11} />
            </button>
          </span>
        )}
      </td>
    </tr>
  );
}
```

Agregar `Pencil` a los imports de lucide-react.

- [ ] **Step 4: Agregar Zona C (validaciones) y botón PDF en el JSX**

Después de la tabla de cédula, antes de "Tramo aplicado", agregar botón Recalcular con ajustes:

```tsx
{Object.keys(overrides).length > 0 && (
  <button onClick={handleCalcular} disabled={declLoading}
    className="mt-2 text-xs text-[#E05519] underline hover:text-[#c44a14]">
    Recalcular con ajustes manuales
  </button>
)}
```

Después del panel de liquidación agregar Zona C:

```tsx
{/* ─── Zona C: Validaciones ─── */}
{decl && (() => {
  const ingresosTotales = (decl.ingresos_laborales || 0) + (decl.rentas_capital || 0)
    + (decl.rentas_no_laborales || 0) + (decl.dividendos || 0);
  const bloqueos: string[] = [];
  const advertencias: string[] = [];

  if (ingresosTotales === 0) bloqueos.push("Sin ingresos declarados en ninguna cédula");

  const tope40 = ingresosTotales * 0.40;
  const exentasDeduc = (decl.rentas_exentas || 0) + (decl.deducciones || 0);
  if (exentasDeduc > tope40 && ingresosTotales > 0)
    advertencias.push(`Rentas exentas + deducciones (${fmtCOP(exentasDeduc)}) superan el 40% de ingresos netos — Art. 336 ET`);

  if ((decl.retenciones || 0) > (decl.impuesto_cargo || 0) && (decl.impuesto_cargo || 0) > 0)
    advertencias.push("Retenciones superiores al impuesto a cargo — saldo a favor probable");

  if ((decl.patrimonio_bruto || 0) === 0 && ingresosTotales > 0)
    advertencias.push("Patrimonio bruto $0 con ingresos declarados — verificar activos");

  decl.inconsistencias.forEach(inc => {
    if (inc.nivel === "advertencia") advertencias.push(inc.mensaje);
  });

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-2">
      <h3 className="text-sm font-semibold text-gray-800">Validaciones</h3>
      {bloqueos.map((b, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg bg-red-50 p-2 text-xs text-red-700">
          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" /> {b}
        </div>
      ))}
      {advertencias.map((a, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg bg-yellow-50 p-2 text-xs text-yellow-800">
          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" /> {a}
        </div>
      ))}
      {bloqueos.length === 0 && advertencias.length === 0 && (
        <p className="text-xs text-green-600 flex items-center gap-1">
          <CheckCircle size={12} /> Sin inconsistencias detectadas
        </p>
      )}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => window.open(`/api-proxy/renta/contribuyentes/${selected!.id}/declaracion/pdf`, "_blank")}
          disabled={!decl}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-40">
          <Download size={12} /> Formulario 210
        </button>
        <button
          onClick={async () => {
            if (!selected || bloqueos.length > 0) return;
            try {
              const result = await patch<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/datos`, { estado: "revision" });
              setDecl(result);
            } catch { /* silent */ }
          }}
          disabled={bloqueos.length > 0 || !decl}
          className="flex-1 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-40">
          {decl?.estado === "revision" ? "✓ Lista para presentar" : "Marcar lista para presentar"}
        </button>
      </div>
    </div>
  );
})()}
```

Agregar `Download` y `Pencil` a los imports de lucide-react.

- [ ] **Step 5: Verificar tipos TypeScript**

```bash
cd taxops-web && npx tsc --noEmit 2>&1 | head -30
```
Corregir cualquier error de tipos antes de hacer commit.

- [ ] **Step 6: Commit final frontend**

```bash
git add taxops-web/app/\(app\)/renta/page.tsx
git commit -m "feat(renta): Zona B (editor overrides), Zona C (validaciones + PDF), botón Formulario 210"
```

- [ ] **Step 7: Push y verificar deploy Vercel**

```bash
git push origin main
```

Verificar en Vercel dashboard que el deploy completa sin errores de build.

---

## Checklist final de verificación

- [ ] Migración 005 corre sin errores (automática en startup Cloud Run)
- [ ] PATCH `/renta/contribuyentes/{id}/declaracion/datos` guarda datos y devuelve `DeclaracionOut`
- [ ] GET `/renta/contribuyentes/{id}/declaracion/pdf` devuelve PDF con sello BORRADOR
- [ ] El motor calcula correctamente dividendos y ganancias ocasionales
- [ ] El límite 40%/1.340 UVT se aplica sobre el total consolidado de cédula general
- [ ] Formulario Zona A se colapsa/expande, guarda datos sin recalcular
- [ ] Editor Zona B muestra chip "manual" en campos overrideados
- [ ] Zona C bloquea "Marcar lista" cuando hay ingresos = 0
- [ ] Botón "Formulario 210" descarga PDF sin errores
- [ ] TypeScript build sin errores en Vercel
