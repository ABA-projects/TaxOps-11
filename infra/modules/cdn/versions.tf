# Sin este bloque, un módulo hijo que usa un provider fuera del namespace "hashicorp/"
# (como cloudflare/cloudflare) resuelve mal el source y falla con "does not have a
# provider named registry.terraform.io/hashicorp/cloudflare" — confirmado con un
# terraform init real.
terraform {
  required_providers {
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}
