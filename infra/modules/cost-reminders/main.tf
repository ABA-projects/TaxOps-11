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
