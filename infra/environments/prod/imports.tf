# Bloques import{} — solo se permiten en el root module (no dentro de un módulo
# reutilizable, ver infra/modules/lambda-api/{main,worker}.tf para el detalle de qué
# recursos adoptan). Cada uno acá corresponde a un recurso que ya existía en AWS antes de
# declararse en Terraform (típicamente auto-creado por otro servicio) y se adopta en vez
# de fallar con "already exists" en el primer apply.

import {
  to = module.lambda_api.aws_cloudwatch_log_group.api
  id = "/aws/lambda/taxops-api-prod"
}

import {
  to = module.lambda_api.aws_cloudwatch_log_group.worker
  id = "/aws/lambda/taxops-worker-prod"
}
