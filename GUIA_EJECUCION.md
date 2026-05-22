# Guía de Ejecución de Pruebas

---

## Requisitos previos

```bash
# Instalar dependencias (incluye pytest y pytest-cov)
pip install -r requirements.txt

# Verificar instalación
python -m pytest --version
# pytest 9.x.x
```

---

## Comandos de ejecución

### Ejecutar todas las pruebas

```bash
python -m pytest
```

Resultado esperado (sin PDFs reales):
```
82 passed, 25 skipped in 2.18s
```

Resultado esperado (con PDFs en facturas/):
```
107 passed in 12.5s
```

---

### Pruebas unitarias — siempre disponibles, sin PDFs

```bash
# Solo pruebas unitarias (recomendado en desarrollo diario)
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py

# Con salida detallada
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py -v
```

---

### Pruebas end-to-end — requieren PDFs en facturas/

```bash
# Solo E2E
python -m pytest tests/test_e2e.py -v

# Solo las pruebas que NO necesitan PDFs (deduplicación de archivos)
python -m pytest tests/test_e2e.py::TestResolverArchivos -v
```

Si los PDFs no están, los tests de extracción y pipeline se muestran como `SKIPPED` — no es un error.

---

### Por módulo individual

```bash
python -m pytest tests/test_extractor.py -v   # 44 tests de extracción
python -m pytest tests/test_validator.py -v   # 19 tests de validación
python -m pytest tests/test_prorateo.py  -v   # 12 tests de prorrateo
python -m pytest tests/test_e2e.py      -v    # 32 tests end-to-end
```

---

### Por clase o test específico

```bash
# Una clase completa
python -m pytest tests/test_extractor.py::TestCalcRetencion -v

# Un test específico
python -m pytest tests/test_extractor.py::TestSearchMoneyNear::test_iva_line_start_evita_calle -v

# Todos los tests de retención y validación de CUFE
python -m pytest -k "retencion or cufe" -v
```

---

### Con cobertura de código

```bash
# Reporte en consola
python -m pytest --cov=. --cov-report=term-missing

# Excluir carpetas que no son módulos del sistema
python -m pytest --cov=. --cov-report=term-missing --cov-omit="tests/*,logs/*"
```

Ejemplo de salida:
```
Name               Stmts   Miss  Cover
--------------------------------------
extractor.py         120      8    93%
validator.py          45      2    96%
prorateo.py           38      1    97%
excel_writer.py       52     12    77%
main.py               48      6    88%
--------------------------------------
TOTAL                303     29    90%
```

---

### Filtrar por palabra clave

```bash
# Todos los tests relacionados con IVA
python -m pytest -k "iva" -v

# Tests de mandatos y notas crédito
python -m pytest -k "mandato or nota_credito" -v

# Tests de formato de números
python -m pytest -k "colombiano or americano" -v
```

---

### Detener al primer fallo

```bash
python -m pytest -x
```

Útil cuando se está corrigiendo un bug: para en el primer error y muestra el detalle completo.

---

### Ver los tests más lentos

```bash
python -m pytest --durations=10
```

Muestra los 10 tests que más tiempo tomaron. Los E2E con PDFs reales suelen aparecer aquí (~1s cada uno).

---

## Interpretar resultados

### Símbolos en la salida

| Símbolo | Significado |
|---|---|
| `.` | Test pasó |
| `F` | Test falló (resultado inesperado) |
| `E` | Error de ejecución (excepción no esperada) |
| `s` | Test saltado (`SKIPPED`) — PDF no disponible |
| `x` | Test marcado como esperado que falle (`xfail`) |

### Salida de un test que falló

```
FAILED tests/test_extractor.py::TestCalcRetencion::test_normal_2_5_pct

FAILURES
test_normal_2_5_pct
  assert _calc_retencion(291400.0, "899999143") == 7285.0
  AssertionError: assert 7300.0 == 7285.0
```

Lectura: la función devolvió `7300.0` pero se esperaba `7285.0`. Indica un cambio en el porcentaje de retención o en la base de cálculo.

### Salida de un test saltado

```
SKIPPED tests/test_e2e.py::TestExtraccionSTK602558::test_folio
  Reason: PDFs de prueba no disponibles (descarga de la DIAN requerida)
```

Normal cuando los PDFs están en `.gitignore`. No es un error.

---

## Flujo recomendado

### Durante desarrollo (cambios al código)

```bash
# 1. Correr unitarias rápido antes de guardar
python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py -q

# 2. Si hay fallos, ver detalle del primero
python -m pytest tests/test_extractor.py -x -v

# 3. Antes de procesar facturas reales, correr E2E
python -m pytest tests/test_e2e.py -v
```

### Al recibir una nueva factura que no extrae bien

