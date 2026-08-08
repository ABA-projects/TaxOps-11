# TaxOps-11 AWS Migration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar el compute, la cola de jobs, el storage de archivos y el frontend de TaxOps-11 de GCP (Cloud Run) + Vercel a AWS, 100% con Terraform, optimizando para $0-2/mes durante el Año 1 (capa gratuita) con una ruta clara de escalamiento en el Año 2 sin necesidad de rediseño.

**Architecture:** Serverless-first. API y worker de background jobs en Lambda (imagen de contenedor, reusa `api/Dockerfile-api`), cola SQS + estado de jobs en DynamoDB (reemplaza el `ThreadPoolExecutor` en memoria), archivos en S3 (reemplaza GCS), frontend Next.js en Amplify Hosting (reemplaza Vercel), CloudFront + Route53 + ACM para TLS/dominio propio, secretos en SSM Parameter Store. **La base de datos se queda en Neon** (no se migra a RDS) — ver Chunk 0 para el porqué.

**Tech Stack:** Terraform ≥1.9 · AWS provider ~> 5.0 · Lambda (container image) · SQS · DynamoDB · S3 · CloudFront · Route53 · ACM · Amplify Hosting · SSM Parameter Store · ECR · GitHub Actions

**Discovery:** `docs/MIGRACION-AWS-DISCOVERY.md`

---

## Observaciones antes de implementar

- **No crear una VPC.** Lambda fuera de VPC (default) puede llamar a Neon, Groq y Google OAuth por internet sin costo extra. Meter Lambda en VPC para "hablar con una RDS" obliga a un NAT Gateway (~$32/mes) que se come todo el ahorro de la capa gratuita — por eso la DB se queda en Neon en la Fase 1.
- El estado de Terraform va en **S3 + DynamoDB lock**, se bootstrapea una sola vez (Chunk 0) fuera del flujo normal de `terraform apply`.
- El código de la API **casi no cambia** salvo dos puntos: (a) `services/renta/storage.py` (GCS → S3), (b) `api/routers/exogenas.py` y `services/renta/job_processor.py` (dict en memoria → DynamoDB). Todo lo demás (FastAPI, rutas, auth) se mantiene igual porque Lambda con Mangum expone la misma app ASGI sin reescribirla.
- Región recomendada: **`us-east-1`** (más barata para Lambda/S3/CloudFront edge, y es donde vive la mayoría de la capa gratuita "forever" de AWS).
- Todas las tareas de Terraform siguen el mismo patrón: escribir el `.tf`, `terraform fmt`, `terraform validate`, `terraform plan` (revisar el output antes de aplicar), `terraform apply`, commit. No se repite el detalle de `fmt`/`validate` en cada task para no inflar el documento — es un paso implícito en todo "Apply" de este plan.
- Convención de nombres de recursos: `taxops-<componente>-<env>` (ej. `taxops-api-prod`, `taxops-jobs-prod`).

---

## Chunk 0: Bootstrap de Terraform (una sola vez, manual)

### Task 0.1: Backend remoto de estado

**Files:**
- Create: `infra/bootstrap/main.tf`
- Create: `infra/bootstrap/versions.tf`

- [ ] **Paso 1: Crear el bucket S3 de state + tabla de lock**

```hcl
# infra/bootstrap/main.tf
resource "aws_s3_bucket" "tfstate" {
  bucket = "taxops11-tfstate-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

data "aws_caller_identity" "current" {}
```

**Nota (actualizado tras aplicar):** no hay tabla DynamoDB de lock — Terraform 1.10+ soporta locking nativo en el backend S3 (`use_lockfile = true`), así que se eliminó ese recurso por completo. Menos superficie a mantener, mismo resultado ($0 de cualquier forma).

- [ ] **Paso 2: Apply manual (única vez, sin backend remoto todavía)**

```bash
cd infra/bootstrap && terraform init && terraform apply
```

- [ ] **Paso 3: Anotar el nombre del bucket en `infra/environments/prod/backend.tf`** (Chunk 1, Task 1.1) y confirmar que el state de bootstrap se queda local (es intencional — es el único módulo sin backend remoto, por el problema del huevo y la gallina).

- [ ] **Commit**

```bash
git add infra/bootstrap && git commit -m "infra: bootstrap terraform state backend (S3, locking nativo)"
```

