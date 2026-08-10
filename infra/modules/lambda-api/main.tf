# Lambda de API — reemplaza Cloud Run. La misma imagen de api/Dockerfile-api, con Mangum
# envolviendo la app FastAPI existente (sin reescribir rutas).
resource "aws_lambda_function" "api" {
  function_name = "taxops-api-prod"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repo_url}:${var.image_tag}"
  memory_size   = 1024 # Tesseract/WeasyPrint necesitan margen; ajustar con CloudWatch si hace falta
  timeout       = 60   # requests HTTP normales; los jobs largos van al worker (SQS), no aquí

  # x86_64 (no arm64): los binarios precompilados de Tesseract (api/Dockerfile-lambda) solo
  # existen para x86_64 — a este volumen de tráfico ambas arquitecturas caen en capa gratuita
  # igual, no vale la pena el riesgo/tiempo extra de recompilar para arm64 por un ahorro que
  # hoy es $0.
  architectures = ["x86_64"]

  lifecycle {
    ignore_changes = [image_uri] # el tag se actualiza vía CI/CD (aws lambda update-function-code), no vía terraform apply
  }
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE" # la auth la maneja FastAPI (JWT), no IAM
}

# authorization_type = "NONE" en el recurso de arriba NO alcanza por sí solo — Lambda además
# exige un permiso explícito en la resource policy de la función que autorice invocación
# pública vía Function URL. Sin esto, cualquier request da 403 Forbidden aunque el Function
# URL diga "NONE" (confirmado con un curl real contra la URL en producción).
resource "aws_lambda_permission" "public_function_url" {
  statement_id           = "AllowPublicFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
