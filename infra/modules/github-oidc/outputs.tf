output "role_arn" {
  value       = aws_iam_role.github_actions_terraform.arn
  description = "Copiar a GitHub → Settings → Secrets and variables → Actions → Variables → AWS_TERRAFORM_ROLE_ARN"
}
