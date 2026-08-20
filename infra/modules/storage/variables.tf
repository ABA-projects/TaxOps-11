variable "allowed_origins" {
  type        = list(string)
  description = "Orígenes permitidos para CORS del bucket de job-artifacts (uploads presignados). Debe mantenerse en sync con local.allowed_origins (mismo set que usa la API para ALLOWED_ORIGINS) — el frontend hoy sirve desde Vercel, no solo desde el dominio propio."
}
