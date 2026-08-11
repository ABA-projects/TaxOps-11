# Guía de Despliegue TaxOps — AWS + CI/CD + Docker

> ⚠️ **Histórico — ya no vigente.** GCP/Cloud Run se decomisionó el 2026-08-11, la migración a AWS Lambda quedó completa y verificada en producción. Se conserva como referencia/archivo, no como guía activa. Ver `docs/superpowers/plans/2026-08-05-taxops11-aws-migration.md` y `docs/MIGRACION-AWS-CASE-STUDY.md` para el estado real.


> **Objetivo:** Alojar TaxOps en producción por **$0–5 USD/mes** con dominio propio, HTTPS, PostgreSQL persistente y pipeline CI/CD automatizado.

---

## Comparativa de opciones

| Plataforma | Costo mensual | Dificultad | Recomendado para |
|---|---|---|---|
| **Railway** (actual) | $5–20 | Muy fácil | Pilotos rápidos |
| **AWS Lightsail** | $3.50 | Media | Producción estable |
| **EC2 + RDS free tier** | $0 (12 meses) → $20+ | Alta | Escalar después |
| **AWS Lightsail + PG local** | $3.50 total | Media | **Recomendado** |

---

## Tabla de costos detallada

| Servicio | Free Tier | Después del free tier | Notas |
|---|---|---|---|
| Lightsail $3.50 bundle | 3 meses gratis | **$3.50/mes** | 1GB RAM, 1vCPU, 40GB SSD |
| PostgreSQL en Lightsail | Incluido | Incluido | En el mismo servidor |
| RDS PostgreSQL t3.micro | 12 meses gratis | ~$15/mes | Opción alternativa |
| Route 53 hosted zone | — | $0.50/mes | Solo si usas Route 53 |
| Dominio `.com` | — | ~$12–15/año | Namecheap o GoDaddy es más barato |
| ACM SSL cert | **Gratis** | **Gratis** | Solo si usas ALB (no necesario) |
| Let's Encrypt via Caddy | **Gratis** | **Gratis** | Recomendado |
| EC2 t2.micro | 12 meses gratis | ~$8/mes | Alternativa a Lightsail |
| **Total recomendado** | | **~$4/mes** | Lightsail + dominio externo |

---

## Opción A — AWS Lightsail (recomendado)

Lightsail es la versión simplificada de AWS: precio fijo, menos configuración, ideal para apps pequeñas.

### 1. Crear instancia Lightsail

