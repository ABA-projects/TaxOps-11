# Sin esto, el primer build real falla con "Unable to assume specified IAM Role" — el
# flujo de consola de Amplify ofrece crear este rol solo, pero vía API/Terraform hay que
# declararlo explícito (confirmado con un build real fallido, no adivinado).
#
# No existe una managed policy oficial "AmplifySSRServiceRolePolicy" (verificado con
# aws iam list-policies) — el compute de SSR (WEB_COMPUTE) solo necesita poder escribir
# sus propios logs, así que se define a mano con el alcance mínimo real.
resource "aws_iam_role" "amplify_ssr" {
  name = "taxops-amplify-ssr"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "amplify.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "amplify_ssr_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.amplify_ssr.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:*:*:log-group:/aws/amplify/*"
    }]
  })
}
