# Plan de migración de cuenta AWS — TaxOps-11

> **Objetivo:** mover toda la infraestructura de TaxOps-11 desde la cuenta *management*
> `786567028012` (perfil `taxops-admin`) a la cuenta dedicada **`taxops` `562548008942`**
> (OU `Workloads`), replicando el patrón ya usado con éxito en DIAN-bot y trip-coveñas
> hacia `ai-platform` `080891698277`.
>
> **Premisas dadas:** la DATA de DynamoDB NO importa (se recrea vacía). El downtime NO
> importa (TaxOps aún no está liberado a usuarios). Región única: `us-east-1`.
>
> **Regla de oro:** este documento es solo un plan. Cada `apply`/`destroy` real lo ejecuta
> un humano tras leer el checkpoint de la fase previa.

---

## 0. Resumen ejecutivo

TaxOps-11 corre hoy en `786567028012` con esta arquitectura (grafo de `infra/environments/prod/main.tf`):

```
ecr ─┐
secrets ─┤
github-oidc ─┤
jobs (DynamoDB + SQS + DLQ) ─┤
storage (2 buckets S3) ─┴─► lambda-api (api + worker + Function URL) ─► cdn (ACM + CloudFront + DNS Cloudflare) ─► amplify (app + branch + dominio + DNS Cloudflare)
cost-reminders (SNS + EventBridge Scheduler)  [independiente]
```

**El plan tiene 8 fases:**

| Fase | Qué hace | Riesgo dominante |
|---|---|---|
| 0 | Prerrequisitos: perfil SSO `taxops`, secretos en GitHub, revisar SCPs | Bloqueo por SCP |
| 1 | Nuevo backend S3 de tfstate + `init -reconfigure` (state vacío) | Confusión de cuál state se toca |
| 2 | Ajustes de código account-agnostic (backend, `imports.tf`, ECR_REPO en CI) | Import de log groups inexistentes |
| 3 | `apply -target` base: `ecr`, `secrets`, `jobs`, `storage`, `github_oidc`, `cost_reminders` | SCP `require-tags` en buckets |
| 4 | Build + push de imagen a ECR nuevo (ANTES de la Lambda) | Lambda sin imagen |
| 5 | `apply -target` de `lambda_api` (api + worker + Function URL + permisos) | Permiso público Function URL (null_resource CLI) |
| 6 | `apply` de `cdn` — ACM + CloudFront + validación DNS. **Aún NO reapunta `api`** | `CNAMEAlreadyExists` por alias duplicado |
| 7 | `apply` de `amplify` + reapuntar DNS (`api` y `app`) a los recursos nuevos | `CNAMEAlreadyExists`, verificación DNS 48h |
| 8 | Verificación E2E y **destrucción** de la infra vieja en `786567028012` | Borrar antes de verificar |

**Riesgos principales (transversales), con mitigación basada en lecciones aprendidas:**

1. **`CNAMEAlreadyExists` en CloudFront y Amplify** (lección 3): un alias de dominio
   (`api.taxopsapp.com` / `app.taxopsapp.com`) no puede existir en dos distribuciones/apps a
   la vez. **Mitigación:** crear los recursos nuevos SIN reapuntar DNS todavía (probar por el
   dominio crudo de CloudFront/Amplify), y solo reapuntar Cloudflare cuando el nuevo esté
   verificado; si aun así choca, primero soltar el alias en el recurso viejo.
2. **Lambda de imagen sin imagen en ECR nuevo** (lección 4): las Lambdas `api`/`worker` usan
   `package_type = "Image"`. **Mitigación:** Fase 4 (build+push) es un gate duro antes de la
   Fase 5; `ecr` se aplica con `-target` en la Fase 3.
3. **SCP `require-tags` sobre buckets S3** (lección 1): ya se quitó `s3:CreateBucket` de la
   SCP, pero los buckets siguen necesitando tags. **Mitigación:** el provider ya trae
   `default_tags` (`Project/Environment/ManagedBy`) → todo recurso nace etiquetado.
4. **Secreto en texto plano commiteado**: `infra/environments/prod/terraform.tfvars.secret`
   contiene valores reales (DATABASE_URL con credenciales de Neon, SECRET_KEY, GROQ_API_KEY,
   GOOGLE_CLIENT_SECRET, BOOTSTRAP_SECRET). **Debe rotarse** durante la migración (Fase 0) y
   dejar de vivir en disco/repo — en la cuenta nueva los secretos se cargan por `-var-file`
   efímero (CI) o SSM. Ver §Secretos.
5. **`null_resource` con AWS CLI para el permiso público del Function URL** (`lambda-api/main.tf`):
   corre `aws lambda add-permission` vía `local-exec` con `--region us-east-1` hardcodeado y
   usa las credenciales del entorno. **Mitigación:** al aplicar la Fase 5 el `AWS_PROFILE`/las
   credenciales OIDC ya deben apuntar a la cuenta nueva; verificar el `statement-id`.

