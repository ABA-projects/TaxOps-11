# TaxOps — Guía de instalación

Tres formas de usar TaxOps según tu entorno.

---

## Opción 1 — Local (sin Docker)

Ideal para pruebas rápidas o uso individual en tu PC.

### Requisitos
- Python 3.10 o superior
- Groq API Key gratuita: https://console.groq.com

### Pasos

```bash
# 1. Clonar el repositorio (o descomprimir el ZIP)
git clone <url-repo>
cd proyecto-facturas

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate        # Mac / Linux
.venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key
mkdir -p .streamlit
# Crear .streamlit/secrets.toml con el siguiente contenido:
echo 'GROQ_API_KEY = "gsk_tu_clave_aqui"' > .streamlit/secrets.toml

# 5. Ejecutar
streamlit run Home.py
```

Abre `http://localhost:8501` en el navegador.

> **Nota:** Sin PostgreSQL, los datos solo persisten durante la sesión (se pierden al cerrar el navegador). Toda la funcionalidad de procesamiento, analítica y chatbot funciona igual.

---

## Opción 2 — Docker (recomendado para equipos)

Incluye PostgreSQL con volumen persistente. Los datos se conservan entre sesiones.

### Requisitos
- Docker Desktop instalado
- Groq API Key

### Pasos

```bash
# 1. Copiar configuración
cp .env.example .env
# Editar .env: completar POSTGRES_PASSWORD y GROQ_API_KEY

# 2. Primera vez (construye la imagen ~3 min)
docker-compose up --build

# Siguientes veces
docker-compose up -d

# Detener
docker-compose down

# Detener y borrar datos de DB
docker-compose down -v
```

URLs:
- App: http://localhost:8501
- Adminer (gestión DB): http://localhost:8080

---

## Opción 3 — Instalable con pip (distribución interna)

Permite instalar TaxOps como un comando en cualquier PC, igual que cualquier paquete Python.

### Construir el paquete (solo el desarrollador lo hace una vez)

```bash
pip install build
python -m build
# Genera: dist/taxops-0.2.0-py3-none-any.whl
```

### Instalar en cada PC

```bash
# Instalar desde el archivo .whl
pip install taxops-0.2.0-py3-none-any.whl

# Configurar API key (una sola vez por PC)
mkdir -p ~/.streamlit
echo 'GROQ_API_KEY = "gsk_tu_clave_aqui"' >> ~/.streamlit/secrets.toml

# Ejecutar desde cualquier directorio
taxops
```

### Actualizar a nueva versión

```bash
pip install --upgrade taxops-0.2.0-py3-none-any.whl
```

### Ventajas del instalable
- No requiere clonar el repo
- Se ejecuta con un solo comando: `taxops`
- Funciona en cualquier directorio
- Los datos de cada sesión se guardan donde el usuario los descargue (Excel)

### Limitaciones del instalable
- Sin PostgreSQL (a menos que el usuario configure `DATABASE_URL` en su entorno)
- Requiere Python 3.10+ instalado en la PC destino
- Para una distribución completamente sin Python, usar PyInstaller (ver abajo)

---

## Opción 4 — Ejecutable standalone con PyInstaller (avanzado)

Para distribuir a usuarios sin Python instalado.

```bash
pip install pyinstaller
pyinstaller --onefile --name taxops cli.py \
  --add-data "pages:pages" \
  --add-data "pipeline:pipeline" \
  --add-data "exogenas:exogenas" \
  --add-data "services:services" \
  --add-data "utils:utils" \
  --add-data "db:db" \
  --add-data "static:static" \
  --add-data "Home.py:."
```

> **Nota:** Streamlit no está diseñado para PyInstaller. Esta opción tiene limitaciones y requiere pruebas adicionales. Se recomienda la Opción 3 (pip) para distribución interna.

---

## Configuración de API Key

La API key de Groq se puede configurar de tres formas (en orden de prioridad):

| Método | Ubicación | Alcance |
|--------|-----------|---------|
| Variable de entorno | `GROQ_API_KEY=gsk_...` | Sistema / Docker |
| Secrets global | `~/.streamlit/secrets.toml` | Todos los proyectos Streamlit |
| Secrets local | `.streamlit/secrets.toml` | Solo este proyecto |

Obtén tu clave gratis en: https://console.groq.com (límite generoso en el plan free).
