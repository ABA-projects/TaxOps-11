# Cada ARN va a una variable de GitHub → Settings → Secrets and variables → Actions → Variables.
output "role_arn" {
  value       = aws_iam_role.github_actions_terraform.arn
  description = "AWS_TERRAFORM_ROLE_ARN — solo terraform-apply.yml (environment: production)"
}

output "plan_role_arn" {
  value       = aws_iam_role.github_actions_plan.arn
  description = "AWS_PLAN_ROLE_ARN — terraform-plan.yml (pull_request)"
}

output "deploy_role_arn" {
  value       = aws_iam_role.github_actions_deploy.arn
  description = "AWS_DEPLOY_ROLE_ARN — deploy-lambda.yml y agentes-contables.yml (main)"
}