---

## Chunk 1: Entorno raíz, ECR y secretos

### Task 1.1: Root module + backend remoto

**Files:**
- Create: `infra/environments/prod/backend.tf`
- Create: `infra/environments/prod/providers.tf`
- Create: `infra/environments/prod/variables.tf`

```hcl
# infra/environments/prod/backend.tf
terraform {
  backend "s3" {
    bucket       = "taxops11-tfstate-<ACCOUNT_ID>" # del Chunk 0
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true # locking nativo de S3 (Terraform 1.10+), sin tabla DynamoDB
    encrypt      = true
  }
}
```

```hcl
# infra/environments/prod/providers.tf
terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "taxops11"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}
```

- [ ] Apply, commit.

### Task 1.2: ECR para la imagen de Lambda

**Files:**
- Create: `infra/modules/ecr/main.tf`

```hcl
resource "aws_ecr_repository" "api" {
  name                 = "taxops-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Mantener solo las últimas 10 imágenes (capa gratuita ECR = 500MB)"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}
```

- [ ] Apply, commit.

### Task 1.3: Secretos en SSM Parameter Store (no Secrets Manager)

**Por qué:** Secrets Manager cobra $0.40/secreto/mes — con ~10 secretos son $4/mes solo por guardarlos. SSM Parameter Store `SecureString` estándar es gratis.

**Files:**
- Create: `infra/modules/secrets/main.tf`
- Create: `infra/modules/secrets/variables.tf`

```hcl
# infra/modules/secrets/variables.tf
variable "secrets" {
  type      = map(string) # nombre -> valor (pasado por -var-file, NUNCA hardcodeado)
  sensitive = true
  default   = {}
}
```

```hcl
# infra/modules/secrets/main.tf
# Terraform no permite un mapa "sensitive" directo como for_each (expondría las keys en el
# plan/state). Las keys (nombres como "DATABASE_URL") no son secretas, solo los values.
locals {
  secret_names = nonsensitive(toset(keys(var.secrets)))
}

resource "aws_ssm_parameter" "this" {
  for_each = local.secret_names
  name     = "/taxops11/prod/${each.value}"
  type     = "SecureString"
  value    = var.secrets[each.value] # este sí se mantiene sensible
  tier     = "Standard"
}
```

- [ ] En `infra/environments/prod/terraform.tfvars.secret` (gitignored) listar: `DATABASE_URL, SECRET_KEY, GROQ_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, TAXOPS_SUPERADMIN_EMAILS, BOOTSTRAP_SECRET`.
- [ ] Apply, commit (el `.tfvars.secret` NO se commitea — agregarlo a `.gitignore`).

### Task 1.4: OIDC provider + rol IAM para GitHub Actions (base del CI/CD de Terraform)

**Por qué ahora:** los workflows de Chunk 1.4b (`.github/workflows/terraform-*.yml`) necesitan un rol que asumir vía OIDC — sin llaves de larga duración, igual que el resto del plan. Se crea una sola vez, manual con tu profile `taxops-admin` (es el único bootstrap de confianza, como el Chunk 0), y de ahí en adelante todo el plan de Terraform corre desde GitHub Actions, no desde tu laptop.

**Files:**
- Create: `infra/modules/github-oidc/main.tf`

```hcl
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"] # thumbprint público de GitHub, no rota seguido
}

resource "aws_iam_role" "github_actions_terraform" {
  name = "taxops-github-actions-terraform"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        # Restringe a este repo y rama — evita que CUALQUIER repo de tu GitHub pueda asumir el rol
        StringLike = { "token.actions.githubusercontent.com:sub" = "repo:ABA-projects/TaxOps-11:*" }
      }
    }]
  })
}

# MVP: AdministratorAccess, igual que jaime.admin — se acota en Fase 2 (ver plan, sección de backlog)
resource "aws_iam_role_policy_attachment" "github_actions_admin" {
  role       = aws_iam_role.github_actions_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
```

- [ ] Apply (con `AWS_PROFILE=taxops-admin`, manual, única vez).
- [ ] Copiar el ARN del rol (`aws_iam_role.github_actions_terraform.arn` en el output) a **GitHub → Settings → Secrets and variables → Actions → Variables** (no Secrets, el ARN no es sensible) → nombre `AWS_TERRAFORM_ROLE_ARN`.
- [ ] Commit.

