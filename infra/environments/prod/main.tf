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

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "jobs_table_name" {
  value = module.jobs.table_name
}

output "jobs_queue_url" {
  value = module.jobs.queue_url
}

output "github_actions_role_arn" {
  value       = module.github_oidc.role_arn
  description = "Copiar a GitHub → Settings → Secrets and variables → Actions → Variables → AWS_TERRAFORM_ROLE_ARN"
}
