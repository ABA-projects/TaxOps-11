# TaxOps — Monitoreo Google Cloud Platform

> Referencia de monitoreo para el entorno Cloud Run desplegado en mayo 2026.

**Proyecto GCP:** `taxops-497921`  
**Región:** `us-central1`  
**Servicio Cloud Run:** `taxops-api`  
**Registry:** `us-central1-docker.pkg.dev/taxops-497921/taxops`

---

## Índice

1. [Acceso rápido a consola GCP](#acceso-rápido-a-consola-gcp)
2. [Cloud Run — servicio taxops-api](#cloud-run--servicio-taxops-api)
3. [Logs en tiempo real](#logs-en-tiempo-real)
4. [Métricas y alertas](#métricas-y-alertas)
5. [Artifact Registry — imágenes Docker](#artifact-registry--imágenes-docker)
6. [Service Account y seguridad](#service-account-y-seguridad)
7. [Facturación y límites free tier](#facturación-y-límites-free-tier)
8. [Comandos gcloud de referencia](#comandos-gcloud-de-referencia)
9. [Runbook — incidentes comunes](#runbook--incidentes-comunes)

---

## Acceso rápido a consola GCP

| Recurso | URL consola |
|---------|-------------|
| Cloud Run — servicio | https://console.cloud.google.com/run/detail/us-central1/taxops-api/metrics?project=taxops-497921 |
| Cloud Run — logs | https://console.cloud.google.com/run/detail/us-central1/taxops-api/logs?project=taxops-497921 |
| Artifact Registry | https://console.cloud.google.com/artifacts/docker/taxops-497921/us-central1/taxops?project=taxops-497921 |
| Cloud Logging | https://console.cloud.google.com/logs/query?project=taxops-497921 |
| Facturación | https://console.cloud.google.com/billing?project=taxops-497921 |
| IAM | https://console.cloud.google.com/iam-admin/iam?project=taxops-497921 |

---

## Cloud Run — servicio taxops-api

### Configuración actual

| Parámetro | Valor |
|-----------|-------|
| Nombre | `taxops-api` |
| Región | `us-central1` |
| Memoria | 1 GiB |
| CPU | 1 vCPU |
| Timeout | 600 s |
| Máx. instancias | 1 |
| Mín. instancias | 0 (scale-to-zero) |
| Concurrencia | 80 requests/instancia (default) |
| Autenticación | Unauthenticated (JWT valida FastAPI) |
| URL | https://taxops-api-fh5jvzgf7q-uc.a.run.app |

### Variables de entorno en el servicio

Las env vars se inyectan en el deploy vía `--set-env-vars`. Para ver los valores actuales (sin secretos):

```bash
gcloud run services describe taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --format="yaml(spec.template.spec.containers[0].env)"
```

Para actualizar una variable de entorno sin rebuild:

```bash
gcloud run services update taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --update-env-vars="VARIABLE=nuevo_valor"
```

---

## Logs en tiempo real

### Desde terminal (gcloud)

```bash
# Últimos 50 logs
gcloud run services logs read taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --limit 50

# Stream en vivo (equivalente a tail -f)
gcloud run services logs tail taxops-api \
  --region us-central1 \
  --project taxops-497921
```

### Filtros útiles en Cloud Logging

Acceder a Cloud Logging desde: https://console.cloud.google.com/logs/query?project=taxops-497921

**Errores 500 de la API:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="taxops-api"
severity>=ERROR
```

**Requests lentos (>5 segundos):**
```
resource.type="cloud_run_revision"
resource.labels.service_name="taxops-api"
httpRequest.latency>"5s"
```

**Logs de un deploy específico:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="taxops-api"
resource.labels.revision_name="taxops-api-XXXXX"
```

**Errores de autenticación:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="taxops-api"
textPayload=~"401|403|Unauthorized|credentials"
```

**Jobs de exógenas (OCR):**
```
resource.type="cloud_run_revision"
resource.labels.service_name="taxops-api"
textPayload=~"exogenas|OCR|procesar"
```

---

## Métricas y alertas

### Métricas disponibles en consola

En la pestaña **Metrics** del servicio Cloud Run:

| Métrica | Qué observar |
|---------|-------------|
| **Request count** | Volumen de tráfico, picos inusuales |
| **Request latencies** | P50/P95/P99 — alertar si P99 > 30s |
| **Container instance count** | Cuántas instancias activas (máx. 1 configurado) |
| **CPU utilization** | Si supera 80% consistentemente, aumentar CPU |
| **Memory utilization** | Crítico — si supera 90% se produce OOM y reinicio |
| **Container startup latency** | Cold start — normal 5-15s en free tier |

### Crear alerta de memoria (recomendado)

Desde Cloud Monitoring → Alerting → Create Policy:

1. **Metric:** `Cloud Run Revision > Memory utilization`
2. **Filter:** `service_name = taxops-api`
3. **Threshold:** `> 85%` por más de 2 minutos
4. **Notification:** email a `arqueanja@gmail.com`

### Health check manual

```bash
curl -s https://taxops-api-fh5jvzgf7q-uc.a.run.app/health | python3 -m json.tool
```

La API responde `{"status": "ok"}` en el endpoint `/health`.

---

## Artifact Registry — imágenes Docker

### Ver imágenes almacenadas

```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/taxops-497921/taxops \
  --include-tags \
  --project taxops-497921
```

### Ver imágenes por fecha (más recientes primero)

```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/taxops-497921/taxops/api \
  --sort-by="~UPDATE_TIME" \
  --limit 10 \
  --project taxops-497921
```

### Limpiar imágenes antiguas (mantener las últimas 5)

```bash
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/taxops-497921/taxops/api \
  --project taxops-497921

# Eliminar una imagen específica por su digest
gcloud artifacts docker images delete \
  "us-central1-docker.pkg.dev/taxops-497921/taxops/api@sha256:DIGEST" \
  --project taxops-497921
```

### Política de limpieza automática (recomendado)

Para evitar acumulación de imágenes:

```bash
gcloud artifacts repositories update taxops \
  --location us-central1 \
  --project taxops-497921 \
  --cleanup-policy-file cleanup-policy.json
```

Contenido de `cleanup-policy.json`:
```json
[
  {
    "name": "keep-last-5",
    "action": {"type": "Keep"},
    "mostRecentVersions": {"keepCount": 5}
  },
  {
    "name": "delete-old",
    "action": {"type": "Delete"},
    "condition": {"olderThan": "30d"}
  }
]
```

---

## Service Account y seguridad

### Service Account del deployer

| Campo | Valor |
|-------|-------|
| Nombre | `taxops-deployer` |
| Email | `taxops-deployer@taxops-497921.iam.gserviceaccount.com` |
| Roles | Cloud Run Admin · Artifact Registry Writer · Service Account User |
| Clave | JSON key almacenada en GitHub Secret `GCP_SA_KEY` |

### Verificar roles asignados

```bash
gcloud projects get-iam-policy taxops-497921 \
  --flatten="bindings[].members" \
  --filter="bindings.members:taxops-deployer" \
  --format="table(bindings.role)"
```

Resultado esperado:
```
ROLE
roles/artifactregistry.writer
roles/iam.serviceAccountUser
roles/run.admin
```

### Rotar la clave JSON (recomendado cada 90 días)

1. Crear nueva clave:
```bash
gcloud iam service-accounts keys create nueva-key.json \
  --iam-account=taxops-deployer@taxops-497921.iam.gserviceaccount.com
```

2. Actualizar el GitHub Secret `GCP_SA_KEY` con el contenido de `nueva-key.json`

3. Eliminar la clave anterior:
```bash
# Listar todas las claves y sus IDs
gcloud iam service-accounts keys list \
  --iam-account=taxops-deployer@taxops-497921.iam.gserviceaccount.com

# Eliminar la clave vieja por KEY_ID
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=taxops-deployer@taxops-497921.iam.gserviceaccount.com
```

4. Eliminar el archivo `nueva-key.json` del disco local.

---

## Facturación y límites free tier

### Google Cloud Run — Free Tier mensual

| Recurso | Free tier | Costo excedente |
|---------|-----------|-----------------|
| Requests | 2 millones/mes | $0.40 / millón |
| CPU | 180,000 vCPU-segundos/mes | $0.00002400 / vCPU-s |
| Memoria | 360,000 GB-segundos/mes | $0.00000250 / GB-s |
| Red egress | 1 GB/mes (América del Norte) | $0.12 / GB |

### Artifact Registry — Free Tier

| Recurso | Free tier |
|---------|-----------|
| Almacenamiento | 0.5 GB/mes |
| Network egress | Variable (dentro de misma región: gratis) |

### Estimación de uso TaxOps (carga normal)

Con `--max-instances 1` y `scale-to-zero`:
- La instancia se apaga cuando no hay tráfico → 0 CPU/memoria consumida
- Cold start al recibir primer request: ~8-12 segundos
- Para una app de uso laboral (9am-6pm, ~50 usuarios/día): estimado < $1/mes

### Configurar alerta de presupuesto

```
Consola GCP → Billing → Budgets & Alerts → Create Budget
  - Amount: $5/month
  - Alert thresholds: 50%, 90%, 100%
  - Notifications: email
```

---

## Comandos gcloud de referencia

### Estado del servicio

```bash
# Descripción completa del servicio
gcloud run services describe taxops-api \
  --region us-central1 \
  --project taxops-497921

# URL del servicio
gcloud run services describe taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --format="value(status.url)"

# Revisiones desplegadas
gcloud run revisions list \
  --service taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --sort-by="~DEPLOYED" \
  --limit 5
```

### Gestión de tráfico

```bash
# Ver distribución de tráfico entre revisiones
gcloud run services describe taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --format="yaml(spec.traffic)"

# Rollback a revisión anterior
gcloud run services update-traffic taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --to-revisions=REVISION_NAME=100
```

### Redeploy manual (sin cambios de código)

```bash
# Forzar redeploy de la última imagen
gcloud run deploy taxops-api \
  --image "us-central1-docker.pkg.dev/taxops-497921/taxops/api:SHA_AQUI" \
  --region us-central1 \
  --project taxops-497921
```

### Eliminar revisiones antiguas

```bash
# Listar revisiones inactivas
gcloud run revisions list \
  --service taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --filter="status.conditions.type:Active AND NOT status.conditions.status:True"

# Eliminar revisión específica
gcloud run revisions delete REVISION_NAME \
  --region us-central1 \
  --project taxops-497921
```

---

## Runbook — incidentes comunes

### La API no responde (timeout)

**Diagnóstico:**
```bash
curl -v https://taxops-api-fh5jvzgf7q-uc.a.run.app/health
gcloud run services logs tail taxops-api --region us-central1 --project taxops-497921
```

**Causas frecuentes:**
1. Cold start lento (>15s) — normal en free tier, primera request tarda más
2. OOM durante procesamiento OCR — revisar logs por `Memory limit exceeded`
3. Timeout de DB — revisar conexión a Neon desde Cloud Run (verificar `DATABASE_URL`)

**Acción si OOM:**
```bash
gcloud run services update taxops-api \
  --memory 2Gi \
  --region us-central1 \
  --project taxops-497921
```

---

### Deploy falla en GitHub Actions

**Verificar logs en:** https://github.com/jaimehenao8126/TaxOps-11/actions

**Error: `PERMISSION_DENIED`**
- Verificar que los 3 roles están asignados a `taxops-deployer`
- Verificar que `GCP_SA_KEY` en GitHub Secrets contiene el JSON completo y válido

**Error: `Image not found`**
- El push a Artifact Registry falló antes del deploy
- Revisar el paso "Build and push Docker image" en el log del workflow

**Error: `Bad syntax for dict arg`**
- Problema en `--set-env-vars` con delimitadores
- La solución `^|^` ya está aplicada en el workflow actual

---

### Ver qué imagen está en producción

```bash
gcloud run services describe taxops-api \
  --region us-central1 \
  --project taxops-497921 \
  --format="value(spec.template.spec.containers[0].image)"
```

El SHA al final de la URL de la imagen corresponde al commit de GitHub que está desplegado actualmente.

---

### Comparar versión desplegada vs código en main

```bash
# SHA del commit desplegado (extraer del nombre de la imagen)
IMAGE=$(gcloud run services describe taxops-api \
  --region us-central1 --project taxops-497921 \
  --format="value(spec.template.spec.containers[0].image)")

DEPLOYED_SHA=$(echo $IMAGE | grep -oP '(?<=api:)[a-f0-9]+')
MAIN_SHA=$(git rev-parse HEAD)

echo "Desplegado: $DEPLOYED_SHA"
echo "Main:       $MAIN_SHA"

if [ "$DEPLOYED_SHA" = "$MAIN_SHA" ]; then
  echo "OK: producción está actualizada"
else
  echo "DESFASADO: hay commits en main sin desplegar"
fi
```

---

*Documento creado: mayo 2026 — Proyecto taxops-497921 (us-central1)*