---

## Inventario completo de recursos (qué se crea y qué tiene estado)

### Con estado / datos (pero la DATA no importa → se recrean vacíos)
| Recurso | Módulo | Nota de migración |
|---|---|---|
| `aws_dynamodb_table.jobs` (`taxops-jobs-prod`, PAY_PER_REQUEST, TTL `expires_at`) | jobs | Se recrea vacía. No exportar datos. |
| `aws_sqs_queue.jobs` (`taxops-jobs-prod`, visibility 900s) | jobs | Vacía; drenar/ignorar mensajes en vuelo de la vieja. |
| `aws_sqs_queue.jobs_dlq` (`taxops-jobs-dlq-prod`) | jobs | Vacía. |
| `aws_s3_bucket.renta_docs` (`taxops-renta-docs-prod`, versioning ON, SSE AES256) | storage | Documentos de clientes. Se recrea vacío (no hay usuarios). Si algún día hubiera datos que conservar, sería un `aws s3 sync` aparte — hoy NO aplica. |
| `aws_s3_bucket.job_artifacts` (`taxops-job-artifacts-prod`, lifecycle 30d/3d, CORS POST) | storage | Vacío. |
| Backend tfstate S3 (`taxops11-tfstate-<account_id>`) | backend.tf / bootstrap | **NO se migra el state**: se arranca uno nuevo y vacío en la cuenta nueva (ver Fase 1). |

### Sin estado relevante (se recrean idénticos)
- `aws_ecr_repository.api` (`taxops-api`, IMMUTABLE, scan on push, lifecycle 3 imágenes).
- `aws_ssm_parameter.this` (SecureString `/taxops11/prod/<KEY>` por cada secreto).
- `aws_lambda_function.api` (`taxops-api-prod`, Image, 1024MB, 60s, x86_64) + `aws_lambda_function_url.api` + 2 `aws_lambda_permission` + `null_resource` de InvokeFunction.
- `aws_lambda_function.worker` (`taxops-worker-prod`, Image, 2048MB, 840s) + `aws_lambda_event_source_mapping.worker_sqs`.
- `aws_cloudwatch_log_group.api` y `.worker` (`/aws/lambda/taxops-*-prod`, 14 días).
- IAM: `taxops-lambda-exec-prod`, `taxops-amplify-ssr`, `taxops-cost-reminder-scheduler`, `taxops-github-actions-{plan,terraform,deploy}` + el OIDC provider de GitHub.
- `aws_acm_certificate.api` + validación (para `api.taxopsapp.com`).
- `aws_cloudfront_distribution.api` (alias `api.taxopsapp.com`, PriceClass_100, cache Disabled, origin-request AllViewerExceptHostHeader, origin_read_timeout 60).
- `aws_amplify_app.web` (`taxops-web-prod`, WEB_COMPUTE) + `aws_amplify_branch.main` + `aws_amplify_domain_association.app` (`app.taxopsapp.com`).
- `cost-reminders`: `aws_sns_topic.reminders` + suscripción email + `aws_scheduler_schedule` (`amplify-free-tier` @ 2027-07-05).

### Depende de DNS/Cloudflare (fuera de AWS)
- `cdn`: `data.cloudflare_zones.main` (zona `taxopsapp.com`) + `cloudflare_dns_record.acm_validation` + `cloudflare_dns_record.api` (CNAME `api` → CloudFront, `proxied=false`).
- `amplify`: `data.cloudflare_zones.main` + `cloudflare_dns_record.app_cert_validation` + `cloudflare_dns_record.app` (CNAME `app` → Amplify, `proxied=false`).
- La zona Cloudflare es **la misma** para vieja y nueva (el dominio no se recompra). Reapuntar = actualizar el `content` de esos CNAME (Terraform lo hace al recrear los records apuntando a los recursos nuevos).

### Depende de GitHub
- `amplify`: `access_token` (PAT) para conectar el repo `ABA-projects/TaxOps-11` y crear el webhook. Var `github_access_token` (secret GitHub `AMPLIFY_GITHUB_TOKEN`).
- `github-oidc`: OIDC provider + 3 roles con trust `repo:ABA-projects/TaxOps-11:*`. Los ARNs resultantes van a GitHub → Variables (`AWS_TERRAFORM_ROLE_ARN`, `AWS_PLAN_ROLE_ARN`, `AWS_DEPLOY_ROLE_ARN`) — **cambian de account id** y hay que actualizarlos.

---

## Qué está hardcodeado a la cuenta vieja `786567028012`

