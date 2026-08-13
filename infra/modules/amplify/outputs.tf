output "default_domain" {
  value       = "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.web.default_domain}"
  description = "URL por defecto de Amplify (antes de tener dominio propio) — probar acá primero"
}

output "app_id" {
  value = aws_amplify_app.web.id
}
