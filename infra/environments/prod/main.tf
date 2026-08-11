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
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "lambda_api_function_url" {
  value = module.lambda_api.function_url
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
