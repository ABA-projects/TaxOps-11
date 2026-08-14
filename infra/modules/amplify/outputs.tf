output "default_domain" {
  value       = "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.web.default_domain}"
  description = "URL por defecto de Amplify (antes de tener dominio propio) — probar acá primero"
}

output "app_id" {
  value = aws_amplify_app.web.id
}

output "custom_domain" {
  value       = "https://${var.app_subdomain}.${var.domain_name}"
  description = "Dominio propio del frontend — verificación DNS puede tardar hasta 48h (nota oficial de AWS para dominios de terceros como Cloudflare)"
}