**Nota de seguridad (deuda técnica documentada, no bloqueante):** este rol usa `AdministratorAccess`, igual que el admin humano — es un atajo válido para arrancar solo, pero antes de invitar a alguien más al repo o de que este pipeline aplique cambios sin que tú revises cada plan, hay que acotarlo a una policy con los servicios exactos del plan (Lambda, SQS, DynamoDB, S3, CloudFront, Route53, ECR, SSM, IAM *solo* para los roles que el propio Terraform gestiona). Se agrega también al backlog de guardrails de `docs/AWS-ACCOUNT-SETUP-GUIDE.md` sección 6.1.

### Task 1.4b: Workflows de GitHub Actions — plan en PR, apply en merge

**Files:**
- Create: `.github/workflows/terraform-plan.yml`
- Create: `.github/workflows/terraform-apply.yml`

```yaml
# .github/workflows/terraform-plan.yml
name: Terraform Plan
on:
  pull_request:
    paths: ["infra/**"]

permissions:
  id-token: write   # requerido para OIDC, no se puede omitir
  contents: read

concurrency:
  group: terraform-prod
  cancel-in-progress: false # nunca cancelar un plan/apply a medias

jobs:
  plan:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: infra/environments/prod
    steps:
      - uses: actions/checkout@v7
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_TERRAFORM_ROLE_ARN }}
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v4
        with:
          terraform_version: "~> 1.15"
      - run: terraform fmt -check -recursive
      - run: terraform init
      - run: terraform validate
      - run: terraform plan -no-color | tee /tmp/plan.txt
      - name: Publicar el plan en el resumen del job
        run: |
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          cat /tmp/plan.txt >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
```

```yaml
# .github/workflows/terraform-apply.yml
name: Terraform Apply
on:
  push:
    branches: [main]
    paths: ["infra/**"]

permissions:
  id-token: write
  contents: read

concurrency:
  group: terraform-prod
  cancel-in-progress: false

jobs:
  apply:
    runs-on: ubuntu-latest
    environment: production # gate de aprobación manual, ver nota abajo
    defaults:
      run:
        working-directory: infra/environments/prod
    steps:
      - uses: actions/checkout@v7
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_TERRAFORM_ROLE_ARN }}
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v4
        with:
          terraform_version: "~> 1.15"
      - run: terraform init
      - run: terraform apply -auto-approve
```

**Nota (traído de Fase 2 antes de tiempo, decisión 2026-08-07):** el backlog original de `docs/CI-CD-GITOPS-GUIDE.md` marcaba "aprobación manual antes de apply" como mejora de Fase 2. Se adelantó porque el costo de configurarlo es $0 y el beneficio (nunca un apply 100% automático sin que un humano lo confirme) es inmediato — no había razón real para esperar un trigger de negocio. Configuración: GitHub → Settings → Environments → `production`, required reviewers = tu usuario, + **"Allow administrators to bypass configured protection rules"** activado (así el propio admin puede aprobar su propio deploy, ya que GitHub por defecto no deja que el mismo actor que disparó el run se auto-apruebe).

- [ ] Push ambos archivos. El `terraform-plan.yml` corre en cada PR que toque `infra/**` (revisas el plan en el Job Summary antes de aprobar el merge); `terraform-apply.yml` corre solo al mergear a `main`.
- [ ] **Regla de oro de aquí en adelante**: nunca más `terraform apply` manual desde tu laptop salvo emergencia — todo cambio de infra pasa por PR. Tu `AWS_PROFILE=taxops-admin` local queda para `plan`/lectura/debug, no para aplicar.
- [ ] Commit: `git commit -m "ci: agregar pipeline de Terraform (plan en PR, apply en merge a main)"`.

---

## Chunk 2: Cola y estado de jobs (arregla el bug de estado en memoria)

### Task 2.1: DynamoDB para estado de jobs

**Files:**
- Create: `infra/modules/jobs/dynamodb.tf`

```hcl
resource "aws_dynamodb_table" "jobs" {
  name         = "taxops-jobs-prod"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}
```

- [ ] Apply, commit.

### Task 2.2: SQS para disparar el worker

**Files:**
- Create: `infra/modules/jobs/sqs.tf`