| Ubicación | Valor hoy | Acción |
|---|---|---|
| `infra/environments/prod/backend.tf` → `bucket` | `taxops11-tfstate-786567028012` | **Cambiar** a `taxops11-tfstate-562548008942` (Fase 2). |
| `infra/modules/github-oidc/variables.tf` → `tfstate_bucket` default | `taxops11-tfstate-786567028012` | **Cambiar** a `...-562548008942` (Fase 2). Usado para el ARN del `.tflock` en el rol plan. |
| `.github/workflows/deploy-lambda.yml` → `env.ECR_REPO` | `786567028012.dkr.ecr.us-east-1.amazonaws.com/taxops-api` | **Cambiar** a `562548008942.dkr...` (Fase 2). |
| GitHub → Variables `AWS_*_ROLE_ARN` | ARNs con `:786567028012:` | **Actualizar** tras Fase 3 con los outputs nuevos. |
| ACM cert ARN (`fa8b...480e`), CloudFront `E2ER4HHX39DUAW`, Lambda URL `iw7umncd...on.aws`, Amplify `d2mechz6r82w9f` | recursos vivos en la cuenta vieja | Se recrean en la nueva; los viejos se destruyen en Fase 8. |

**Ya es account-agnostic (usa `data.aws_caller_identity.current.account_id`):**
- `infra/bootstrap/main.tf` → nombre del bucket tfstate.
- `infra/modules/github-oidc/main.tf` → todos los ARNs de las policies IAM (`local.account_id`).
- Los nombres de recursos (`taxops-api-prod`, buckets, etc.) no llevan account id → no chocan.

> **Nota:** `providers.tf` NO tiene `profile` hardcodeado (lo resuelve `AWS_PROFILE` vía direnv
> local o las credenciales OIDC en CI). Solo hay que apuntar `AWS_PROFILE` al perfil nuevo.

---

## Dominios y DNS (Cloudflare — zona `taxopsapp.com`)

| FQDN | Servicio AWS | Registro Cloudflare | Reapuntar en |
|---|---|---|---|
| `api.taxopsapp.com` | CloudFront (`cdn`) | CNAME → `<cloudfront>.cloudfront.net`, `proxied=false` | Fase 6/7 |
| `app.taxopsapp.com` | Amplify (`amplify`) | CNAME → target de Amplify, `proxied=false` | Fase 7 |
| `_<acm_validation>.taxopsapp.com` | ACM DNS validation (`cdn`) | CNAME de validación, `proxied=false` | Fase 6 (se recrea) |
| `_<amplify_cert>.taxopsapp.com` | Amplify cert validation | CNAME de validación, `proxied=false` | Fase 7 (se recrea) |

Todo se gestiona por Terraform con el provider `cloudflare` (token en env var `CLOUDFLARE_API_TOKEN`). **Regla de la lección 3:** el CNAME de `api`/`app` no puede apuntar al CloudFront/Amplify viejo cuando se crea el nuevo con el mismo alias → o se recrea el record apuntando al nuevo (Terraform lo hace en el mismo apply que crea el recurso) o, si AWS devuelve `CNAMEAlreadyExists`, primero se suelta el alias del recurso viejo.

---

## Prerrequisitos (Fase 0)

1. **Perfil SSO `taxops` (cuenta `562548008942`)**
   - Configurar en `~/.aws/config` un perfil SSO (p. ej. `taxops`) apuntando a `562548008942`
     con un permission set que permita crear la infra (Administrator o equivalente acotado).
   - `aws sso login --profile taxops` y verificar:
     `AWS_PROFILE=taxops aws sts get-caller-identity` → debe mostrar `Account: 562548008942`.
   - Actualizar `docs/DIRENV-AWS-PROFILE.md` / `.envrc` para exportar `AWS_PROFILE=taxops`
     al entrar al repo (hoy usa `taxops-admin`).

2. **Revisar las 4 SCP de la OU `Workloads` contra el plan de recursos** (solo lectura):
   - `region-lock us-east-1`: OK, todo el proyecto ya es `us-east-1` (incluido ACM, que para
     CloudFront debe vivir en us-east-1 — ya se cumple).
   - `deny-expensive-services`: verificar que NO bloquee Amplify, CloudFront, Lambda, ECR,
     DynamoDB PAY_PER_REQUEST, SQS, SNS, EventBridge Scheduler, SSM Standard, ACM. Ninguno es
     "caro", pero confirmar la lista exacta de la SCP antes de la Fase 3.
   - `require-tags` (SIN `s3:CreateBucket`): OK para crear buckets; igual el provider pone
     `default_tags`. Confirmar que la SCP exige exactamente el/los tag(s) que `default_tags`
     provee (`Project`). Si exige más (p. ej. `Environment`, `Owner`), añadirlos a
     `default_tags` en `providers.tf` **antes** de aplicar.
   - `protect-org`: no debería afectar workloads; confirmar que no restrinja `iam:*` necesario
     para el OIDC provider y los roles `taxops-*`.

