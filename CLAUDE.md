# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit app (entry point: Home.py)
python -m streamlit run Home.py

# Run CLI processor
python main.py
python main.py --carpeta /ruta/facturas --ingresos "2026-04:5000000,2026-03:4500000"
python main.py --workers 8

# Run file watcher (requires: pip install watchdog>=4.0.0)
python watcher.py

# Docker — desarrollo local completo (app + PostgreSQL + Adminer)
cp .env.example .env          # rellenar POSTGRES_PASSWORD y GROQ_API_KEY
docker-compose up --build     # primera vez (~3 min)
docker-compose up             # siguientes veces
docker-compose down -v        # destruir incluyendo volumen postgres

# URLs locales Docker
#   App:     http://localhost:8501
#   Adminer: http://localhost:8080  (Server: db, User: taxops)

# Run tests
python -m pytest
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py tests/test_chatbot.py
python -m pytest tests/test_e2e.py -v    # requiere PDFs en facturas/
python -m pytest --cov=. --cov-report=term-missing
```

## Architecture

TaxOps procesa facturas electrónicas DIAN (PDF/XML) colombianas en un pipeline:
`facturas/` → `facturas/extractor.py` → `validator.py` → `prorateo.py` → `excel_writer.py` / PostgreSQL

**Stack:** FastAPI 0.115 · Next.js 15.3 (React 19) · PostgreSQL 16 · SQLAlchemy · Groq/OpenAI/Anthropic/Google · Docker · Railway

### Module responsibilities

- **`facturas/extractor.py`** — Parsing de documentos. `extract_one(path)` es el entry point principal (thread-safe). Despacha a `extract_xml()` o `extract_pdf()` por extensión. XML tiene prioridad cuando coexisten ambos. Carga `autorretenedores.txt` al inicio como frozenset O(1). Fallback de fecha desde nombre de carpeta (`_date_from_folder`).

- **`facturas/validator.py`** — Validación stateless sobre DataFrame. `validate()` agrega columnas `validacion` (OK/ERROR) y `observacion`. Verifica: formato CUFE/CUDE (96 hex), duplicados, formato NIT, subtotal+IVA≈total (tolerancia $1 COP), campos obligatorios vacíos, mandato/peaje con IVA.

- **`facturas/prorateo.py`** — Prorrateo IVA Art. 490 E.T. `calcular_prorateo()` recibe dicts `{YYYY-MM: float}` para gravados/excluidos. Mandatos siempre van a no-deducible. Notas Crédito tienen signo negativo → reducen automáticamente el mes. `calcular_prorateo_simple()` retorna 100% deducible con columna de advertencia.

- **`facturas/excel_writer.py`** — Escribe el workbook de 3 hojas (BASE_DATOS, VALIDACION, PRORRATEO_IVA). Colores en VALIDACION: rojo=ERROR, verde=OK. Columnas de dinero con formato `#,##0.00`.

- **`main.py`** — CLI via `argparse`. Deduplica pares PDF/XML en `_resolver_archivos()` antes del paralelismo. Procesa con `ThreadPoolExecutor`. Log por archivo; progreso cada 50 archivos.

- **`watcher.py`** — Watcher local con `watchdog` (no incluido en requirements.txt cloud). Monitorea `facturas/` recursivamente. Debounce: 10s. Espera 5s al detectar nuevo archivo. Requiere `pip install watchdog>=4.0.0`.

- **`Home.py`** — Landing page TaxOps. Usa `utils/theme.py` para Dark/Light/System. Botones CTA con `st.switch_page()`.

- **`services/processor.py`** — Orquestación UI-agnóstica: extracción → validación → prorrateo → insert DB. `procesar()` devuelve `ResultadoProcesamiento` con los 3 DataFrames. Integra `db/database.py` para deduplicación por CUFE.

- **`services/chatbot.py`** — Accounting Assistant multi-provider. Soporta Groq, OpenAI, Anthropic, Google. Selección dinámica de modelo. Tool use: `consultar_iva_mes`, `top_proveedores`, `buscar_factura`, `resumen_errores`, `resumen_general`.

- **`utils/theme.py`** — Sistema de temas Dark/Light/System. `apply_theme()` inyecta CSS. `theme_selector()` muestra el radio en sidebar. Paletas `_DARK` / `_LIGHT` con tokens de color TaxOps.

