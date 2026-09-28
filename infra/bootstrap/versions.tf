terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  # Sin profile hardcodeado: lo resuelve AWS_PROFILE del entorno (taxops-admin
  # para la cuenta vieja, taxops para la nueva). Bootstrap account-agnostic.

  default_tags {
    tags = {
      Project     = "taxops11"
      Environment = "bootstrap"
      ManagedBy   = "terraform"
    }
  }
}