```bash
# 1. Correr en modo debug para ver qué sale
python -c "
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
with pdfplumber.open('facturas/NUEVA_FACTURA.pdf') as p:
    for i, pg in enumerate(p.pages):
        print(f'--- Pagina {i+1} ---')
        print(pg.extract_text())
"

# 2. Probar la extracción directa
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from extractor import extract_one
from pathlib import Path
r = extract_one(Path('facturas/NUEVA_FACTURA.pdf'))
for k, v in r.items(): print(f'{k}: {v}')
"

# 3. Agregar el test al archivo correspondiente y verificar
python -m pytest tests/test_extractor.py -v -k "nueva"
```

### Antes de procesar un lote grande (800 facturas)

```bash
# Verificar que todo está en orden
python -m pytest -q

# Si pasan todas las unitarias, procesar el lote
python main.py --workers 8
```

---

## Activar los tests E2E (con PDFs reales)

Los tests E2E se activan automáticamente cuando los PDFs de prueba están en `facturas/`:

```
facturas/
├── 3e7b57a72f36a2df...fd3.pdf   <- STK-602558 (SATENA)
└── 7732b1b30b906ea7...cd.pdf    <- EB-33355 (AGROTECNICO)
```

Una vez copiados:
```bash
python -m pytest tests/test_e2e.py -v
# Resultado esperado: 32 passed
```

---

## Agregar pytest al flujo de trabajo

Si quieres correr las pruebas automáticamente cada vez que guardas un archivo, instala `pytest-watch`:

```bash
pip install pytest-watch
ptw tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py
```

Monitorea cambios y ejecuta los tests unitarios al instante.

---

## Resumen rápido de comandos

| Necesidad | Comando |
|---|---|
| Todas las pruebas | `python -m pytest` |
| Solo unitarias | `python -m pytest tests/test_extractor.py tests/test_validator.py tests/test_prorateo.py` |
| Solo E2E | `python -m pytest tests/test_e2e.py -v` |
| Con cobertura | `python -m pytest --cov=. --cov-report=term-missing` |
| Parar al primer fallo | `python -m pytest -x` |
| Buscar por nombre | `python -m pytest -k "iva"` |
| Tests más lentos | `python -m pytest --durations=10` |

---

## Docker y despliegue local (TaxOps)

### Requisitos
- Docker ≥ 24 y Docker Compose ≥ v2 instalados

### Primer arranque

```bash
cd repo-andres/proyecto-facturas

# 1. Crear .env desde la plantilla (solo la primera vez)
cp .env.example .env
# Editar .env: ajusta POSTGRES_PASSWORD y verifica GROQ_API_KEY

# 2. Construir imagen y levantar todos los servicios
docker compose up --build
```

Cuando aparezca `You can now view your streamlit app in your browser`, los servicios están listos:

| Servicio | URL | Descripción |
|---|---|---|
| TaxOps App | http://localhost:8501 | Interfaz Streamlit |
| Adminer | http://localhost:8080 | UI web para PostgreSQL |
| PostgreSQL | localhost:5432 | Base de datos (directo) |

### Credenciales Adminer (desarrollo local)
- Sistema: `PostgreSQL`
- Servidor: `db`
- Usuario: `taxops`
- Contraseña: `taxops_local_2026` (o la que pusiste en `.env`)
- Base de datos: `taxops`

### Verificar esquema de base de datos

```bash
docker exec -it taxops_db psql -U taxops -d taxops -c "\dt"
```

Deben aparecer las 7 tablas: `organizations`, `users`, `clients`, `invoices`,
`processing_sessions`, `autorretenedores`, `ingresos_prorateo`.

### Comandos cotidianos

```bash
# Levantar en segundo plano (sin rebuild)
docker compose up -d

# Ver logs en vivo de la app
docker compose logs -f app

# Reiniciar solo la app (tras cambios en código)
docker compose restart app

# Parar todos los servicios
docker compose down

# Parar Y borrar la base de datos (⚠️ irreversible)
docker compose down -v
```

### Rebuild tras cambios en requirements.txt o Dockerfile

```bash
docker compose build --no-cache app
docker compose up -d
```

### Variables de entorno principales (`.env`)

| Variable | Descripción |
|---|---|
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL |
| `DATABASE_URL` | DSN completo para SQLAlchemy |
| `GROQ_API_KEY` | Clave API para el chatbot |
| `TAXOPS_ENV` | `development` / `staging` / `production` |
| `TAXOPS_ORG_ID` | UUID de la organización activa |

### Estructura de archivos Docker

```
proyecto-facturas/
├── Dockerfile            # Multi-stage build (builder + runtime)
├── docker-compose.yml    # App + PostgreSQL + Adminer
├── .env                  # Variables locales (NO commitear)
├── .env.example          # Plantilla para nuevos entornos
└── db/
    ├── init.sql          # Esquema PostgreSQL (corre automático al crear DB)
    └── database.py       # Capa SQLAlchemy UI-agnóstica
```
