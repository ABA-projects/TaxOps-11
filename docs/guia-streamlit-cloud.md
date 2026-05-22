# Guía: Deploy en Streamlit Community Cloud

Streamlit Community Cloud es la plataforma gratuita oficial para desplegar apps Streamlit.
Se conecta directamente a tu repositorio de GitHub y redespliega automáticamente en cada push.

---

## Requisitos previos

- [ ] Cuenta de GitHub con el repo del proyecto
- [ ] `app_v2.py` en la raíz del repo (o en una subcarpeta)
- [ ] `requirements.txt` actualizado (incluye `groq>=0.11` y `streamlit>=1.36`)
- [ ] Código pusheado a la rama `main`

---

## 1. Preparar el repositorio

### Verificar que requirements.txt está completo

```bash
cat requirements.txt
```

Debe incluir al menos:
```
pdfplumber>=0.11.4
lxml>=5.3.0
pandas>=2.3.0
openpyxl>=3.1.5
streamlit>=1.36.0
watchdog>=4.0.0
groq>=0.11
```

### Verificar .gitignore

Asegurarse de que estos archivos NO se suban a GitHub:
```
# .gitignore
.env
*.pyc
__pycache__/
logs/
output/
outputs/
facturas/
*.xlsx
```

### Push a GitHub

```bash
git add .
git commit -m "feat: add app_v2 with chatbot ready for cloud deploy"
git push origin main
```

---

## 2. Crear cuenta en Streamlit Community Cloud

1. Ir a **[share.streamlit.io](https://share.streamlit.io)**
2. Click **"Sign up"** → **"Continue with GitHub"**
3. Autorizar el acceso a tu cuenta de GitHub
4. Listo — ya estás en el dashboard

---

## 3. Crear el deploy

1. Click **"New app"** (botón azul arriba a la derecha)
2. Seleccionar **"From existing repo"**
3. Configurar:

| Campo | Valor |
|-------|-------|
| Repository | `tu-usuario/proyecto-facturas` |
| Branch | `main` |
| Main file path | `app_v2.py` |
| App URL (opcional) | `facturas-dian` → genera `facturas-dian.streamlit.app` |

4. Click **"Advanced settings"** antes de hacer deploy

---

## 4. Configurar Secrets (API Keys)

En **"Advanced settings"** → pestaña **"Secrets"**:

```toml
# Mismo formato que tu .streamlit/secrets.toml local — copia y pega
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
```

> Streamlit lee estos secrets con `st.secrets["GROQ_API_KEY"]` — el mismo código
> que usa tu archivo local. **Un solo mecanismo para local y cloud.**
> Los secrets nunca aparecen en los logs ni en el navegador.

Click **"Save"**

---

## 5. Deploy

Click **"Deploy!"**

Streamlit:
1. Clona tu repo
2. Instala `requirements.txt` (~2-3 min la primera vez)
3. Arranca la app
4. Te da la URL pública

URL resultante:
```
https://facturas-dian.streamlit.app
```
o si no elegiste nombre personalizado:
```
https://tu-usuario-proyecto-facturas-app-v2-xxxxxxxx.streamlit.app
```

---

## 6. Flujo de actualizaciones

Cada vez que hagas `git push origin main`, Streamlit redespliega automáticamente:

```bash
# Workflow normal de desarrollo
git add app_v2.py chatbot.py
git commit -m "feat: mejora en el chatbot"
git push origin main
# → Streamlit detecta el push y redespliega en ~1-2 min
```

Para forzar un redeploy sin cambios de código:
- Dashboard → tu app → botón **"⋮"** → **"Reboot app"**

---

## 7. Gestionar Secrets después del deploy

Para actualizar o agregar nuevas variables de entorno:
1. Dashboard → tu app → botón **"⋮"** → **"Settings"**
2. Pestaña **"Secrets"**
3. Editar el bloque TOML
4. Click **"Save"** → la app se reinicia

Ejemplo con múltiples secrets:
```toml
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
# Futuras integraciones:
# DIAN_EMAIL_USER = "contabilidad@empresa.com"
# DIAN_EMAIL_PASS = "app-password-aqui"
```

---

## 8. Límites del tier gratuito

| Recurso | Límite |
|---------|--------|
| Apps activas | 3 apps |
| RAM por app | 1 GB |
| CPU | Compartida |
| Almacenamiento | Temporal (se borra al reiniciar) |
| Uptime | La app hiberna si nadie la usa por ~7 días; despierta en ~30s al primer acceso |

> Para uso de un contador con sesiones regulares, estos límites son suficientes.
> Si necesitas la app siempre activa, considera Railway ($5/mes).

---

## 9. Dominio personalizado (opcional, futuro)

Streamlit Community Cloud soporta dominios personalizados en el plan Teams ($).
Para una alternativa gratuita con dominio propio, usar Railway o Render + Cloudflare:

```
tu-dominio.com → CNAME → facturas-dian.railway.app
```

Ver guía completa en `.claude/commands/devops.md`.

---

## 10. Solución de problemas comunes

| Problema | Causa probable | Solución |
|----------|---------------|---------|
| App no inicia (`ModuleNotFoundError`) | Falta dependencia en requirements.txt | Agregar el módulo y hacer push |
| `GROQ_API_KEY not set` en producción | Secret no configurado | Verificar sección Secrets en Settings |
| App hiberna y tarda en cargar | Normal en free tier | Primer request tarda ~30s en despertar |
| Deploy falla en `pip install` | Versión incompatible de paquete | Revisar logs de deploy en el dashboard |
| Archivos subidos se pierden al reiniciar | Streamlit no tiene almacenamiento persistente | Normal — los archivos son temporales por sesión |

---

## 11. Logs de la app

Para ver logs en tiempo real:
- Dashboard → tu app → botón **"⋮"** → **"View logs"**
- Útil para depurar errores de producción

Los logs de `logging` de Python aparecen aquí, igual que el stdout.
