# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Install as editable package (exposes `taxops` CLI entry point)
pip install -e .

# Run FastAPI server (from api/ directory)
cd api && uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs

# Run Next.js frontend
cd taxops-web && npm install && npm run dev   # http://localhost:3000
cd taxops-web && npm run build && npm run lint

# DB management (requires DATABASE_URL env var)
python manage.py init-db
python manage.py create-org --name "Firma ABC" --email admin@firma.com --password secret123

# Run CLI processor
python main.py
python main.py --carpeta /ruta/facturas --ingresos "2026-04:5000000,2026-03:4500000"
python main.py --workers 8

# Run file watcher (requires: pip install watchdog>=4.0.0)
python watcher.py

# Run tests
python -m pytest
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py tests/test_chatbot.py
python -m pytest tests/test_e2e.py -v    # requires PDFs in facturas/
python -m pytest tests/test_extractor.py::TestClass::test_name -v  # single test
python -m pytest --cov=. --cov-report=term-missing
```

## Deployment

**Current production path (actualizado 2026-08-20 tras confirmar el cutover — ver `docs/MIGRACION-AWS-DISCOVERY.md` §0 para el trail histórico de docs de deploy que ya NO aplican):**

- **API**: AWS Lambda (container image, `api/Dockerfile-lambda`) detrás de CloudFront en `api.taxopsapp.com`, desplegada vía `.github/workflows/deploy-lambda.yml` (`on: push: branches: [main]`) + `terraform-apply.yml` (gate manual, `environment: production`) para cambios de infra. Cloud Run **ya no es producción** — decommissioned junto con esta migración.
- **Frontend**: AWS Amplify Hosting (`app.taxopsapp.com`), `taxops-web/` con SSR nativo (`platform WEB_COMPUTE`), auto-deploy on push a `main` vía el webhook de Amplify. Confirmado funcionando y al día (build `SUCCEED` en cada push, `curl https://app.taxopsapp.com/` → 200).
- **Vercel (`taxops-app.vercel.app`)**: en proceso de decommission — dejó de ser la ruta de producción real (Amplify ya la reemplazó), pero el proyecto sigue vivo en el dashboard de Vercel hasta que se pause/borre manualmente ahí (fuera de este repo). No confiar en esa URL para pruebas — usar siempre `app.taxopsapp.com`.
- **⚠️ Stale/vestigial, do not trust**: `render.yaml` (Render), `.github/workflows/deploy.yml` (Railway trigger), `taxops-web/vercel.json` (config de Vercel, no tocar hasta decommission completo — sigue sirviendo tráfico legacy) — leftovers de iteraciones anteriores, **no** la ruta viva.
- **Alembic**: migrations run automatically on API startup (`api/main.py` calls `alembic upgrade head`) in a background thread. Manual: `cd api && alembic upgrade head`.

### Migración a AWS — Chunks 0-8 completos (S3 presign + Exógenas async, 2026-08-20)

Migración de compute/storage/CI-CD de GCP+Vercel a AWS, gestionada 100% con Terraform, vive en `infra/`. Si tocas deploy/CI-CD/`docs/`, lee esto primero:

