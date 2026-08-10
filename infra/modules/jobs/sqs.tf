# Dispara el Lambda worker (Chunk 4) para procesar jobs largos (OCR/exógenas) de forma
# desacoplada — reemplaza el ThreadPoolExecutor in-process.
resource "aws_sqs_queue" "jobs_dlq" {
  name = "taxops-jobs-dlq-prod" # dead-letter — jobs que fallan 3 veces caen acá para inspección manual
}

resource "aws_sqs_queue" "jobs" {
  name                       = "taxops-jobs-prod"
  visibility_timeout_seconds = 900 # >= timeout del Lambda worker (14 min, Chunk 4)

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })
}