```hcl
resource "aws_sqs_queue" "jobs_dlq" {
  name = "taxops-jobs-dlq-prod"
}

resource "aws_sqs_queue" "jobs" {
  name                       = "taxops-jobs-prod"
  visibility_timeout_seconds = 900 # >= timeout del Lambda worker (15 min)
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount      = 3
  })
}
```

- [ ] Apply, commit.

### Task 2.3: Cambio de código — dict en memoria → DynamoDB

**Files:**
- Modify: `api/routers/exogenas.py` (reemplazar `_pending`/`_jobs` dict por `boto3.resource("dynamodb").Table("taxops-jobs-prod")`)
- Modify: `services/renta/job_processor.py` (reemplazar `in_memory_jobs` dict de la misma forma)
- Modify: `api/requirements-api.txt` (agregar `boto3`)

- [ ] Escribir un helper único `api/core/job_store.py` con `put_job(job_id, status, data)` / `get_job(job_id)` sobre DynamoDB, y usarlo desde ambos routers — evita duplicar el cliente boto3 en dos archivos.
- [ ] Reemplazar en `exogenas.py` y `job_processor.py` las escrituras/lecturas del dict por llamadas al helper.
- [ ] Test manual: correr un job de exógenas localmente contra una tabla DynamoDB real (o `moto` en tests) y confirmar que `GET /exogenas/status/{job_id}` lee el estado correctamente tras "reiniciar" el proceso (mata y levanta el proceso local — antes esto perdía el job, ahora no).
- [ ] Commit: `git commit -m "feat: mover estado de jobs de memoria a DynamoDB"`.

---

## Chunk 3: Storage — S3 reemplaza GCS

### Task 3.1: Buckets S3

**Files:**
- Create: `infra/modules/storage/main.tf`

