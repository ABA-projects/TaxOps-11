variable "domain_name" {
  description = "Dominio raíz registrado en Cloudflare (ej. taxopsapp.com)"
  type        = string
}

variable "api_subdomain" {
  description = "Subdominio para la API (ej. api → api.taxopsapp.com)"
  type        = string
  default     = "api"
}

variable "lambda_function_url" {
  description = "Function URL de la Lambda API (module.lambda_api.function_url) — origin de CloudFront"
  type        = string
}
