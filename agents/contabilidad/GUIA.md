# Agentes IA — Oficina Contable Colombia

Suite de 4 agentes para automatizar el monitoreo tributario, normativo y prospección
comercial de una firma contable colombiana.

---

## Estructura

```
contabilidad/
├── GUIA.md                          ← este archivo
├── dian-monitor/                    ← novedades DIAN semanales
├── vencimientos-tributarios/        ← alertas de vencimientos próximos 30 días
├── monitor-niif/                    ← actualizaciones NIIF/CTCP
└── prospector-clientes-contables/   ← leads de empresas para nuevos clientes
```

---

## Requisitos

- Python 3.10+
- Cuenta gratuita en [console.groq.com](https://console.groq.com) → obtener `GROQ_API_KEY`
- Conexión a internet (DuckDuckGo Search, sin API key adicional)
- Costo de inferencia: **$0** (Groq free tier)

---

## Setup inicial (una sola vez por agente)

Cada agente tiene su propio entorno virtual. Entrar a la carpeta del agente y ejecutar:

```bash
cd <nombre-agente>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml      # ajustar con datos del cliente
echo "GROQ_API_KEY=gsk_..." > .env      # pegar la API key de Groq
```

---

## Configuración por cliente

Cada agente tiene un `config.yaml`. Los campos a personalizar son:

| Agente | Campos clave a cambiar |
|--------|------------------------|
| `dian-monitor` | `client_name`, `keywords` |
| `vencimientos-tributarios` | `client_name`, `tipo_contribuyente`, `obligaciones` |
| `monitor-niif` | `client_name`, `grupo_niif`, `normas_a_monitorear` |
| `prospector-clientes-contables` | `agencia_nombre`, `ciudades`, `sectores_objetivo` |

---

## Uso individual

```bash
# Desde la carpeta del agente (con .venv activado):
source .venv/bin/activate
python agent.py
# → reporte en output/<nombre>-<fecha>.md
```

### Ejemplos por agente

```bash
# Novedades DIAN de la semana
cd dian-monitor && python agent.py

# Vencimientos tributarios próximos 30 días
cd vencimientos-tributarios && python agent.py

# Actualizaciones NIIF/CTCP
cd monitor-niif && python agent.py

# Leads de prospectos para nuevos clientes
cd prospector-clientes-contables && python agent.py
```

---

## Automatización semanal (opcional)

Para correr un agente automáticamente cada lunes a las 7am:

```bash
crontab -e
# Agregar (ajustar ruta y agente):
0 7 * * 1 cd /ruta/a/contabilidad/dian-monitor && .venv/bin/python agent.py
```

---

## Output de ejemplo

Cada agente genera un archivo Markdown en su carpeta `output/`:

| Agente | Archivo generado |
|--------|------------------|
| `dian-monitor` | `output/reporte-dian-<fecha>.md` |
| `vencimientos-tributarios` | `output/vencimientos-<fecha>.md` |
| `monitor-niif` | `output/monitor-niif-<fecha>.md` |
| `prospector-clientes-contables` | `output/leads-contables-<fecha>.md` |

---

## Personalización avanzada

- Para agregar más fuentes de búsqueda, editar el `system_prompt` en `agent.py` de cada agente.
- Para cambiar el modelo LLM, reemplazar `"openai/gpt-oss-120b"` por cualquier modelo disponible
  en [console.groq.com/docs/models](https://console.groq.com/docs/models).
- Para usar Claude en vez de Groq (mejor calidad, costo por token): ver el bloque comentado
  al final de `freelance-job-finder/agent.py` como referencia de migración.
