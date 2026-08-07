terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Sin "profile" hardcodeado a propósito: localmente lo resuelve AWS_PROFILE=taxops-admin
# (vía direnv, ver docs/DIRENV-AWS-PROFILE.md); en CI lo resuelven las credenciales
# temporales que inyecta aws-actions/configure-aws-credentials (OIDC, ver Task 1.4).
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "taxops11"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}
