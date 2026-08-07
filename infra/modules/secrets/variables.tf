variable "secrets" {
  description = "Mapa nombre -> valor de secretos de aplicación. Se pasa por -var-file (terraform.tfvars.secret, gitignored), nunca hardcodeado."
  type        = map(string)
  sensitive   = true
  default     = {}
}
