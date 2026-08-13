output "api_domain" {
  value       = "https://${local.api_fqdn}"
  description = "URL pública final de la API detrás de CloudFront — reemplaza la Function URL cruda en FRONTEND_URL/API_BASE_URL"
}