3. **Secretos en GitHub (Environment `production` / repo secrets)** — ya existen para la cuenta
   vieja; se reutilizan salvo los que se rotan (ver §Secretos). Confirmar presencia de:
   `DATABASE_URL, SECRET_KEY, GROQ_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
   TAXOPS_SUPERADMIN_EMAILS, BOOTSTRAP_SECRET, AMPLIFY_GITHUB_TOKEN, CLOUDFLARE_API_TOKEN`.

4. **Bucket de tfstate nuevo** — dos opciones:
   - **(Recomendada) Bootstrap:** correr `infra/bootstrap` con `AWS_PROFILE=taxops` para crear
     `taxops11-tfstate-562548008942` (versioning + SSE + public access block). El bootstrap ya
     usa `account_id` dinámico → sale con el nombre correcto sin editar nada.
   - **(Alternativa) Manual:** `aws s3 mb` + versioning + SSE + block public access, con el tag
     `Project=taxops11`.

5. **Token de Cloudflare** con permisos de edición de DNS sobre la zona `taxopsapp.com`
   (mismo token que ya se usa; exportar `CLOUDFLARE_API_TOKEN` local o tenerlo como secret en CI).

6. **Docker** disponible localmente (o correr el build/push por CI) para la Fase 4, con el
   `Dockerfile-lambda` (`api/Dockerfile-lambda`, x86_64 / linux/amd64).

**Checkpoint Fase 0:** `get-caller-identity` = `562548008942`; bucket tfstate nuevo existe y
está versionado; SCPs revisadas sin bloqueos; secretos presentes en GitHub; token Cloudflare OK.

---

## Fase 1 — Backend nuevo y state vacío

Como la DATA no importa y no se migra state, se arranca un state **nuevo y vacío** en la cuenta nueva (no se copia el `.tfstate` viejo).

1. (Tras editar `backend.tf` en Fase 2) desde `infra/environments/prod`:
   `AWS_PROFILE=taxops terraform init -reconfigure`
   → Terraform detecta backend nuevo (bucket `...-562548008942`). Ante "¿copiar state
   existente?", responder **NO** (queremos empezar vacío).
2. Confirmar que el backend usa `use_lockfile = true` (locking nativo S3, Terraform 1.10+) —
   ya está así, sin DynamoDB (lección 6). Requiere Terraform ≥ 1.10; CI usa `~> 1.15`, OK.

> **Nota de orden:** en la práctica conviene hacer primero los edits de la Fase 2 (backend
> apunta al bucket nuevo) y luego el `init -reconfigure`. Se listan como fases separadas por
> claridad, pero el `init` ocurre después de editar `backend.tf`.

**Checkpoint Fase 1:** `terraform init -reconfigure` OK contra el bucket nuevo; `terraform state
list` vacío (0 recursos); el `.tflock` se crea/borra sin error (permite validar permisos del bucket).

---

## Fase 2 — Ajustes de código account-agnostic (solo edición, sin apply)

> Estos edits los revisa y aplica el humano; el agente solo los documenta.

1. `infra/environments/prod/backend.tf` → `bucket = "taxops11-tfstate-562548008942"`.
2. `infra/modules/github-oidc/variables.tf` → default de `tfstate_bucket` a
   `"taxops11-tfstate-562548008942"`.
3. `.github/workflows/deploy-lambda.yml` → `env.ECR_REPO` a
   `562548008942.dkr.ecr.us-east-1.amazonaws.com/taxops-api`.
4. **`infra/environments/prod/imports.tf` (lección 6 / adopción de recursos):** los dos
   `import{}` adoptan log groups que **YA existían** en la cuenta vieja
   (`/aws/lambda/taxops-api-prod`, `/aws/lambda/taxops-worker-prod`). En la cuenta nueva **NO
   existen** → el import fallará ("Cannot import non-existent remote object"). **Quitar (o
   comentar) ambos bloques `import{}` antes del primer apply.** Terraform creará los log groups
   normalmente vía los `aws_cloudwatch_log_group` del módulo `lambda-api`. (Se pueden reponer
   más adelante solo si algún servicio vuelve a auto-crearlos antes que Terraform.)
5. Revisar `terraform.tfvars.secret`: **no debe usarse con valores commiteados**. Para apply
   local usar un `-var-file` fuera del repo o exportar por env; en CI ya se genera
   `terraform.tfvars.secret.json` efímero desde GitHub Secrets. Ver §Secretos (rotación).

**Checkpoint Fase 2:** `terraform fmt -check -recursive` OK; `terraform validate` OK; `grep -r
786567028012 infra/ .github/` sin coincidencias (salvo este documento); `imports.tf` sin
bloques activos.

---

## Fase 3 — Base sin dependencias de imagen ni DNS (`apply -target`)

Aplicar primero lo que no depende de la imagen ECR ni del DNS, para dejar ECR listo (lección 4)
y descubrir temprano cualquier bloqueo de SCP.

