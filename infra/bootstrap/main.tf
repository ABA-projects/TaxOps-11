data "aws_caller_identity" "current" {}

# Bucket S3 para el state remoto de Terraform (todos los módulos de infra/environments/*)
resource "aws_s3_bucket" "tfstate" {
  bucket = "taxops11-tfstate-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled" # permite recuperar un state anterior si un apply sale mal
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "tfstate_bucket_name" {
  value       = aws_s3_bucket.tfstate.bucket
  description = "Usar como 'bucket' en el backend.tf de infra/environments/prod"
}

# Nota: el locking usa "use_lockfile = true" nativo de S3 (Terraform 1.10+) — no hace falta
# tabla DynamoDB. Si en algún punto se baja a un Terraform < 1.10, habría que revivir esto.
