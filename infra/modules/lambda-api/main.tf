# Variables de entorno — compartidas entre la API y el worker (mismo rol IAM, mismo
# acceso a todo de cualquier forma). No se setea AWS_REGION explícito: es una env var
# reservada de Lambda (Terraform fallaría si se intenta) — Lambda ya la inyecta sola con
# la región de la función, y el default de Settings ("us-east-1") ya coincide.
locals {
  # API_BASE_URL: NO se referencia aws_lambda_function_url.api acá — crearía un ciclo
  # (la función necesitaría su propia URL antes de poder crearse). Se queda con el
  # default de Settings ("http://localhost:8000") hasta el Chunk 5, cuando haya dominio
  # propio vía CloudFront — ahí sí es un valor conocido de antemano, sin ciclo. Solo
  # afecta el redirect_uri de Google OAuth, que tampoco está configurado todavía para
  # esta URL en Google Cloud Console — no bloquea nada de lo que se prueba hoy.
  lambda_env = merge(var.secrets, {
    ALGORITHM                   = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = "30"
    REFRESH_TOKEN_EXPIRE_DAYS   = "7"
    ALLOWED_ORIGINS             = var.allowed_origins
    FRONTEND_URL                = var.frontend_url
    JOBS_TABLE_NAME             = var.jobs_table_name
    S3_BUCKET_RENTA_DOCS        = var.s3_bucket_renta_docs
    SQS_QUEUE_URL               = var.sqs_queue_url
  })
}

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

  environment {
    variables = local.lambda_env
  }

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

# Desde octubre 2025, AWS exige TAMBIÉN lambda:InvokeFunction (no solo InvokeFunctionUrl)
# para que un Function URL con auth NONE sea invocable públicamente — sin este segundo
# statement, sigue dando 403 aunque el de arriba esté bien (confirmado con curl real,
# doc oficial: https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html).
#
# El provider de Terraform TODAVÍA no soporta esto de forma nativa — el argumento
# `invoked_via_function_url` en aws_lambda_permission es un feature request abierto sin
# versión publicada (https://github.com/hashicorp/terraform-provider-aws/issues/44829).
# Mientras tanto, se agrega vía AWS CLI dentro de un null_resource — sigue siendo
# Terraform quien lo declara y aplica (terraform apply, trackeado en state), no un
# comando suelto fuera de código. Reemplazar por el argumento nativo en cuanto el
# provider lo publique.
resource "null_resource" "public_function_url_invoke_permission" {
  triggers = {
    function_name = aws_lambda_function.api.function_name
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws lambda add-permission \
        --function-name ${aws_lambda_function.api.function_name} \
        --statement-id AllowPublicFunctionUrlInvokeFunction \
        --action lambda:InvokeFunction \
        --principal '*' \
        --invoked-via-function-url \
        --region us-east-1 \
        || true
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      aws lambda remove-permission \
        --function-name ${self.triggers.function_name} \
        --statement-id AllowPublicFunctionUrlInvokeFunction \
        --region us-east-1 \
        || true
    EOT
  }

  depends_on = [aws_lambda_function.api]
}
