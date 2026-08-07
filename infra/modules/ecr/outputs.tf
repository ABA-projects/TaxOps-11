output "repository_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "URL del repo ECR — usar en el build/push de la imagen Lambda (Chunk 4)"
}

output "repository_name" {
  value = aws_ecr_repository.api.name
}
