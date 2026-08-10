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
