resource "aws_ecr_repository" "api" {
  name                 = "taxops-api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      # Solo 3 imágenes (actual + 2 rollbacks) — con Tesseract/WeasyPrint cada imagen puede
      # rondar 300-500MB, y el free tier de ECR es 500MB total. 3 imágenes mantiene el
      # storage dentro (o muy cerca) del free tier en vez de acumular indefinidamente.
      description = "Mantener solo las últimas 3 imágenes (capa gratuita ECR = 500MB)"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 3
      }
      action = { type = "expire" }
    }]
  })
}