```
AWS_PROFILE=taxops terraform apply \
  -target=module.ecr \
  -target=module.secrets \
  -target=module.jobs \
  -target=module.storage \
  -target=module.github_oidc \
  -target=module.cost_reminders \
  -var-file=<secretos-fuera-del-repo>
```

- `module.secrets` necesita `var.secrets` (mapa) → pasar el var-file de secretos.
- `module.github_oidc` no toma inputs desde el root (usa defaults). Genera los ARNs nuevos.

**Riesgos/mitigación:**
- *SCP `require-tags` en buckets (lección 1):* mitigado por `default_tags`. Si falla, revisar qué
  tag exige la SCP y añadirlo a `default_tags`.
- *`deny-expensive-services`:* si bloquea algún servicio, ajustar la SCP (fuera de este repo, en
  la cuenta management) o el diseño — confirmar en Fase 0.

**Checkpoint Fase 3:**
- `terraform output ecr_repository_url` → `562548008942.dkr.ecr.us-east-1.amazonaws.com/taxops-api`.
- `AWS_PROFILE=taxops aws ssm get-parameters-by-path --path /taxops11/prod --query 'Parameters[].Name'`
  lista los 7 parámetros.
- `aws dynamodb describe-table --table-name taxops-jobs-prod` OK; colas SQS creadas; 2 buckets creados y etiquetados.
- `terraform output github_actions_role_arn / plan_role_arn / deploy_role_arn` → ARNs con `:562548008942:`.
- **Acción manual:** actualizar GitHub → Variables `AWS_TERRAFORM_ROLE_ARN`, `AWS_PLAN_ROLE_ARN`,
  `AWS_DEPLOY_ROLE_ARN` con los ARNs nuevos.

> **Lección 2 (trust OIDC):** hoy el trust es exacto (`repo:ABA-projects/TaxOps-11:pull_request`,
> `:environment:production`, `:ref:refs/heads/main`). Con el flujo actual funciona porque el
> claim `sub` de GitHub coincide con esos patrones. **Si tras la migración un workflow falla al
> asumir el rol** con `Not authorized to perform sts:AssumeRoleWithWebIdentity`, aplicar la
> lección: relajar los `values` del trust a comodines que toleren variantes del claim (p. ej.
> `repo:ABA-projects/TaxOps-11:*` o el patrón `repo:owner*/repo*:*`). Verificar el `sub` real en
> el log del run fallido antes de tocar el trust.

---

## Fase 4 — Build + push de la imagen a ECR nuevo (GATE antes de la Lambda)

**Lección 4 (crítica):** las Lambdas son `package_type = "Image"`; sin imagen en el ECR nuevo,
`module.lambda_api` falla al crear la función.

1. Login al ECR nuevo:
   `AWS_PROFILE=taxops aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 562548008942.dkr.ecr.us-east-1.amazonaws.com`
2. Build (x86_64 / linux/amd64, lección de arquitectura de Tesseract):
   `docker build --platform linux/amd64 -f api/Dockerfile-lambda -t 562548008942.dkr.ecr.us-east-1.amazonaws.com/taxops-api:v3 .`
   - El tag debe coincidir con `var.image_tag` de `lambda-api` (default `v3`). Si se usa el `sha`
     u otro tag, pasar `-var image_tag=<tag>` en la Fase 5.
   - **Lección 5 (CI build antes de terraform):** aquí aplica igual — la imagen debe existir
     antes del apply de la Lambda. Si en algún flujo un `archive_file`/data source dependiera del
     build, ese build va primero.
   - Recordar `ECR IMMUTABLE`: no repushear el mismo tag; usar uno nuevo si hay que reintentar.
3. Push:
   `docker push 562548008942.dkr.ecr.us-east-1.amazonaws.com/taxops-api:v3`

**Checkpoint Fase 4:**
`AWS_PROFILE=taxops aws ecr describe-images --repository-name taxops-api --query 'imageDetails[].imageTags'`
muestra el tag esperado (`v3` o el elegido).

---

## Fase 5 — Lambda API + worker (`apply -target`)

```
AWS_PROFILE=taxops terraform apply \
  -target=module.lambda_api \
  -var-file=<secretos-fuera-del-repo>
```

Crea: log groups (`api`/`worker`), `aws_lambda_function.api` + Function URL + `worker` +
event source mapping (SQS→worker) + los 2 `aws_lambda_permission` + el `null_resource` del
permiso `lambda:InvokeFunction`.

**Riesgos/mitigación:**
- *`null_resource.public_function_url_invoke_permission` (local-exec con AWS CLI):* corre
  `aws lambda add-permission ... --region us-east-1` con las credenciales del entorno. **Debe
  ejecutarse con `AWS_PROFILE=taxops`** (o credenciales OIDC de la cuenta nueva). Si el apply es
  local, asegurar que el profile activo es el nuevo, no `taxops-admin`. El `statement-id`
  (`AllowPublicFunctionUrlInvokeFunction`) es idempotente con `|| true`.
