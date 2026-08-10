output "function_url" {
  value       = aws_lambda_function_url.api.function_url
  description = "URL pública de la API — para probar antes de apuntar CloudFront/DNS (Chunk 5)"
}

output "api_function_name" {
  value = aws_lambda_function.api.function_name
}

output "worker_function_name" {
  value = aws_lambda_function.worker.function_name
}
