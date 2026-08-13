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

# String estático (no depende de ningún recurso) — permite pasarlo a module.lambda_api
# sin crear un ciclo con module.cdn, que sí depende de lambda_api.function_url.
locals {
  cdn_domain_name   = "taxopsapp.com"
  cdn_api_subdomain = "api"
  api_base_url      = "https://${local.cdn_api_subdomain}.${local.cdn_domain_name}"
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
}

module "cdn" {
  source              = "../../modules/cdn"
  domain_name         = local.cdn_domain_name
  api_subdomain       = local.cdn_api_subdomain
  lambda_function_url = module.lambda_api.function_url
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
