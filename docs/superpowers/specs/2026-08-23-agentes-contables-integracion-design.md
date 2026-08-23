# Integración de agentes contables existentes a TaxOps

## Contexto

`agents/contabilidad/` contiene 4 agentes standalone ya funcionando (Groq + web search vía el
motor compartido `agents/_shared/agent_core.py`, corren con `python agent.py`, escriben un
reporte a `output/`):

- **dian-monitor** — resumen semanal de resoluciones/circulares/decretos DIAN relevantes para PYMEs.
- **monitor-niif** — cambios recientes en normas NIIF aplicables en Colombia.
- **vencimientos-tributarios** — vencimientos tributarios de los próximos 30 días.
- **prospector-clientes-contables** — leads comerciales (empresas que podrían necesitar
  contratar servicios contables) por ciudad/sector, según `config.yaml`.

Ninguno está programado (sin cron) ni conectado a TaxOps — hoy son herramientas personales de
línea de comandos. Este spec cubre **solo** la integración de estos 4 agentes ya existentes al
producto. No cubre (quedan como sub-proyectos futuros, cada uno con su propio spec):

- Agente conversacional que dispara/consulta/reintenta procesamiento de Facturas/Exógenas/Renta
  desde el chat.
- Sistema de notificaciones proactivas (email/calendario) — este spec sienta datos que un futuro
  sistema de notificaciones podría consumir, pero no envía notificaciones él mismo.
- Agente nuevo de descarga de facturas desde el portal DIAN (requiere spike de viabilidad
  primero — autenticación con certificado digital/RUT).
- `agents/empleo/*` — fuera de alcance de TaxOps, dominio no relacionado (búsqueda de empleo).

## Hallazgo que este spec también corrige

`api/routers/calendario.py` persiste el Calendario DIAN en un archivo local
(`api/data/calendario_2026.json`, leído/escrito con `Path.write_text`/`read_text`). Esto
funcionaba en Cloud Run (proceso continuo, un solo disco de vida larga) pero **no sobrevive en
Lambda**: cada execution environment arranca desde la imagen del container, así que cualquier
`PUT /calendario/eventos` se pierde en el siguiente cold start, y dos invocaciones concurrentes ni
siquiera ven el mismo archivo. Es un bug latente de la migración de agosto, no relacionado con el
trabajo de esta semana, que este spec corrige de paso porque el agente de vencimientos necesita un
lugar real donde persistir.

## Arquitectura

```
┌─────────────────────────┐     cron semanal      ┌──────────────────────────┐
│ GitHub Actions           │ ────────────────────▶ │ agents/contabilidad/*/    │
│ .github/workflows/       │   (1 workflow,         │ agent.py (sin cambios de  │
│ agentes-contables.yml    │    4 jobs paralelos)   │ motor, solo agrego modo   │
└─────────────────────────┘                        │ --json a vencimientos)    │
                                                     └────────────┬─────────────┘
                                                                  │ output estructurado
                                    ┌─────────────────────────────┼─────────────────────┐
                                    ▼                             ▼                     ▼
                          ┌──────────────────┐         ┌──────────────────┐   ┌──────────────────┐
                          │ INSERT directo a  │         │ PUT directo a S3  │   │ INSERT directo a  │
                          │ Neon (novedades)  │         │ (calendario json) │   │ Neon (leads_      │
                          │ dian-monitor +    │         │ vencimientos-     │   │ comerciales)       │
                          │ monitor-niif      │         │ tributarios       │   │ prospector-...     │
                          └──────────────────┘         └──────────────────┘   └──────────────────┘
                                    │                             │                     │
                                    ▼                             ▼                     ▼
                          GET /novedades              GET/PUT /calendario/    GET /admin/leads
                          (cualquier rol)              eventos (sin cambio    (owner/admin)
                                                        de contrato, cambia
                                                        el storage debajo)
```

**Por qué el workflow escribe directo al storage en vez de llamar a la API por HTTP**: llamar a
`PUT /calendario/eventos` requeriría un JWT superadmin de larga duración solo para automatización
— una superficie de riesgo nueva (¿dónde vive ese token? ¿cómo se rota?) para un problema que no
hace falta resolver. El workflow ya tiene `DATABASE_URL` (GitHub Secret existente) y el rol OIDC
`github_actions_terraform` (ya usado por `terraform-plan.yml`/`terraform-apply.yml`, ya tiene
`AdministratorAccess` — deuda técnica ya documentada en `docs/CI-CD-GITOPS-GUIDE.md`, no introducida
por este spec) para escribir a S3 sin permisos nuevos — escribe directo, como lo haría un script de
mantenimiento.

## Componentes

### 1. Workflow de GitHub Actions

`.github/workflows/agentes-contables.yml`, `schedule: cron: "0 11 * * 1"` (lunes 6am COT) +
`workflow_dispatch` (para correr manual/probar). 4 jobs independientes (uno por agente), cada uno:
1. Checkout + Python setup + `pip install -r agents/contabilidad/<nombre>/requirements.txt`.
2. Corre `python agent.py` con `GROQ_API_KEY` (ya existe como secret) inyectado.
3. Corre un script nuevo `agents/contabilidad/<nombre>/publish.py` que toma el output del agente y
   lo persiste (Postgres o S3 según el agente, ver abajo).

Un job que falla no afecta a los otros tres (jobs independientes, no un solo script secuencial).

### 2. Cambio a vencimientos-tributarios: salida estructurada

