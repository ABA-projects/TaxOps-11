# Recordatorios puntuales por email — EventBridge Scheduler (one-time) + SNS. Ambos con
# capa gratuita perpetua a este volumen (Scheduler: 14M invocaciones/mes gratis siempre;
# SNS: 1M publishes + 1000 emails/mes gratis siempre) — el mecanismo de alerta en sí no
# cuesta nada nunca, sin importar cuánto dure el proyecto.

resource "aws_sns_topic" "reminders" {
  name = "taxops-cost-reminders"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.reminders.arn
  protocol  = "email"
  endpoint  = var.email
  # SNS manda un email de confirmación aparte — hay que darle click una vez para que la
  # suscripción quede activa, Terraform no puede confirmarla por vos.
}

resource "aws_iam_role" "scheduler" {
  name = "taxops-cost-reminder-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_publish" {
  name = "publish-to-sns"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sns:Publish"
      Resource = aws_sns_topic.reminders.arn
    }]
  })
}

resource "aws_scheduler_schedule" "reminders" {
  for_each = var.reminders

  name       = "taxops-reminder-${each.key}"
  group_name = "default"

  flexible_time_window {
    mode = "OFF" # queremos la fecha exacta, no una ventana
  }

  schedule_expression          = "at(${each.value.schedule_at})"
  schedule_expression_timezone = "America/Bogota"

  target {
    arn      = aws_sns_topic.reminders.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = each.value.message
  }

  # Un schedule one-time no se auto-borra tras dispararse (queda en estado "COMPLETED") —
  # no afecta nada dejarlo, evita que Terraform intente recrearlo en cada apply.
}

# Budget mensual de costo con alerta temprana. AWS Budgets da los primeros 2 budgets por
# cuenta gratis (perpetuo) — este es el primero, así que no cuesta nada. Vigila el gasto de
# ESTA cuenta (prod corre contra 562548008942/taxops). No ve el consolidado de la Organization
# (ese payer es 786567028012); para el total de las 3 cuentas se usa la revisión manual
# documentada en context/decisions.md. Notifica por email directo del budget (no vía SNS):
# un canal menos que confirmar y sin IAM extra.
resource "aws_budgets_budget" "monthly" {
  name         = "taxops-monthly-cost"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Avisa cuando el gasto REAL supera el umbral. A costo-cero el objetivo es enterarse de
  # cualquier repunte (un recurso olvidado, un build que se disparó) sin tener que consultar
  # Cost Explorer, que cobra US$0,01 por consulta.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100 # % del límite
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.email]
  }

  # Y un aviso anticipado al 80% del REAL, para reaccionar antes de cruzar el límite.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.email]
  }
}
