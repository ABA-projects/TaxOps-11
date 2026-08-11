variable "ecr_repo_url" {
  description = "URL del repo ECR (module.ecr.repository_url)"
  type        = string
}

variable "image_tag" {
  description = "Tag de la imagen a desplegar — debe existir en ECR antes de aplicar (build+push manual/CI primero)"
  type        = string
  default     = "v3" # verificado con Lambda RIE local antes de pushear (Chunk 4)
}

variable "sqs_queue_arn" {
  type = string
}

variable "dynamodb_table_arn" {
  type = string
}

variable "s3_bucket_arns" {
  description = "ARNs de los buckets S3 (renta_docs, job_artifacts) a los que Lambda necesita acceso"
  type        = list(string)
}

variable "secrets" {
  description = "DATABASE_URL, SECRET_KEY, GROQ_API_KEY, etc. — mismo mapa que module.secrets, pasado directo como env vars (evita una llamada extra a SSM en cada cold start)"
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "sqs_queue_url" {
  type = string
}

variable "jobs_table_name" {
  type = string
}

variable "s3_bucket_renta_docs" {
  type = string
}

variable "allowed_origins" {
  description = "CORS — mismo valor que usa Cloud Run hoy, actualizar en Chunk 6 cuando exista el dominio de Amplify"
  type        = string
  default     = "https://taxops-app.vercel.app,http://localhost:3000"
}

variable "frontend_url" {
  description = "Para redirect post-login de Google OAuth — actualizar en Chunk 5/6 con el dominio real"
  type        = string
  default     = "https://taxops-app.vercel.app"
}
