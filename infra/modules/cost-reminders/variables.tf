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

variable "monthly_budget_usd" {
  description = <<-EOT
    Límite mensual de gasto (USD) de ESTA cuenta para el budget de alerta. Default $1,
    coherente con la premisa costo-cero: a este proyecto cualquier mes por encima de ~$1
    es una anomalía que amerita mirar. Avisa al 80% y al 100% del gasto real.
  EOT
  type        = string
  default     = "1"
}