Hoy el agente solo pide al modelo un resumen en Markdown. Se agrega al prompt un bloque final
pidiendo también un bloque ` ```json ` con una lista de eventos en el mismo shape que ya usa
`calendario_2026.json` (`{id, fecha, titulo, descripcion, tipo, urgencia, articulo, alertaDias}`).
`publish.py` extrae ese bloque JSON, valida con Pydantic (mismo shape, campos obligatorios) antes
de tocar nada — si el JSON es inválido o está vacío, el job falla visible (rojo en Actions) y el
calendario existente en S3 **no se toca**. Solo un reemplazo exitoso pisa el archivo.

### 3. Persistencia

**`api/routers/calendario.py`** — cambia de archivo local a S3:
```python
# antes: _DATA_FILE.write_text(...) / _DATA_FILE.read_text()
# después: s3.get_object/put_object sobre S3_BUCKET_JOB_ARTIFACTS,
#          key="config/calendario_2026.json" (fuera de "uploads/", no cae
#          en el lifecycle de 3 días)
```
Mismo contrato de `GET`/`PUT`/`POST`/`DELETE /calendario/eventos` — el frontend no cambia. Se
inicializa el objeto en S3 con el contenido actual de `calendario_2026.json` como parte de esta
migración (una vez, a mano, antes de mergear).

**Tabla nueva `novedades`** (Postgres, global — sin `org_id`, mismo criterio que
`reglas_tributarias`):
```sql
CREATE TABLE IF NOT EXISTS novedades (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo            VARCHAR(20) NOT NULL,  -- 'dian' | 'niif'
    titulo          TEXT NOT NULL,
    resumen         TEXT NOT NULL,          -- markdown completo del agente
    fecha_generado  DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_novedades_fecha ON novedades (fecha_generado DESC);
```
`publish.py` de dian-monitor/monitor-niif hace un `INSERT` simple tras cada corrida — no hay
update ni dedup: cada corrida semanal es una fila nueva, el feed las lista más-reciente-primero.

**Tabla nueva `leads_comerciales`** (Postgres, global, mismo criterio):
```sql
CREATE TABLE IF NOT EXISTS leads_comerciales (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa         TEXT NOT NULL,
    sector          VARCHAR(100),
    ciudad          VARCHAR(100),
    contacto        TEXT,               -- email/teléfono/LinkedIn, lo que haya encontrado
    fuente_url      TEXT,
    fecha_generado  DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lead UNIQUE (empresa, ciudad)  -- evita duplicar el mismo lead corrida tras corrida
);
```
A diferencia de novedades, acá sí hace falta dedup (un lead real no cambia semana a semana) —
`INSERT ... ON CONFLICT (empresa, ciudad) DO NOTHING`.

### 4. Backend — nuevos endpoints

- `GET /novedades?tipo=dian|niif&limit=20&offset=0` — `get_current_user` (cualquier rol),
  devuelve lista ordenada por `fecha_generado DESC`.
- `GET /admin/leads?ciudad=&sector=&limit=&offset=` — `require_admin` (owner/admin, mismo guard
  que ya usan otros endpoints de `/admin`).

### 5. Frontend

- **Página nueva `/novedades`** — entrada de menú visible para cualquier rol (icono tipo
  "Newspaper"/"Bell"), lista simple con tipo (badge DIAN/NIIF), título, fecha, resumen renderizado
  como markdown, sin tabs ni analítica — es un feed, no un dashboard.
- **Página nueva `/admin/leads`** — entrada de menú con `adminOnly: true` (mismo patrón que
  "Administración" en `sidebar.tsx`), tabla simple (empresa, sector, ciudad, contacto, fecha).
- **Calendario DIAN**: sin cambios de UI — sigue leyendo `GET /calendario/eventos` igual que hoy.

## Manejo de errores

- Un agente que no encuentra nada esa semana (`web_search` sin resultados útiles) debe distinguir
  "no hubo novedades" de "el agente falló" — el prompt ya le pide al modelo cerrar con lo que
  tenga; `publish.py` solo trata como fallo real una respuesta vacía/sin el bloque JSON esperado
  (vencimientos) o sin contenido (novedades/leads), no "esta semana no hay nada que reportar".
- Ningún job pisa datos existentes con una corrida fallida — el archivo/tabla solo se actualiza
  tras validar la salida.
- `prospector-clientes-contables` corre con la `config.yaml` que ya existe (ciudades/sectores
  fijos) — parametrizarlo por organización queda fuera de este spec.

## Testing

- `agents/contabilidad/vencimientos-tributarios/test_publish.py` (nuevo) — parseo del bloque JSON
  desde una salida de agente simulada (casos: JSON válido, JSON malformado, sin bloque JSON,
  bloque vacío) → confirma que solo el caso válido dispara un `PUT` a S3.
- `tests/test_novedades.py`, `tests/test_admin_leads.py` (nuevos, patrón moto/TestClient ya
  establecido en `tests/test_uploads_presign.py`) — cubren los endpoints nuevos con datos
  insertados directo en una DB de test.
- `tests/test_calendario.py` — actualizar los tests existentes de `calendario.py` (si los hay,
  confirmar con `grep -rl calendario tests/` antes de tocar) para mockear S3 en vez de filesystem.
- Verificación manual: `workflow_dispatch` del nuevo workflow corrido una vez a mano antes de
  activar el cron, confirmando que las 4 tablas/storage quedan bien pobladas.
