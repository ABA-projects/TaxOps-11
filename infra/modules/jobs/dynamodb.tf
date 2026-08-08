# Estado de jobs largos (exógenas, renta/OCR) — reemplaza el dict en memoria de
# ThreadPoolExecutor que se pierde en cada restart/redeploy (ver discovery, sección 2).
resource "aws_dynamodb_table" "jobs" {
  name         = "taxops-jobs-prod"
  billing_mode = "PAY_PER_REQUEST" # $0 al volumen actual (~50 usuarios/día)

  hash_key = "job_id"
  attribute {
    name = "job_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at" # limpieza automática de jobs viejos, sin cron ni costo extra
    enabled        = true
  }
}