```hcl
resource "aws_s3_bucket" "renta_docs" {
  bucket = "taxops-renta-docs-prod"
}

resource "aws_s3_bucket" "job_artifacts" {
  bucket = "taxops-job-artifacts-prod"
}

resource "aws_s3_bucket_lifecycle_configuration" "job_artifacts" {
  bucket = aws_s3_bucket.job_artifacts.id
  rule {
    id     = "expire-old-exports"
    status = "Enabled"
    expiration { days = 30 } # los excel de exógenas no necesitan vivir para siempre
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = { renta = aws_s3_bucket.renta_docs.id, jobs = aws_s3_bucket.job_artifacts.id }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

- [ ] Apply, commit.

### Task 3.2: Cambio de código — GCS → S3 en `services/renta/storage.py`

**Files:**
- Modify: `services/renta/storage.py` (swap `google-cloud-storage` client por `boto3` S3 client, misma interfaz pública: `upload()`, `signed_url()`)
- Modify: `api/requirements-api.txt` (quitar `google-cloud-storage`, ya está `boto3` del Chunk 2)

- [ ] Mantener la misma firma de funciones que hoy usa `services/renta/job_processor.py` para no tocar el caller — solo cambia la implementación interna.
- [ ] Usar `generate_presigned_url` de boto3 en vez de `generate_signed_url` de GCS (equivalente directo).
- [ ] Commit: `git commit -m "feat: migrar storage de Renta de GCS a S3"`.

---

## Chunk 4: Lambda — API y worker

### Task 4.1: IAM role compartido

**Files:**
- Create: `infra/modules/lambda-api/iam.tf`

```hcl
resource "aws_iam_role" "lambda_exec" {
  name = "taxops-lambda-exec-prod"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Política mínima: SQS (enviar/recibir), DynamoDB (jobs table), S3 (los 2 buckets), SSM (leer /taxops11/prod/*)
resource "aws_iam_role_policy" "app_access" {
  name = "taxops-app-access"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = var.sqs_queue_arn },
      { Effect = "Allow", Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"], Resource = var.dynamodb_table_arn },
      { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject"], Resource = ["${var.s3_bucket_arns[0]}/*", "${var.s3_bucket_arns[1]}/*"] },
      { Effect = "Allow", Action = ["ssm:GetParameter", "ssm:GetParametersByPath"], Resource = "arn:aws:ssm:*:*:parameter/taxops11/prod/*" }
    ]
  })
}
```

### Task 4.2: Lambda de API (imagen de contenedor, Function URL)

**Files:**
- Create: `infra/modules/lambda-api/main.tf`
- Modify: `api/Dockerfile-api` (agregar capa de Mangum + handler Lambda, ver abajo)
- Modify: `api/requirements-api.txt` (agregar `mangum`)

```hcl
resource "aws_lambda_function" "api" {
  function_name = "taxops-api-prod"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repo_url}:${var.image_tag}"
  memory_size   = 1024 # Tesseract/WeasyPrint necesitan margen; empezar aquí y ajustar con CloudWatch
  timeout       = 60   # requests HTTP normales; los jobs largos van al worker (Task 4.3), no aquí
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type  = "NONE" # la auth la maneja FastAPI (JWT), no IAM
}
```

Cambio mínimo en `api/main.py` (no roto: Mangum envuelve la app ASGI existente sin tocar rutas):

```python
# api/main.py — agregar al final
from mangum import Mangum
handler = Mangum(app)
```

- [ ] Apply, commit.

### Task 4.3: Lambda worker (jobs largos, disparado por SQS)

**Files:**
- Create: `infra/modules/lambda-api/worker.tf`

```hcl
resource "aws_lambda_function" "worker" {
  function_name = "taxops-worker-prod"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repo_url}:${var.image_tag}"
  image_config { command = ["worker_handler.handler"] } # mismo repositorio de imagen, entrypoint distinto
  memory_size   = 2048 # OCR con Tesseract — igual que los 2Gi que ya usa en Cloud Run hoy
  timeout       = 840  # 14 min, deja margen bajo el máximo de 15 min de Lambda
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1 # un job OCR a la vez por invocación, evita competir por memoria
}
```

- [ ] Refactorizar `api/routers/exogenas.py` y `services/renta/job_processor.py` para que, en vez de lanzar un `ThreadPoolExecutor`, hagan `sqs.send_message()` y devuelvan el `job_id` de inmediato (202 Accepted). El procesamiento real se mueve a un `worker_handler.py` nuevo que consume el mensaje SQS y llama a la misma lógica de pipeline que ya existe (`pipeline/extractor.py`, etc.) — no se reescribe el pipeline, solo quién lo invoca.
- [ ] Apply, commit: `git commit -m "feat: worker Lambda para jobs largos vía SQS"`.

---

## Chunk 5: CDN, dominio y TLS

### Task 5.1: ACM + CloudFront delante de la Function URL

**Files:**
- Create: `infra/modules/cdn/main.tf`

```hcl
resource "aws_acm_certificate" "api" {
  provider          = aws.us_east_1 # ACM para CloudFront SIEMPRE en us-east-1
  domain_name       = "api.taxops.co" # ajustar al dominio real
  validation_method = "DNS"
}

resource "aws_cloudfront_distribution" "api" {
  enabled = true
  origin {
    domain_name = replace(var.lambda_function_url, "https://", "")
    origin_id   = "lambda-api"
    custom_origin_config {
      origin_protocol_policy = "https-only"
      http_port              = 80
      https_port             = 443
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  default_cache_behavior {
    target_origin_id       = "lambda-api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods         = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods          = ["GET", "HEAD"]
    cache_policy_id         = data.aws_cloudfront_cache_policy.disabled.id # API dinámica, no cachear por defecto
  }
  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.api.arn
    ssl_support_method  = "sni-only"
  }
  restrictions { geo_restriction { restriction_type = "none" } }
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}
```

### Task 5.2: Route53

**Files:**
- Create: `infra/modules/dns/main.tf`

- [ ] Hosted zone (~$0.50/mes, único costo fijo real de todo Fase 1) + registros `A`/`AAAA` alias hacia CloudFront (API) y hacia Amplify (frontend, Chunk 6).
- [ ] Apply, commit.

---

## Chunk 6: Frontend — Amplify Hosting reemplaza Vercel

### Task 6.1: App de Amplify conectada al repo de GitHub

**Files:**
- Create: `infra/modules/frontend/main.tf`

```hcl
resource "aws_amplify_app" "web" {
  name       = "taxops-web-prod"
  repository = "https://github.com/ABA-projects/TaxOps-11"
  platform   = "WEB_COMPUTE" # soporte SSR de Next.js 15 (App Router)

  build_spec = <<-YAML
    version: 1
    applications:
      - appRoot: taxops-web
        frontend:
          phases:
            preBuild:
              commands: ["npm ci"]
            build:
              commands: ["npm run build"]
          artifacts:
            baseDirectory: .next
            files: ["**/*"]
          cache:
            paths: ["node_modules/**/*"]
  YAML

  environment_variables = {
    NEXT_PUBLIC_API_URL = "https://api.taxops.co"
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.web.id
  branch_name = "main"
  enable_auto_build = true
}
```

- [ ] Conectar el token de GitHub (Amplify pide OAuth app o PAT — se guarda en SSM, no en el `.tf`).
- [ ] Apply, commit.
- [ ] **Nota de alcance:** este task NO borra el proyecto en Vercel — se deja correr en paralelo hasta el cutover (Chunk 8), es el rollback más simple si algo falla.

---

## Chunk 7: CI/CD — GitHub Actions apunta a AWS

### Task 7.1: Nuevo workflow de deploy

**Files:**
- Create: `.github/workflows/deploy-aws-lambda.yml`
- Modify: `.github/workflows/ci.yml` (cambiar el trigger de `workflow_dispatch` a `on: pull_request` — hoy no gatea nada, se aprovecha la migración para arreglarlo)

- [ ] `deploy-aws-lambda.yml`: checkout → configurar credenciales AWS (OIDC con `aws-actions/configure-aws-credentials`, **no** llaves de larga duración) → build+push a ECR → `aws lambda update-function-code` para `taxops-api-prod` y `taxops-worker-prod` → correr `alembic upgrade head` como paso de CI separado contra Neon (ya no al arrancar el Lambda — resuelve la condición de carrera mencionada en el discovery).
- [ ] Apply/push, commit.

---

## Chunk 8: Cutover y rollback

### Task 8.1: Runbook de corte

- [ ] Desplegar todo el stack AWS en paralelo (DNS aún apuntando a Cloud Run/Vercel).
- [ ] Smoke test manual contra las URLs de AWS directamente (Function URL, dominio de Amplify) antes de tocar DNS.
- [ ] Cambiar el registro Route53 de `api.taxops.co` y `app.taxops.co` (o el dominio real) para apuntar a CloudFront/Amplify. TTL bajo (60s) preparado con anticipación para poder revertir rápido.
- [ ] Monitorear CloudWatch Logs + métricas de error rate 24-48h.
- [ ] **Rollback:** revertir el registro DNS a Cloud Run/Vercel (siguen corriendo, no se apagan hasta confirmar estabilidad en AWS por al menos 1 semana).
- [ ] Una vez estable: apagar el servicio de Cloud Run y el proyecto de Vercel, borrar `deploy-cloud-run.yml`.

---

## Backlog — Fase 2 (NO ejecutar ahora, solo cuando haya tráfico/ingresos reales)

No son tasks de este plan, quedan documentados como referencia para cuando se revisite:

- **Aurora Serverless v2** en vez de Neon, si se necesita estar 100% dentro de AWS o el free tier de Neon se queda corto. Implica VPC + endpoints — recién ahí se justifica el costo de red.
- **Fargate/App Runner** en vez de Lambda, solo si el costo por invocación de Lambda supera lo que costaría un contenedor siempre encendido (cruce típico: tráfico sostenido alto, no picos).
- **ALB + WAF**, solo junto con Fargate (ALB no tiene capa gratuita, ~$16/mes mínimo).
- **AWS Budgets + Cost Anomaly Detection**: configurar desde ya en Chunk 1 aunque el gasto sea casi cero, es gratis y da alertas tempranas si algo se sale de lo esperado.
- **Reserved Capacity / Compute Savings Plans** una vez el patrón de tráfico sea predecible (típicamente 3-6 meses de datos de Fase 2).

---

## Siguiente paso

Este plan está listo para ejecutarse chunk por chunk. Antes de arrancar Chunk 0:
1. Confirmar cuenta de AWS a usar (nueva o existente) y el dominio real (se usó `taxops.co` como placeholder en Chunk 5).
2. Confirmar que se ejecuta con **superpowers:subagent-driven-development** (un sub-agente por chunk, con revisión de código entre cada uno) — es el modo recomendado para este harness.
