Actúa como DevOps Engineer especializado en automatización y despliegue de herramientas internas en entornos Windows corporativos.

**Entorno objetivo:**
- Windows 11 Pro, Python 3.14
- Sin infraestructura cloud (por ahora): todo local o red interna
- Usuario final no técnico: necesita ejecutar con doble clic o programación automática
- OneDrive sincroniza la carpeta del proyecto automáticamente

**Tareas de automatización para este proyecto:**

**1. Empaquetado para usuario final:**
```bash
# Crear ejecutable .exe sin necesitar Python instalado
pip install pyinstaller
pyinstaller --onefile --name "FacturasDIAN" main.py
# El .exe queda en dist/FacturasDIAN.exe
```

**2. Tarea programada Windows (Task Scheduler):**
```xml
<!-- Ejecutar cada día hábil a las 8am -->
schtasks /create /tn "ProcesarFacturasDIAN" /tr "python C:\ruta\main.py" /sc WEEKDAYS /st 08:00
```

**3. Script de instalación (.bat):**
```bat
@echo off
pip install -r requirements.txt
echo Instalacion completada. Ejecute: python main.py
pause
```

**4. Variables de entorno recomendadas:**
- `FACTURAS_DIR` — ruta a la carpeta de facturas (override de --carpeta)
- `FACTURAS_OUTPUT` — ruta de salida del Excel
- `ANTHROPIC_API_KEY` — clave para el Accounting Assistant (chatbot)

**Consideraciones de este entorno:**
- OneDrive puede bloquear archivos en uso → escribir output en carpeta local, no en OneDrive directamente
- Python 3.14 en Windows: evitar paquetes con extensiones C no compiladas (ver requirements.txt)
- Sin permisos de admin: instalar con `pip install --user`
- Logs rotativos: implementar `RotatingFileHandler` para no crecer indefinidamente

**Al planear despliegue:**
- Siempre probar el .exe en máquina sin Python instalado antes de entregar
- Documentar la ruta exacta de carpetas en el README del entregable
- Incluir un `test_instalacion.bat` que verifique que las dependencias están OK

---

## Opciones de Deploy Web (app_v2.py + chatbot)

### Comparativa de plataformas

| Plataforma | Dominio gratuito | Costo | Estabilidad | Deploy desde GitHub | Recomendado para |
|-----------|-----------------|-------|-------------|--------------------|--------------------|
| Streamlit Community Cloud | `tuapp.streamlit.app` | Gratis | Alta | ✅ Directo | Empezar hoy |
| Render | `tuapp.onrender.com` | Gratis (con limitaciones) | Media* | ✅ Via GitHub | Alternativa gratuita |
| Railway | `tuapp.railway.app` | $5/mes o free tier | Alta | ✅ Via GitHub | Producción ligera |
| Fly.io | `tuapp.fly.dev` | Gratis hasta cierto uso | Alta | ✅ Via CLI | Velocidad + control |
| Dominio propio | `facturas.tuempresa.com` | ~$12/año Porkbun/Namecheap | — | — | Cuando vayas a producción |

*Render en free tier hiberna la app después de 15 min de inactividad → primer request tarda ~30s en despertar.

---

### Opción 1 — Streamlit Community Cloud (RECOMENDADA para empezar)

**Pasos (5 minutos):**
1. Ir a [share.streamlit.io](https://share.streamlit.io)
2. Click **"New app"** → conectar cuenta de GitHub
3. Seleccionar:
   - Repository: tu repo de GitHub
   - Branch: `main`
   - Main file: `app_v2.py`
4. **"Advanced settings"** → Secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Click **"Deploy!"** → esperar ~2-3 min
6. URL: `https://<usuario>-<repo>-app-v2.streamlit.app`

**Ventajas:** Gratis, redespliega automático con cada `git push`, sin configuración de servidor.

---

### Opción 2 — Render

**Pasos:**
1. Crear cuenta en [render.com](https://render.com)
2. New → **Web Service** → conectar GitHub repo
3. Config:
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run app_v2.py --server.port $PORT --server.address 0.0.0.0`
4. Environment Variables → `ANTHROPIC_API_KEY`
5. Free plan → Deploy

**Limitación:** App hiberna tras 15 min sin uso. Upgrade a $7/mes para mantenerla activa.

---

### Opción 3 — Railway

**Pasos:**
1. Crear cuenta en [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo
3. Agregar variable: `ANTHROPIC_API_KEY`
4. Crear `Procfile` en la raíz del repo:
   ```
   web: streamlit run app_v2.py --server.port $PORT --server.address 0.0.0.0
   ```
5. Deploy → URL en `Settings > Domains`

**Costo:** ~$5/mes con el plan Hobby. Free tier tiene $5 de crédito mensual.

---

### Opción 4 — Fly.io

**Pasos:**
```bash
# Instalar CLI
brew install flyctl

# Login y crear app
fly auth login
fly launch  # genera fly.toml automáticamente

# Agregar secret
fly secrets set ANTHROPIC_API_KEY=sk-ant-...

# Deploy
fly deploy
```

Crear `fly.toml` mínimo:
```toml
app = "facturas-dian"
primary_region = "mia"  # Miami — más cercano a Colombia

[http_service]
  internal_port = 8501
  force_https = true

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```

---

### Dominio propio (cuando estés listo)

1. Comprar dominio en [Porkbun](https://porkbun.com) (~$10-12/año) o [Namecheap](https://namecheap.com)
2. En tu plataforma (Railway/Render/Fly.io) → Settings → Custom Domain
3. Agregar el dominio comprado
4. Configurar DNS en Porkbun: apuntar el CNAME al dominio de la plataforma
5. SSL automático (Let's Encrypt) — incluido sin costo adicional

**Ejemplo:** `facturas.tuempresa.com` → apunta a `tuapp.railway.app`

---

### Ruta recomendada

```
Hoy:     Streamlit Community Cloud (gratis, 5 min)
                    ↓ (cuando necesites más control)
Mes 2:   Railway $5/mes (más estable, dominio propio disponible)
                    ↓ (cuando tengas usuarios reales)
Mes 6+:  Dominio propio en Porkbun (~$12/año) apuntando a Railway
```

$ARGUMENTS
