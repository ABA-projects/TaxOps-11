module "ecr" {
  source = "../../modules/ecr"
}

module "secrets" {
  source  = "../../modules/secrets"
  secrets = var.secrets
}

module "github_oidc" {
  source = "../../modules/github-oidc"
}

module "jobs" {
  source = "../../modules/jobs"
}

module "storage" {
  source = "../../modules/storage"
}

# Estáticos (no dependen de ningún recurso) — permiten pasarlos a module.lambda_api sin
# crear un ciclo con module.cdn/module.amplify, que sí dependen de lambda_api (function_url
# y, transitivamente, api_domain). amplify_default_domain no se puede derivar de
# module.amplify.default_domain por la misma razón — se hardcodea el ID real ya creado
# (d2mechz6r82w9f, ver output amplify_default_domain de un apply anterior). Si el app de
# Amplify se recrea alguna vez, actualizar este valor a mano.
locals {
  cdn_domain_name        = "taxopsapp.com"
  cdn_api_subdomain      = "api"
  api_base_url           = "https://${local.cdn_api_subdomain}.${local.cdn_domain_name}"
  amplify_default_domain = "https://main.d2mechz6r82w9f.amplifyapp.com"
  allowed_origins        = "https://taxops-app.vercel.app,${local.amplify_default_domain},http://localhost:3000"
}

module "lambda_api" {
  source               = "../../modules/lambda-api"
  ecr_repo_url         = module.ecr.repository_url
  sqs_queue_arn        = module.jobs.queue_arn
  dynamodb_table_arn   = module.jobs.table_arn
  s3_bucket_arns       = [module.storage.renta_docs_bucket_arn, module.storage.job_artifacts_bucket_arn]
  secrets              = var.secrets
  sqs_queue_url        = module.jobs.queue_url
  jobs_table_name      = module.jobs.table_name
  s3_bucket_renta_docs = module.storage.renta_docs_bucket
  api_base_url         = local.api_base_url
  allowed_origins      = local.allowed_origins
}

module "cdn" {
  source              = "../../modules/cdn"
  domain_name         = local.cdn_domain_name
  api_subdomain       = local.cdn_api_subdomain
  lambda_function_url = module.lambda_api.function_url
}

module "amplify" {
  source              = "../../modules/amplify"
  github_access_token = var.github_access_token
  api_domain          = module.cdn.api_domain
}

module "cost_reminders" {
  source = "../../modules/cost-reminders"
  email  = "taxopsa@gmail.com"

  reminders = {
    # Cuenta AWS creada 2026-08-05T16:14:12-05:00 (aws organizations describe-account) —
    # el free tier de 12 meses de Amplify Hosting vence ~2027-08-05. Alerta 1 mes antes.
    amplify-free-tier = {
      schedule_at = "2027-07-05T09:00:00"
      message     = "TaxOps-11: el free tier de 12 meses de AWS Amplify Hosting vence ~2027-08-05 (build minutes, storage CDN, data transfer, SSR requests pasan a pago). Revisar costo real acumulado vs. alternativas (Vercel free tier, S3+CloudFront estático si aplica) antes de esa fecha. Ver docs/MIGRACION-AWS-CASE-STUDY.md."
    }
  }
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "lambda_api_function_url" {
  value = module.lambda_api.function_url
}

output "api_domain" {
  value       = module.cdn.api_domain
  description = "Dominio final de la API (CloudFront) — usar para probar antes de que el frontend/DNS lo referencien"
}

output "jobs_table_name" {
  value = module.jobs.table_name
}

output "jobs_queue_url" {
  value = module.jobs.queue_url
}

output "renta_docs_bucket" {
  value = module.storage.renta_docs_bucket
}

output "job_artifacts_bucket" {
  value = module.storage.job_artifacts_bucket
}

output "github_actions_role_arn" {
  value       = module.github_oidc.role_arn
  description = "Copiar a GitHub → Settings → Secrets and variables → Actions → Variables → AWS_TERRAFORM_ROLE_ARN"
}

output "amplify_default_domain" {
  value       = module.amplify.default_domain
  description = "URL de Amplify antes de tener dominio propio (Chunk 5 solo cubrió api.taxopsapp.com, no el frontend)"
}