- *`ignore_changes = [image_uri]`:* correcto — el tag lo maneja el CI luego; el apply inicial
  usa `var.image_tag`.
- *Function URL 403 si faltan permisos:* ya cubierto por los dos `aws_lambda_permission` +
  el `null_resource` (documentado en el módulo).

**Checkpoint Fase 5:**
- `terraform output lambda_api_function_url` → URL `*.lambda-url.us-east-1.on.aws`.
- `curl -sf "$(terraform output -raw lambda_api_function_url)health"` → `{"status":"ok"}`
  (probar por la Function URL cruda, **sin** DNS todavía).
- Worker: `aws lambda get-function --function-name taxops-worker-prod` OK; event source mapping
  `Enabled` contra la cola `taxops-jobs-prod`.

---

## Fase 6 — CDN (ACM + CloudFront) SIN reapuntar `api` todavía

```
AWS_PROFILE=taxops CLOUDFLARE_API_TOKEN=<token> terraform apply \
  -target=module.cdn \
  -var-file=<secretos-fuera-del-repo>
```

Crea: `aws_acm_certificate.api` (`api.taxopsapp.com`, DNS validation) +
`cloudflare_dns_record.acm_validation` + `aws_acm_certificate_validation.api` +
`aws_cloudfront_distribution.api` + `cloudflare_dns_record.api` (CNAME `api` → CloudFront nuevo).

**Riesgo dominante — `CNAMEAlreadyExists` (lección 3):** `api.taxopsapp.com` sigue siendo alias
del CloudFront **viejo** (`E2ER4HHX39DUAW`) en la cuenta vieja. CloudFront no deja registrar el
mismo alias en dos distribuciones.

**Estrategia recomendada (downtime OK):** como el downtime no importa, **soltar el alias en el
CloudFront viejo primero** para evitar el choque:
   - Opción A (limpia): en la cuenta vieja, quitar `api.taxopsapp.com` de los `aliases` de
     `E2ER4HHX39DUAW` (o directamente destruir el `cdn` viejo — se hace igual en Fase 8; se
     puede adelantar aquí solo la distribución de la API). Tras soltar el alias, aplicar la
     Fase 6 en la cuenta nueva.
   - Opción B: crear la distribución nueva **sin alias** primero, validar por su
     `*.cloudfront.net`, y en la Fase 7 mover el alias. Requiere editar el módulo (no
     preferido — el módulo declara el alias fijo).
   → **Preferir Opción A**: destruir/soltar el alias del CloudFront viejo, luego `apply` Fase 6.

El CNAME de validación de ACM (`proxied=false`) y el CNAME `api` los gestiona Cloudflare vía
Terraform. La validación ACM puede tardar minutos.

**Checkpoint Fase 6:**
- `aws acm describe-certificate` (cuenta nueva) → `Status: ISSUED`.
- `aws cloudfront get-distribution --id <nuevo>` → `Status: Deployed`, alias `api.taxopsapp.com`.
- Tras propagación DNS: `curl -sf https://api.taxopsapp.com/health` → `{"status":"ok"}`
  (ya apuntando al CloudFront nuevo → Lambda nueva).
- `dig api.taxopsapp.com CNAME` apunta al `*.cloudfront.net` **nuevo**.

---

## Fase 7 — Amplify + reapuntar `app` (y confirmar `api`)

```
AWS_PROFILE=taxops CLOUDFLARE_API_TOKEN=<token> terraform apply \
  -var-file=<secretos-fuera-del-repo>
```

(Ya sin `-target`: aplica todo, incluido `module.amplify` y cierra cualquier pendiente.)

Crea: `aws_amplify_app.web` (con `access_token` = PAT de GitHub) + `aws_amplify_branch.main`
(auto-build) + `aws_amplify_domain_association.app` (`app.taxopsapp.com`) +
`cloudflare_dns_record.app_cert_validation` + `cloudflare_dns_record.app` +
`time_sleep.wait_for_iam_propagation` (15s por la consistencia del compute role, ya en el módulo).

**Riesgos/mitigación:**
- *`CNAMEAlreadyExists` / dominio en uso (lección 3):* `app.taxopsapp.com` sigue asociado a la
  Amplify vieja (`d2mechz6r82w9f`). **Soltar el custom domain de la Amplify vieja primero** (o
  destruir el `amplify` viejo) antes/durante esta fase. Con downtime OK, se puede destruir el
  `amplify` viejo antes de crear el nuevo.
- *Conexión a GitHub / webhook:* Amplify usa el PAT (`AMPLIFY_GITHUB_TOKEN`) una sola vez para
  conectar el repo y crear el webhook. Verificar que el PAT sigue válido y con scope `repo`
  (o fine-grained: Contents RO + Webhooks RW). `ignore_changes=[access_token]` evita diffs por
  rotación.