- **Discovery, plan y guías**: `docs/MIGRACION-AWS-DISCOVERY.md`, `docs/superpowers/plans/2026-08-05-taxops11-aws-migration.md` (plan ejecutable por chunks, con checkboxes), `docs/AWS-ACCOUNT-SETUP-GUIDE.md`, `docs/CI-CD-GITOPS-GUIDE.md`, `docs/DIRENV-AWS-PROFILE.md`, `docs/MIGRACION-AWS-CASE-STUDY.md` (portafolio).
- **Estado (2026-08-20)**: migración completa — API en Lambda, jobs vía SQS+DynamoDB+worker (Renta y Exógenas), uploads directo a S3 con presigned POST (`api/routers/uploads.py`), frontend en Amplify. Pendiente real: decommission manual de Vercel (dashboard, fuera de Terraform) y confirmar en 3-4 días que el lifecycle rule de 3 días borra objetos bajo `uploads/`.
- **Premisa no negociable: todo gratis, siempre.** Cualquier recurso AWS nuevo se evalúa primero por costo (capa gratuita perpetua > 12 meses > pago). Ver el detalle de decisiones de costo en el case study.
- **Regla de oro del pipeline**: ningún `terraform apply` manual salvo el bootstrap inicial — todo cambio de `infra/` pasa por PR (`terraform-plan.yml` comenta el plan) → merge a `main` → aprobación manual en GitHub (`terraform-apply.yml`, environment `production`) → apply.
- **La DB se queda en Neon** en la Fase 1 (no se migra a RDS/Aurora) — evita el costo de un NAT Gateway. Ver justificación completa en el case study.
- **Tagging obligatorio en todo recurso AWS nuevo.** Los dos providers (`infra/bootstrap/versions.tf`, `infra/environments/prod/providers.tf`) ya tienen `default_tags { Project = "taxops11", Environment = "...", ManagedBy = "terraform" }` — cualquier resource nuevo dentro de esos providers hereda las tags automáticamente, no hace falta repetirlas a mano. La única excepción real: recursos que Lambda/otros servicios auto-crean fuera de Terraform (p. ej. CloudWatch Log Groups de una función nueva) — esos nacen sin tags y con retención "Never expire". Si agregas una función Lambda nueva (o cualquier recurso con ese patrón de auto-creación), declara el recurso explícito en Terraform (`aws_cloudwatch_log_group` con `retention_in_days` + `depends_on` desde la función) en el mismo PR, usando un bloque `import {}` si el recurso ya existe en AWS por haberse auto-creado antes.

## Auth modes

The app has two runtime modes:

- **Local/demo** — `DATABASE_URL` not set. No authentication required. Streamlit app runs without login gate.
- **SaaS** — `DATABASE_URL` set. `home_gate.py:login_required()` returns `True`; `Home.py` enforces auth via JWT session stored in `st.session_state["auth"]`.

FastAPI always requires auth (JWT Bearer). Required env vars for SaaS: see `api/.env.example`.

## Architecture

TaxOps procesa facturas electrónicas DIAN (PDF/XML) colombianas en un pipeline:
`pipeline/extractor.py` → `pipeline/validator.py` → `pipeline/prorateo.py` → `pipeline/excel_writer.py` / PostgreSQL

**Stack:** FastAPI 0.115 · Next.js 15.3 (React 19) · PostgreSQL 16 · SQLAlchemy · Groq/OpenAI/Anthropic/Google · Cloud Run · Vercel

### Module responsibilities

- **`pipeline/extractor.py`** — Parsing de documentos. `extract_one(path)` es el entry point principal (thread-safe). Despacha a `extract_xml()` o `extract_pdf()` por extensión. XML tiene prioridad cuando coexisten ambos. Carga `autorretenedores.txt` al inicio como frozenset O(1). Fallback de fecha desde nombre de carpeta (`_date_from_folder`).

- **`pipeline/validator.py`** — Validación stateless sobre DataFrame. `validate()` agrega columnas `validacion` (OK/ERROR) y `observacion`. Verifica: formato CUFE/CUDE (96 hex), duplicados, formato NIT, subtotal+IVA≈total (tolerancia $1 COP), campos obligatorios vacíos, mandato/peaje con IVA.

- **`pipeline/prorateo.py`** — Prorrateo IVA Art. 490 E.T. `calcular_prorateo()` recibe dicts `{YYYY-MM: float}` para gravados/excluidos. Mandatos siempre van a no-deducible. Notas Crédito tienen signo negativo → reducen automáticamente el mes. `calcular_prorateo_simple()` retorna 100% deducible con columna de advertencia.

- **`pipeline/excel_writer.py`** — Escribe el workbook de 3 hojas (BASE_DATOS, VALIDACION, PRORRATEO_IVA). Colores en VALIDACION: rojo=ERROR, verde=OK. Columnas de dinero con formato `#,##0.00`.