1. Ir a [aws.amazon.com/lightsail](https://aws.amazon.com/lightsail) → **Crear instancia**
2. Región: **us-east-1** o **sa-east-1** (São Paulo, más cerca de Colombia)
3. Sistema operativo: **Ubuntu 22.04 LTS**
4. Plan: **$3.50/mes** (1 GB RAM, 1 vCPU, 40 GB SSD) — suficiente para el piloto
5. Nombre de instancia: `taxops-prod`
6. Crear instancia → esperar ~2 minutos

### 2. Configurar IP estática

En el panel de Lightsail → **Redes** → **Crear IP estática** → asociar a `taxops-prod`.

Anotar la IP: por ejemplo `3.85.xxx.xxx`.

### 3. Abrir puertos

En Lightsail → instancia → **Redes** → agregar reglas de firewall:
- Puerto `22` (SSH) — ya abierto
- Puerto `80` (HTTP)
- Puerto `443` (HTTPS)
- Puerto `8501` — opcional, solo para debug

### 4. Conectarse por SSH

```bash
# Desde el panel de Lightsail, descargar la llave .pem
chmod 400 ~/Downloads/LightsailDefaultKey-us-east-1.pem
ssh -i ~/Downloads/LightsailDefaultKey-us-east-1.pem ubuntu@3.85.xxx.xxx
```

### 5. Instalar Docker y dependencias

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker

# Instalar Docker Compose
sudo apt install -y docker-compose-plugin

# Verificar
docker --version
docker compose version
```

### 6. Instalar PostgreSQL (en el mismo servidor)

```bash
sudo apt install -y postgresql postgresql-contrib

# Crear base de datos y usuario
sudo -u postgres psql <<'EOF'
CREATE USER taxops WITH PASSWORD 'tu_password_seguro_aqui';
CREATE DATABASE taxops OWNER taxops;
GRANT ALL PRIVILEGES ON DATABASE taxops TO taxops;
EOF

# Habilitar al inicio
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

La `DATABASE_URL` será:
```
DATABASE_URL=postgresql://taxops:tu_password_seguro_aqui@localhost:5432/taxops
```

### 7. Instalar Caddy (reverse proxy con HTTPS automático)

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Crear `/etc/caddy/Caddyfile`:
```
taxops.tudominio.com {
    reverse_proxy localhost:8501
}
```

```bash
sudo systemctl enable caddy
sudo systemctl restart caddy
```

Caddy obtiene automáticamente el certificado SSL de Let's Encrypt.

### 8. Clonar el repositorio y configurar

```bash
cd /home/ubuntu
git clone https://github.com/tu-usuario/proyecto-facturas.git taxops
cd taxops

# Crear archivo de variables de entorno
cat > .env <<'EOF'
DATABASE_URL=postgresql://taxops:tu_password_seguro_aqui@localhost:5432/taxops
GROQ_API_KEY=tu_groq_api_key
EOF

chmod 600 .env
```

### 9. Inicializar la base de datos

```bash
cd /home/ubuntu/taxops
pip install -r requirements.txt
DATABASE_URL=postgresql://taxops:tu_password_seguro_aqui@localhost:5432/taxops python manage.py init-db
```

### 10. Ejecutar la app con Docker

```bash
docker compose -f docker-compose.prod.yml up -d
```

Ver el archivo `docker-compose.prod.yml` en el **Apéndice B**.

### 11. Configurar inicio automático

```bash
sudo tee /etc/systemd/system/taxops.service <<'EOF'
[Unit]
Description=TaxOps Streamlit App
After=docker.service postgresql.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/taxops
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable taxops
sudo systemctl start taxops
```

---

## Opción B — EC2 free tier (12 meses gratis)

Igual que Lightsail pero usando EC2 t2.micro. Los pasos de instalación son idénticos. Diferencia: en EC2 necesitas configurar manualmente los Security Groups para abrir puertos 80 y 443.

**Cuándo usar EC2:** Si quieres aprovechar los 12 meses gratis de AWS antes de pagar.

**Después del free tier:** EC2 t2.micro ~$8/mes + RDS t3.micro ~$15/mes = **$23/mes**. Migrar a Lightsail a tiempo.

---

## Dominio y DNS

### Opción 1 — Dominio externo (Namecheap, más barato)

1. Comprar dominio en [namecheap.com](https://namecheap.com) (~$8–12/año para `.com`)
2. En Namecheap → **Advanced DNS** → agregar registro:
   - Tipo: `A`
   - Host: `@` (o `taxops` para subdominio)
   - Value: `3.85.xxx.xxx` (tu IP estática de Lightsail)
   - TTL: Automático
3. Esperar propagación: 5–30 minutos
4. Actualizar el `Caddyfile` con el dominio correcto y reiniciar Caddy

### Opción 2 — Route 53 (dentro de AWS)

1. AWS Console → Route 53 → **Hosted zones** → **Create hosted zone**
2. Domain name: `tudominio.com`
3. Copiar los 4 Name Servers de Route 53
4. En el registrador donde compraste el dominio, actualizar los NS
5. En Route 53 → **Create record**:
   - Record name: (vacío para raíz)
   - Record type: A
   - Value: IP de Lightsail
6. Costo: $0.50/mes por hosted zone + precio del dominio

---

## CI/CD con GitHub Actions + Docker

### Flujo completo

```
git push → GitHub Actions:
  1. Build Docker image
  2. Push a GitHub Container Registry (gratis)
  3. SSH al servidor → docker compose pull + up -d
```

### Dockerfile

Ver **Apéndice A**.

### Workflow de GitHub Actions

Crear `.github/workflows/deploy.yml`:

```yaml
name: Deploy TaxOps

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=,suffix=,format=short
            type=raw,value=latest

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy to server
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ubuntu
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /home/ubuntu/taxops
            git pull origin main
            echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
            docker compose -f docker-compose.prod.yml pull
            docker compose -f docker-compose.prod.yml up -d --no-deps --remove-orphans
            docker image prune -f
            echo "✅ Deploy completado: $(date)"
```

### Secrets de GitHub Actions

En el repositorio → **Settings** → **Secrets and variables** → **Actions** → agregar:

| Secret | Valor |
|---|---|
| `SERVER_HOST` | IP de Lightsail (ej: `3.85.xxx.xxx`) |
| `SERVER_SSH_KEY` | Contenido del archivo `.pem` de Lightsail |

El `GITHUB_TOKEN` lo provee GitHub automáticamente.

### Variables de entorno en el servidor

El `.env` en el servidor **nunca** va al repositorio. Las variables sensibles van en `/home/ubuntu/taxops/.env`:

```bash
DATABASE_URL=postgresql://taxops:password@localhost:5432/taxops
GROQ_API_KEY=gsk_xxx
```

El `docker-compose.prod.yml` carga este archivo con `env_file: .env`.

---

## Apéndice A — Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema para psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Streamlit config
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["python3", "-m", "streamlit", "run", "Home.py"]
```

---

## Apéndice B — docker-compose.prod.yml

```yaml
version: "3.9"

services:
  app:
    image: ghcr.io/tu-usuario/proyecto-facturas:latest
    restart: unless-stopped
    ports:
      - "8501:8501"
    env_file:
      - .env
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
    depends_on:
      - healthcheck
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  healthcheck:
    image: alpine
    command: echo "ok"
```

> **Nota:** PostgreSQL corre directamente en el host (paso 6 de la guía). No se incluye como servicio Docker para evitar problemas de volúmenes y permisos en Lightsail. Si prefieres PostgreSQL en Docker, agregar el servicio `db` del `docker-compose.yml` original.

---

## Resumen de comandos operacionales

```bash
# Ver estado de la app
docker compose -f docker-compose.prod.yml ps

# Ver logs en tiempo real
docker compose -f docker-compose.prod.yml logs -f app

# Reiniciar app
docker compose -f docker-compose.prod.yml restart app

# Actualizar manualmente (sin esperar el CI/CD)
git pull && docker compose -f docker-compose.prod.yml up -d --build

# Crear primera organización en producción
DATABASE_URL=postgresql://taxops:password@localhost:5432/taxops \
  python manage.py create-org \
  --name "Firma Contable Piloto" \
  --email admin@firma.com \
  --password "contraseña_segura_2026"

# Backup de la base de datos
pg_dump -U taxops taxops > backup_$(date +%Y%m%d).sql
```

---

## Checklist de go-live

- [ ] Lightsail creada y accesible por SSH
- [ ] Docker instalado y funcionando
- [ ] PostgreSQL corriendo y schema inicializado con `manage.py init-db`
- [ ] `.env` creado con `DATABASE_URL` y `GROQ_API_KEY`
- [ ] Dominio apuntando a la IP estática (registro A en DNS)
- [ ] Caddy corriendo y sirviendo HTTPS
- [ ] App accesible en `https://tudominio.com`
- [ ] Primera organización creada con `manage.py create-org`
- [ ] Login del cliente piloto validado
- [ ] GitHub Actions configurado y primer deploy automático exitoso
- [ ] Backup de DB programado (cron job)
