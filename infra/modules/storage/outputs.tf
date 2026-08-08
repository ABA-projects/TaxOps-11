output "renta_docs_bucket" {
  value = aws_s3_bucket.renta_docs.bucket
}

output "renta_docs_bucket_arn" {
  value = aws_s3_bucket.renta_docs.arn
}

output "job_artifacts_bucket" {
  value = aws_s3_bucket.job_artifacts.bucket
}

output "job_artifacts_bucket_arn" {
  value = aws_s3_bucket.job_artifacts.arn
}