- **`main.py`** — CLI via `argparse`. Deduplica pares PDF/XML en `_resolver_archivos()` antes del paralelismo. Procesa con `ThreadPoolExecutor`. Log por archivo; progreso cada 50 archivos.

- **`manage.py`** — Operator CLI. `init-db` corre `db/init.sql` directamente vía raw psycopg2 (no SQLAlchemy text, que para en el primer `;`). `create-org` crea organización + usuario owner.

- **`home_gate.py`** — Helpers puros sin Streamlit para la compuerta de login. `login_required()` devuelve `True` cuando `DATABASE_URL` está set. `get_auth_session()` valida que `st.session_state["auth"]` tenga las 4 claves requeridas (`user_id`, `org_id`, `role`, `email`).

- **`services/processor.py`** — Orquestación UI-agnóstica: extracción → validación → prorrateo → insert DB. `procesar()` devuelve `ResultadoProcesamiento` con los 3 DataFrames. Integra `db/database.py` para deduplicación por CUFE.

- **`services/processor_exogenas.py`** — Equivalente de `processor.py` para certificados de retención. Orquesta `exogenas/extractor.py` → DB.

- **`services/chatbot.py`** — Accounting Assistant multi-provider. Soporta Groq, OpenAI, Anthropic, Google. Selección dinámica de modelo. Tool use: `consultar_iva_mes`, `top_proveedores`, `buscar_factura`, `resumen_errores`, `resumen_general`.

- **`services/nomina.py`** — Procesador de nómina electrónica DIAN.

- **`utils/theme.py`** — Sistema de temas Dark/Light/System. `apply_theme()` inyecta CSS. `theme_selector()` muestra el radio en sidebar. Paletas `_DARK` / `_LIGHT` con tokens de color TaxOps.

- **`db/database.py`** — Capa SQLAlchemy UI-agnóstica. `db_available()` para degraded mode. `get_existing_cufes(org_id)` para deduplicación incremental. `insert_invoices_batch()` con `ON CONFLICT DO NOTHING`. `get_autorretenedores_nits()` desde DB con fallback a `autorretenedores.txt`.

- **`db/init.sql`** — Schema PostgreSQL multi-tenant: `organizations`, `users` (con `deleted_at` soft-hard delete), `clients`, `invoices`, `processing_sessions`, `autorretenedores`, `ingresos_prorateo`, `groups`, `user_groups`, `audit_logs`. UUID como PK, índices GIN trigram en campos de búsqueda.

- **`pipeline/autorretenedores.txt`** — 3.287 NITs DIAN (corte 25/02/2026). Cargado al inicio de `pipeline/extractor.py`. Para actualizar: reemplazar por nuevo archivo NIT-por-línea. En producción se carga desde tabla `autorretenedores` de PostgreSQL.

- **`exogenas/extractor.py`** (~1090 líneas) — Extractor de certificados de retención. Entry points: `extract_many(path)` → `list[dict]`, `extract_one(path)` → `dict`. Soporta PDF (pdfplumber + pytesseract para escaneados), imágenes (pytesseract 2×), Excel (.xlsx openpyxl / .xls xlrd), Word (.docx). Layouts soportados: Bodega de Moda standard, Tennis narrativo, RETE IVA bimestral, RTE ICA 4-col, SAP bilingüe (EL BUCANERO), Mekano ERP (ENTREAGUAS), MEDIFE/IRCC, PUBLIK MAGIC paréntesis, Narrativo base, MAYORISTA, SAN JUAN DE DIOS, QUIRUSTETIC, Multi-concepto tabla.
  - `_extract_direccion`: usa word boundaries `(?<!\w)AV(?!\w)` para no capturar "GRAVABLE", "AVABLE", "CLARANTES", nombres de empresa.
  - `_clean_city`: strip trailing artículos+blacklist, em-dash, requiere inicial mayúscula, any-significant-word check; `_TRAILING_NOISE` frozenset para artículos.
  - `_make_result`: strip prefijos "Retenedor:", "Señores:", "RETENIDO:", NIT prefix, headers inválidos "AÑO GRAVABLE"/"FECHA DE EXPEDICION".
  - `_fix_pct_as_amount(b, r)`: corrige retención=2.5 (porcentaje) → monto real (`b × r/100`) cuando `b > 10_000 and r ≤ 30 and r/b < 0.001`.

