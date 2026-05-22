# Guía: Configurar API Key de Groq (modelo gratuito)

Groq ofrece acceso gratuito a modelos de lenguaje de alta velocidad (llama-3.3-70b).
No requiere tarjeta de crédito para el tier gratuito.

---

## 1. Obtener la API Key (3 minutos)

1. Ir a **[console.groq.com](https://console.groq.com)**
2. Click **"Sign Up"** → crear cuenta con Google o email
3. Una vez dentro: menú izquierdo → **"API Keys"**
4. Click **"Create API Key"**
5. Darle un nombre: `facturas-dian-prod`
6. Copiar la clave — empieza con `gsk_...`

> La clave solo se muestra una vez. Guárdala de inmediato.

---

## 2. Límites del tier gratuito

| Modelo | Tokens/minuto | Requests/minuto | Requests/día |
|--------|--------------|-----------------|--------------|
| llama-3.3-70b-versatile | 6,000 | 30 | 1,000 |

Para un contador procesando facturas en sesiones normales, estos límites son más que suficientes.

---

## 3. Configurar en local (desarrollo) — sin export, sin .env

Este proyecto usa **Streamlit Secrets** como mecanismo único para local y cloud.
No necesitas instalar nada extra ni ejecutar comandos antes de correr la app.

### Paso único: editar `.streamlit/secrets.toml`

El archivo ya existe en el proyecto. Solo reemplaza el placeholder:

```toml
# .streamlit/secrets.toml
GROQ_API_KEY = "gsk_PEGA_TU_CLAVE_AQUI"
```

Cambia `gsk_PEGA_TU_CLAVE_AQUI` por tu clave real y guarda. Listo.

```bash
python3 -m streamlit run Home.py
# La app lee la clave automáticamente — sin export, sin configuración extra
```

> **Seguridad:** `.streamlit/secrets.toml` ya está en `.gitignore`.
> Nunca se subirá a GitHub aunque hagas `git add .`

### Por qué no .env

| Característica | `.env` + python-dotenv | Streamlit Secrets |
|---------------|----------------------|-------------------|
| Librería extra | ✅ Requiere `python-dotenv` | ❌ No requiere nada |
| Funciona en Streamlit Cloud | ❌ No | ✅ Sí, mismo mecanismo |
| Un solo lugar de config | ❌ `.env` local + secrets en cloud | ✅ `.streamlit/secrets.toml` siempre |
| `export` antes de correr | ❌ No (si usas dotenv) | ❌ No |

---

## 4. Configurar en Streamlit Community Cloud (producción)

Ver guía completa en `docs/guia-streamlit-cloud.md`, sección "Secrets".

Resumen rápido:
1. En el dashboard de tu app → botón **"⋮"** → **"Settings"**
2. Pestaña **"Secrets"**
3. Agregar:
```toml
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
```
4. Click **"Save"** → la app se reinicia automáticamente

---

## 5. Verificar que funciona

```python
# test_groq.py — correr una vez para verificar
from groq import Groq
import os

client = Groq(api_key=os.environ["GROQ_API_KEY"])
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Responde solo: OK"}],
    max_tokens=10,
)
print(response.choices[0].message.content)
# Expected: "OK"
```

```bash
python3 test_groq.py
# Expected: OK
```

---

## 6. Errores comunes

| Error | Causa | Solución |
|-------|-------|---------|
| `AuthenticationError` | Clave incorrecta o expirada | Regenerar en console.groq.com |
| `RateLimitError` | Superaste 30 req/min | Esperar 1 minuto o reducir frecuencia |
| `GROQ_API_KEY not set` | Variable de entorno no configurada | Verificar `export` o archivo `.env` |

---

## 7. Rotación de claves (buenas prácticas)

- Crear una clave por entorno: `facturas-dev`, `facturas-prod`
- Revocar claves viejas desde el dashboard si sospechas que se filtraron
- Nunca hardcodear la clave en el código fuente
- Nunca commitear `.env` a GitHub
