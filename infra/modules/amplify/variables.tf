variable "github_repo_url" {
  description = "URL del repo (Amplify hace polling/webhook sobre esto)"
  type        = string
  default     = "https://github.com/ABA-projects/TaxOps-11"
}

variable "github_access_token" {
  description = "PAT (fine-grained: Contents read-only + Webhooks read/write, o classic: scope 'repo') — ver infra/environments/prod/variables.tf"
  type        = string
  sensitive   = true
}

variable "api_domain" {
  description = "module.cdn.api_domain — para NEXT_PUBLIC_API_URL en el build de Amplify"
  type        = string
}

variable "domain_name" {
  description = "Dominio raíz en Cloudflare (ej. taxopsapp.com) — el frontend cuelga de app.<domain_name>"
  type        = string
}

variable "app_subdomain" {
  description = "Subdominio del frontend (ej. app → app.taxopsapp.com)"
  type        = string
  default     = "app"
}
