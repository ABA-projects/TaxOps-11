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
  region  = "us-east-1"
  profile = "taxops-admin"

  default_tags {
    tags = {
      Project     = "taxops11"
      Environment = "bootstrap"
      ManagedBy   = "terraform"
    }
  }
}
