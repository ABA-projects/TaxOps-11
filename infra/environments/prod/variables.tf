variable "aws_region" {
  description = "Región AWS de todo el proyecto"
  type        = string
  default     = "us-east-1"
}

variable "secrets" {
  description = "Secretos de aplicación (DATABASE_URL, SECRET_KEY, GROQ_API_KEY, etc.) — ver terraform.tfvars.secret.example"
  type        = map(string)
  sensitive   = true
  default     = {}
}
