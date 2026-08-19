# Reemplaza Google Cloud Storage (bucket "taxops-docs") — documentos de Renta y artefactos
# de jobs de exógenas. Ver Chunk 3 del plan de migración.

resource "aws_s3_bucket" "renta_docs" {
  bucket = "taxops-renta-docs-prod"
}

resource "aws_s3_bucket" "job_artifacts" {
  bucket = "taxops-job-artifacts-prod"
}

resource "aws_s3_bucket_lifecycle_configuration" "job_artifacts" {
  bucket = aws_s3_bucket.job_artifacts.id
  rule {
    id     = "expire-old-exports"
    status = "Enabled"
    filter {} # aplica a todos los objetos del bucket
    expiration {
      days = 30 # los .xlsx de exógenas no necesitan vivir para siempre — controla el storage $
    }
  }
  rule {
    id     = "expire-temp-uploads"
    status = "Enabled"
    filter { prefix = "uploads/" }
    expiration {
      days = 3 # uploads temporales pendientes de procesar + resultados derivados — no el documento fuente definitivo
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "job_artifacts" {
  bucket = aws_s3_bucket.job_artifacts.id

  cors_rule {
    allowed_methods = ["POST"] # generate_presigned_post — NO "PUT", el mecanismo de subida es multipart/form-data
    allowed_origins = ["https://app.taxopsapp.com", "http://localhost:3000"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_versioning" "renta_docs" {
  bucket = aws_s3_bucket.renta_docs.id
  versioning_configuration {
    status = "Enabled" # documentos tributarios de clientes — sí vale la pena poder recuperarlos
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "renta_docs" {
  bucket = aws_s3_bucket.renta_docs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    renta_docs    = aws_s3_bucket.renta_docs.id
    job_artifacts = aws_s3_bucket.job_artifacts.id
  }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
