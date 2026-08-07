terraform {
  backend "s3" {
    bucket       = "taxops11-tfstate-786567028012"
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true # locking nativo de S3 (Terraform 1.10+) — reemplaza la tabla DynamoDB
    encrypt      = true
  }
}