- **`api/routers/calendario.py`** — CRUD del calendario tributario DIAN. Lee/escribe `api/data/calendario_2026.json`. Actualizable sin redeploy vía PUT superadmin.

- **`api/data/calendario_2026.json`** — 31 eventos DIAN 2026 (fuente de verdad). Formato: `{id, fecha, titulo, descripcion, tipo, urgencia, articulo, alertaDias}`. Para actualizar año a año: PUT `/calendario/eventos` con el JSON del nuevo año.

### Data flow

```
PDF/XML → extract_one() → dict plano
                              ↓
                         validate(df) → df + validacion/observacion
                              ↓
                    calcular_prorateo(df, ingresos) → df_pror
                              ↓
              insert_invoices_batch() → PostgreSQL (ON CONFLICT DO NOTHING)
                              ↓
                    ResultadoProcesamiento → Streamlit UI / Excel
```

### Document types

| Type | Detection | Sign | IVA |
|---|---|---|---|
| `Nota Crédito` | "nota cr", stem `NC-*` | -1 | resta del mes |
| `Nota Débito` | "nota déb/deb", stem `ND-*` | +1 | suma al mes |
| `Mandato/Peaje` | "mandato", "peaje" | +1 | siempre no-deducible |
| `Documento Soporte` | "documento soporte" | +1 | normal |
| `Documento Equivalente` | "documento equivalente" | +1 | normal |
| `Factura Electrónica` | default | +1 | normal |

### Documento Equivalente — two sub-layouts

**POS layout** (e.g. SUPERMERCADO EL CAMPESINO): sección `"Datos del vendedor"` presente. Folio alfanumérico `POSE5217`. NIT emisor en sección vendedor.

**SPD layout** (e.g. EPM — prefijo DEE): sección `"Datos del emisor"` estándar. Detectado por ausencia de `"Datos del vendedor"`.

Distinción en runtime: `tiene_vendedor = bool(re.search(r'datos\s+del\s+vendedor', text, re.I))`.

### Multi-tenant DB schema

```
organizations (UUID, plan: free/starter/pro)
    └── users (role: owner/admin/contador · deleted_at para soft-hard delete)
    └── clients (empresas que gestiona cada contador)
    └── invoices (CUFE único por org — deduplicación automática)
    └── processing_sessions (historial de cargas con métricas)
    └── ingresos_prorateo (persiste ingresos por período)
    └── groups (módulos TEXT[] por grupo)
        └── user_groups (many-to-many users↔groups)
    └── audit_logs (trazabilidad completa: action, module, resource, details JSONB)
autorretenedores (reemplaza autorretenedores.txt en producción)
```

### FastAPI — rutas clave

| Método | Path | Guard | Descripción |
|--------|------|-------|-------------|
| POST | `/auth/login` | — | JWT access + refresh |
| POST | `/auth/register` | — | Crea org + owner |
| GET | `/admin/stats` | require_admin | Dashboard KPIs + charts |
| GET | `/admin/users` | require_admin | Lista usuarios (excluye deleted_at) |
| POST | `/admin/users` | require_admin | Crea usuario en la org |
| DELETE | `/admin/users/{id}/permanent` | require_owner | Anonymize + soft-hard delete |
| POST | `/admin/users/{id}/reactivate` | require_admin | Reactiva usuario inactivo |
| GET/POST | `/admin/groups` | require_admin/owner | CRUD de grupos |
| GET | `/admin/audit-logs` | require_admin | Logs con filtros module/action/email |
| GET | `/calendario/eventos` | get_current_user | Lista eventos DIAN del año en curso |
| PUT | `/calendario/eventos` | require_superadmin | Reemplaza todos los eventos (nuevo año) |
| POST | `/calendario/eventos` | require_superadmin | Agrega un evento individual |
| DELETE | `/calendario/eventos/{id}` | require_superadmin | Elimina un evento por ID |