- **`db/database.py`** — Capa SQLAlchemy UI-agnóstica. `db_available()` para degraded mode. `get_existing_cufes(org_id)` para deduplicación incremental. `insert_invoices_batch()` con `ON CONFLICT DO NOTHING`. `get_autorretenedores_nits()` desde DB con fallback a `autorretenedores.txt`.

- **`db/init.sql`** — Schema PostgreSQL multi-tenant: `organizations`, `users` (con `deleted_at` soft-hard delete), `clients`, `invoices`, `processing_sessions`, `autorretenedores`, `ingresos_prorateo`, `groups`, `user_groups`, `audit_logs`. UUID como PK, índices GIN trigram en campos de búsqueda.

- **`facturas/autorretenedores.txt`** — 3.287 NITs DIAN (corte 25/02/2026). Cargado al inicio de `facturas/extractor.py`. Para actualizar: reemplazar por nuevo archivo NIT-por-línea. En producción se carga desde tabla `autorretenedores` de PostgreSQL.

- **`taxops-web/app/icon.svg`** — Favicon Next.js App Router (auto-detected). Logo TaxOps Tax naranja + Ops azul marino.

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

Guards: `get_current_user` → `require_admin` (owner+admin) → `require_owner` (solo owner) → `require_superadmin` (emails en TAXOPS_SUPERADMIN_EMAILS)

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
├── test_extractor.py   # 44 unit tests — funciones puras + mocked PDF
├── test_validator.py   # 19 unit tests — reglas de validación
├── test_prorateo.py    # 12 unit tests — Art. 490 ET
├── test_chatbot.py     # 11 unit tests — sin llamar API real
└── test_e2e.py         # 32 end-to-end (se saltan si no hay PDFs)
```

### CI/CD

- **`.github/workflows/ci.yml`** — flake8 + mypy (api-lint), pytest pipeline tests (api-test), ESLint + tsc (web-lint), next build (web-build). Corre en push/PR a main.
- **`.github/workflows/deploy.yml`** — Se activa cuando CI pasa. Llama Railway GraphQL API para redeploy. **Si Railway tiene auto-deploy ON en el repo, desactivarlo para evitar doble deploy.** Secretos requeridos: `RAILWAY_API_TOKEN`, `RAILWAY_SERVICE_API_ID`, `RAILWAY_SERVICE_WEB_ID`.
- **`taxops-web/next.config.ts`** — `INTERNAL_API_URL` se bake en build time. Tiene `.trim()` defensivo. Fallback: `NEXT_PUBLIC_API_URL` → `http://localhost:8000`.
- **Alembic**: `api/alembic/versions/001_baseline.py` (marker), `002_audit_groups.py` (deleted_at + groups + audit_logs).

### Próximos pasos

- **Rate limiting**: sin throttling por organización
- **Invitaciones por email**: hoy solo el owner puede crear usuarios directamente
- **Permisos por grupo**: grupos tienen `modules[]` pero el frontend no bloquea rutas por grupo todavía

### Bugs pendientes — extractor exógenas (próxima sesión)

1. **`RETE FTE 2025 MA TERESA MARTINEZ.jpeg`** → "No se encontraron montos" — OCR imagen baja calidad; considerar preprocesamiento (binarización/contraste).
2. **`RTE FTE 2025 CAROLINA ARISTIZBAL.pdf`** → "No se encontraron montos" — formato minimalista no reconocido; extraer texto y revisar.
3. **IND FANTASIA ICA** → base=251231, ret=2025 — fecha "25.12.31" parseada como base; año "2025" como retención. Fix: en ICA fallback, aplicar `0.003 < r/b < 0.02` y descartar números < 1000.
4. **LEAM SAS** → retención=2500 — `_RE_TOTAL_LINE` captura "2.500" (podría ser % no monto). Fix: validar `r/b > 0.001` antes de retornar.
5. **EL BUCANERO RTE IVA** → razón social vacía — SAP bilingüe para IVA tiene layout diferente al de renta.
6. **COMERTEX** → razón social="GIRON", nit=3144113024 — NIT 10 dígitos clasificado como tipo_doc=31; podría ser cédula (13). Fix: verificar si hay "NIT:" o "Cédula:" en el texto.
7. **Script auto-update calendario**: Parsear PDF DIAN anual y generar `calendario_YYYY.json` automáticamente.
