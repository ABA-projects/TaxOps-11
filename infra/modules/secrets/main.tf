# SSM Parameter Store (Standard, SecureString) — no Secrets Manager.
# Secrets Manager cobra $0.40/secreto/mes; SSM Standard SecureString es $0.

# Terraform no permite usar un mapa "sensitive" directo como for_each (expondría las keys
# en el plan/state). Las KEYS (nombres como "DATABASE_URL") no son secretas por sí solas —
# solo los VALUES lo son — así que declaramos explícitamente que las keys son seguras de
# mostrar, y el value real sigue viniendo del mapa sensible.
locals {
  secret_names = nonsensitive(toset(keys(var.secrets)))
}

resource "aws_ssm_parameter" "this" {
  for_each = local.secret_names

  name  = "/taxops11/prod/${each.value}"
  type  = "SecureString"
  value = var.secrets[each.value] # este sí se mantiene sensible
  tier  = "Standard"              # gratis — no usar "Advanced" (tiene costo)
}