- *Verificación DNS de Amplify hasta 48h* (nota oficial para dominios de terceros/Cloudflare):
  `wait_for_verification=false` a propósito para no bloquear el apply. La verificación ocurre
  async; el sitio por dominio propio puede tardar en resolver.
- *Build de Amplify:* dispara un build de `main` al conectar. Requiere que el repo compile
  (CI `web-build` ya lo valida). El `compute_role_arn`/`iam_service_role_arn` apuntan a
  `taxops-amplify-ssr` (creado en este módulo); el `time_sleep` cubre la propagación IAM.

**Checkpoint Fase 7:**
- `terraform output amplify_default_domain` → probar `https://main.<appid>.amplifyapp.com` primero.
- `terraform output amplify_custom_domain` → `https://app.taxopsapp.com`.
- `aws amplify get-app --app-id <nuevo>` → `productionBranch.status: SUCCEED`.
- Tras propagación: `curl -sfI https://app.taxopsapp.com` → 200; el frontend llama a
  `https://api.taxopsapp.com` (env `NEXT_PUBLIC_API_URL`/`INTERNAL_API_URL`).
- `terraform plan` → **sin cambios** (todo convergido en la cuenta nueva).

---

## Fase 8 — Verificación E2E y destrucción de la infra vieja

**Primero verificar (NO borrar antes):**
1. E2E en la cuenta nueva: login (Google OAuth — validar `redirect_uri`/`API_BASE_URL`), subida
   de documento (S3 presigned POST → `job_artifacts`), job async (SQS → worker → DynamoDB),
   `/health`, endpoints GET con `Authorization` (el que motivó `Managed-AllViewerExceptHostHeader`).
2. Confirmar que los DNS `api`/`app` resuelven a los recursos **nuevos** (`dig`).
3. Confirmar suscripción SNS de `cost-reminders`: hay que **confirmar el email** una vez
   (AWS manda un correo de confirmación; Terraform no lo confirma solo). Endpoint: `taxopsa@gmail.com`.
4. Rotación de secretos aplicada (ver §Secretos) y probada en la app nueva.

**Luego destruir la infra vieja en `786567028012`** (perfil `taxops-admin`), en este orden para
evitar dependencias colgadas:
1. Amplify vieja (`d2mechz6r82w9f`) — app, branch, domain association, DNS records viejos si aún existieran.
2. CloudFront viejo (`E2ER4HHX39DUAW`) — disable → wait Deployed → delete; + ACM viejo
   (`fa8b...480e`) + registros de validación viejos.
3. Lambdas (`taxops-api-prod`, `taxops-worker-prod`) + Function URL + event source mapping + permisos.
4. `jobs` (DynamoDB `taxops-jobs-prod`, SQS `taxops-jobs-prod`/`-dlq-prod`).
5. `storage` (buckets `taxops-renta-docs-prod`, `taxops-job-artifacts-prod` — **vaciar antes**:
   `aws s3 rm s3://... --recursive`; ojo versioning en `renta-docs` → borrar versiones o usar
   lifecycle/`--force` del provider al `destroy`).
6. `secrets` (SSM `/taxops11/prod/*`), ECR (`taxops-api` + imágenes), `cost-reminders`
   (SNS + scheduler), `github-oidc` (OIDC provider + roles `taxops-*`).
7. Bucket tfstate viejo (`taxops11-tfstate-786567028012`) — **último**, cuando ya no se
   necesite el state viejo para nada. Vaciar versiones y borrar.

> **Cómo destruir:** lo más limpio es hacer el `terraform destroy` de la infra vieja **desde un
> checkout apuntando al backend/config viejos** (o desde el `.tfstate` viejo que aún existe en
> `.terraform/` local antes de reconfigurar). Como el `init -reconfigure` de la Fase 1 ya movió
> el backend al bucket nuevo, para destruir lo viejo conviene: (a) un worktree/branch separado
> con `backend.tf` apuntando al bucket viejo + `AWS_PROFILE=taxops-admin` + `terraform init
> -reconfigure` + `terraform destroy`; o (b) borrado manual dirigido por consola/CLI recurso por
> recurso siguiendo el orden de arriba. **Nunca** correr `destroy` con el profile nuevo apuntando
> al state nuevo pensando que borra lo viejo.

**Checkpoint Fase 8 (final):**
- App 100% funcional en la cuenta nueva (E2E verde).
- `AWS_PROFILE=taxops-admin` → `aws resourcegroupstaggingapi get-resources
  --tag-filters Key=Project,Values=taxops11` **vacío** (o solo lo que se decida conservar).
- `aws s3 ls | grep taxops` sin buckets viejos.
- Cero costo residual en la cuenta vieja para TaxOps-11.

---

## Secretos a migrar (nombres, SIN valores)

Viven en 3 lugares hoy y se materializan como SSM SecureString (`/taxops11/prod/<KEY>`) + env
vars de las Lambdas:

