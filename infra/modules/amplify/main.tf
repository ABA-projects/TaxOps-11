# Amplify Hosting reemplaza Vercel (Chunk 6) — soporte SSR nativo de Next.js 15 (App
# Router) vía platform WEB_COMPUTE. Vercel NO se apaga en este chunk (Task 6.1 del plan):
# corre en paralelo hasta que Amplify esté probado y el Chunk 8 confirme el cutover — es
# el rollback más simple si algo falla.

resource "aws_amplify_app" "web" {
  name         = "taxops-web-prod"
  repository   = var.github_repo_url
  access_token = var.github_access_token
  platform     = "WEB_COMPUTE"

  build_spec = <<-YAML
    version: 1
    applications:
      - appRoot: taxops-web
        frontend:
          phases:
            preBuild:
              commands: ["npm ci"]
            build:
              commands: ["npm run build"]
          artifacts:
            baseDirectory: .next
            files: ["**/*"]
          cache:
            paths: ["node_modules/**/*"]
  YAML

  environment_variables = {
    NEXT_PUBLIC_API_URL = var.api_domain
    INTERNAL_API_URL    = var.api_domain
  }

  lifecycle {
    ignore_changes = [access_token] # rotar el PAT no debe forzar un diff perpetuo — se re-aplica a mano si vence
  }
}

resource "aws_amplify_branch" "main" {
  app_id            = aws_amplify_app.web.id
  branch_name       = "main"
  enable_auto_build = true
  framework         = "Next.js - SSR"
  stage             = "PRODUCTION"
}

# Amplify crea el webhook de GitHub automáticamente al conectar el repo (usa el
# access_token de arriba una sola vez, en la creación) — no hace falta un
# aws_amplify_webhook aparte para auto-deploy en push a main.
