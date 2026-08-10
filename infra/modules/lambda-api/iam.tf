resource "aws_iam_role" "lambda_exec" {
  name = "taxops-lambda-exec-prod"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Política mínima: SQS (enviar/recibir), DynamoDB (jobs table), S3 (los 2 buckets), SSM (leer /taxops11/prod/*)
resource "aws_iam_role_policy" "app_access" {
  name = "taxops-app-access"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = var.sqs_queue_arn },
      { Effect = "Allow", Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"], Resource = var.dynamodb_table_arn },
      { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject"], Resource = [for arn in var.s3_bucket_arns : "${arn}/*"] },
      { Effect = "Allow", Action = ["ssm:GetParameter", "ssm:GetParametersByPath"], Resource = "arn:aws:ssm:*:*:parameter/taxops11/prod/*" }
    ]
  })
}
