variable "email" {
  description = "Destino de los recordatorios (SNS email subscription)"
  type        = string
}

variable "reminders" {
  description = <<-EOT
    Mapa de recordatorios puntuales de costo/decisión — pensado para free tiers de 12
    meses (Amplify, etc.) o cualquier trigger fechado ya documentado como "decidir más
    adelante" (ver docs/AWS-ACCOUNT-SETUP-GUIDE.md §6.1). Cada key debe ser estable
    (no cambiar una vez creado, o Terraform destruye/recrea el schedule).
  EOT
  type = map(object({
    schedule_at = string # "YYYY-MM-DDTHH:MM:SS", sin zona — se aplica America/Bogota
    message     = string
  }))
  default = {}
}
