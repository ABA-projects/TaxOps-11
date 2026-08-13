terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    } # solo para el workaround temporal en infra/modules/lambda-api/main.tf (ver comentario ahí)
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    } # espera de propagación de IAM antes de que Amplify valide el compute role (ver infra/modules/amplify/main.tf)
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

# Sin api_token explícito a propósito: el provider lo lee solo de la env var
# CLOUDFLARE_API_TOKEN — localmente vía direnv (.envrc, gitignored), en CI vía el secret
# CLOUDFLARE_API_TOKEN inyectado como env var en terraform-plan.yml/terraform-apply.yml.
provider "cloudflare" {}