Guards: `get_current_user` → `require_admin` (owner+admin) → `require_owner` (solo owner) → `require_superadmin` (emails en `TAXOPS_SUPERADMIN_EMAILS`)

### Key regex patterns

```python
_RE_FOLIO          # "Número de Factura:" — facturas y notas
_RE_FOLIO_DOC      # "Número de documento: [A-Za-z]..." — doc equivalente/soporte
_RE_EMISOR_NIT     # "Nit del Emisor:"
_RE_EMISOR_NOMBRE  # "Razón Social:" (primera ocurrencia = emisor)
_RE_VENDEDOR_NIT   # "Datos del vendedor ... Número de documento:" (POS)
_RE_RECEPTOR_NIT   # "Número Documento:" or "nit del adquir..."
_RE_ADQUIRIENTE_NIT # "NIT del adquiriente:" (POS)
```

Bug crítico resuelto: `_search_money_near(text, "IVA", line_start=True)` — requiere IVA al inicio de línea para no capturar números de calle en `"Dirección: CALLE 26"`.

### Tests

```
tests/
├── test_extractor.py          # 44 unit tests — funciones puras + mocked PDF
├── test_validator.py          # 19 unit tests — reglas de validación
├── test_prorateo.py           # 12 unit tests — Art. 490 ET
├── test_chatbot.py            # 11 unit tests — sin llamar API real
├── test_e2e.py                # 32 end-to-end (se saltan si no hay PDFs)
├── test_auth.py               # auth helpers y JWT
├── test_home_login_gate.py    # home_gate.py sin Streamlit
├── test_manage.py             # manage.py CLI (init-db, create-org)
├── test_database_lazy.py      # db/database.py lazy-load / degraded mode
├── test_get_org_id.py         # utils/org_id.py
├── test_processor_db.py       # services/processor.py con DB
└── test_processor_exogenas_db.py  # services/processor_exogenas.py con DB
```

### Bugs pendientes — extractor exógenas (próxima sesión)

1. **`RETE FTE 2025 MA TERESA MARTINEZ.jpeg`** → "No se encontraron montos" — OCR imagen baja calidad; considerar preprocesamiento (binarización/contraste).
2. **`RTE FTE 2025 CAROLINA ARISTIZBAL.pdf`** → "No se encontraron montos" — formato minimalista no reconocido; extraer texto y revisar.
3. **IND FANTASIA ICA** → base=251231, ret=2025 — fecha "25.12.31" parseada como base; año "2025" como retención. Fix: en ICA fallback, aplicar `0.003 < r/b < 0.02` y descartar números < 1000.
4. **LEAM SAS** → retención=2500 — `_RE_TOTAL_LINE` captura "2.500" (podría ser % no monto). Fix: validar `r/b > 0.001` antes de retornar.
5. **EL BUCANERO RTE IVA** → razón social vacía — SAP bilingüe para IVA tiene layout diferente al de renta.
6. **COMERTEX** → razón social="GIRON", nit=3144113024 — NIT 10 dígitos clasificado como tipo_doc=31; podría ser cédula (13). Fix: verificar si hay "NIT:" o "Cédula:" en el texto.
7. **Script auto-update calendario**: Parsear PDF DIAN anual y generar `calendario_YYYY.json` automáticamente.

### Próximos pasos

- **Rate limiting**: sin throttling por organización
- **Invitaciones por email**: hoy solo el owner puede crear usuarios directamente
- **Permisos por grupo**: grupos tienen `modules[]` pero el frontend no bloquea rutas por grupo todavía