| Secreto (nombre) | Origen | Destino en cuenta nueva | Rotar |
|---|---|---|---|
| `DATABASE_URL` | GitHub Secret / tfvars | SSM `/taxops11/prod/DATABASE_URL` + env Lambda | **Sí** (credencial Neon expuesta en repo) |
| `SECRET_KEY` (JWT) | GitHub Secret / tfvars | SSM + env Lambda | **Sí** (expuesta en repo) |
| `GROQ_API_KEY` | GitHub Secret / tfvars | SSM + env Lambda + agentes CI | **Sí** (expuesta en repo) |
| `GOOGLE_CLIENT_ID` | GitHub Secret / tfvars | SSM + env Lambda | Opcional (no secreto) |
| `GOOGLE_CLIENT_SECRET` | GitHub Secret / tfvars | SSM + env Lambda | **Sí** (expuesto en repo) |
| `TAXOPS_SUPERADMIN_EMAILS` | GitHub Secret / tfvars | SSM + env Lambda | No (no secreto) |
| `BOOTSTRAP_SECRET` | GitHub Secret / tfvars | SSM + env Lambda | **Sí** (expuesto en repo) |
| `AMPLIFY_GITHUB_TOKEN` (PAT GitHub) | GitHub Secret / `var.github_access_token` | Amplify `access_token` (NO va a env de Lambda) | Recomendado |
| `CLOUDFLARE_API_TOKEN` | GitHub Secret / env var | Solo entorno (provider Cloudflare) | Opcional |

**Mecánica:** en CI (`terraform-apply.yml`) se genera `terraform.tfvars.secret.json` efímero
desde los GitHub Secrets → `terraform apply -var-file=...`. Para apply local, usar un var-file
**fuera del repo** o exportar por entorno; **no** commitear valores. Google OAuth: si cambia
`API_BASE_URL`/`redirect_uri` (no cambia, sigue `https://api.taxopsapp.com`), no hay que tocar la
consola de Google; si se rota `GOOGLE_CLIENT_SECRET`, actualizar el secret en GitHub y re-aplicar.

> ⚠️ **Acción de seguridad (independiente de la migración):** `infra/environments/prod/
> terraform.tfvars.secret` está commiteado con valores reales. Rotar `DATABASE_URL`, `SECRET_KEY`,
> `GROQ_API_KEY`, `GOOGLE_CLIENT_SECRET`, `BOOTSTRAP_SECRET`, purgar el archivo del historial de
> git y confirmar que está en `.gitignore`. La migración es el momento natural para hacerlo.

---

## Puntos manuales (checklist)

- [ ] Configurar perfil SSO `taxops` (562548008942) y `aws sso login`.
- [ ] Revisar las 4 SCP de `Workloads` (sobre todo `require-tags` y `deny-expensive-services`).
- [ ] Bootstrap del bucket tfstate nuevo.
- [ ] `init -reconfigure` respondiendo **NO** a copiar state.
- [ ] Editar `backend.tf`, `github-oidc/variables.tf`, `deploy-lambda.yml`; quitar `imports.tf`.
- [ ] Actualizar GitHub Variables `AWS_*_ROLE_ARN` con los ARNs nuevos (post Fase 3).
- [ ] Build+push imagen a ECR nuevo antes de la Lambda.
- [ ] Soltar alias `api.taxopsapp.com` del CloudFront viejo antes de crear el nuevo (Fase 6).
- [ ] Soltar `app.taxopsapp.com` de la Amplify vieja antes de crear la nueva (Fase 7).
- [ ] **Confirmar la suscripción SNS por email** (`taxopsa@gmail.com`) — clic en el correo.
- [ ] Verificar/renovar el PAT de GitHub para Amplify.
- [ ] Rotar secretos expuestos y purgar `terraform.tfvars.secret` del repo/historial.
- [ ] E2E verde en la cuenta nueva antes de destruir lo viejo.
- [ ] `destroy` de la infra vieja desde config apuntando al backend viejo + `taxops-admin`.

---

## Notas de dependencias (por qué este orden)

- El grafo de `main.tf` fuerza: `ecr/secrets/jobs/storage/github-oidc` → `lambda_api` →
  `cdn` → `amplify`. Por eso ECR va antes de la Lambda (lección 4) y CDN/Amplify al final.
- `cdn` depende de `lambda_api.function_url` (origin) → no se puede crear CDN sin Lambda.
- `amplify` depende de `cdn.api_domain` (env `NEXT_PUBLIC_API_URL`) → va después de CDN.
- `local.api_base_url`/`allowed_origins` son **strings estáticos** (no referencias a módulos)
  a propósito, para romper el ciclo `lambda_api ↔ cdn`. No hay que tocarlos: el dominio no cambia.
- `cost_reminders` es independiente → se puede aplicar en la Fase 3 sin bloquear nada.
