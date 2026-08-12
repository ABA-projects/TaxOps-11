resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/taxops-worker-prod"
  retention_in_days = 14
}

# Lambda worker — consume SQS, corre OCR/clasificación (jobs largos). Misma imagen que la
# API, entrypoint distinto (worker_handler.handler en vez de main.handler).
resource "aws_lambda_function" "worker" {
  function_name = "taxops-worker-prod"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repo_url}:${var.image_tag}"
  image_config {
    command = ["worker_handler.handler"]
  }
  memory_size = 2048 # OCR con Tesseract — igual que los 2Gi que ya usaba en Cloud Run
  timeout     = 840  # 14 min, deja margen bajo el máximo de 15 min de Lambda

  architectures = ["x86_64"] # mismo motivo que aws_lambda_function.api — binarios de Tesseract son x86_64 (Dockerfile-lambda)

  environment {
    variables = local.lambda_env
  }

  lifecycle {
    ignore_changes = [image_uri]
  }

  depends_on = [aws_cloudwatch_log_group.worker]
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1 # un job OCR a la vez por invocación, evita competir por memoria
}
