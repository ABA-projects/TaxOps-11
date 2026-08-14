# Mismo motivo que infra/modules/cdn/versions.tf — un módulo hijo que usa un provider
# fuera del namespace "hashicorp/" necesita su propio required_providers, si no
# terraform init lo resuelve mal contra registry.terraform.io/hashicorp/cloudflare.
terraform {
  required_providers {
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}
