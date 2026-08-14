# Amplify Hosting reemplaza Vercel (Chunk 6) — soporte SSR nativo de Next.js 15 (App
# Router) vía platform WEB_COMPUTE. Vercel NO se apaga en este chunk (Task 6.1 del plan):
# corre en paralelo hasta que Amplify esté probado y el Chunk 8 confirme el cutover — es
# el rollback más simple si algo falla.

# IAM es eventualmente consistente entre regiones/servicios — un apply real falló con
# "The compute role provided cannot be assumed by Amplify" porque Amplify intentó validar
# el rol ~1s después de creado, antes de que la propagación global terminara. Se espera
# explícito en vez de reintentar a ciegas.
resource "time_sleep" "wait_for_iam_propagation" {
  depends_on = [aws_iam_role.amplify_ssr, aws_iam_role_policy.amplify_ssr_logs]

  create_duration = "15s"
}

resource "aws_amplify_app" "web" {
  name         = "taxops-web-prod"
  repository   = var.github_repo_url
  access_token = var.github_access_token
  platform     = "WEB_COMPUTE"
  # Dos argumentos de rol distintos en este recurso — iam_service_role_arn (general) y
  # compute_role_arn (específico del compute SSR de WEB_COMPUTE). El build real falló con
  # "Unable to assume specified IAM Role" sin ninguno de los dos seteados; se apunta ambos
  # al mismo rol (aws_iam_role.amplify_ssr) para cubrir los dos casos sin adivinar cuál
  # exactamente lo pedía.
  iam_service_role_arn = aws_iam_role.amplify_ssr.arn
  compute_role_arn     = aws_iam_role.amplify_ssr.arn

  depends_on = [time_sleep.wait_for_iam_propagation]

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
    # Necesaria pese a que build_spec ya declara appRoot: taxops-web — el paso de
    # detección de framework corre ANTES del build_spec custom y necesita esto para
    # encontrar el package.json (confirmado con un build real: "Cannot read 'next'
    # version in package.json" sin esta env var).
    AMPLIFY_MONOREPO_APP_ROOT = "taxops-web"
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

# Dominio propio para el frontend (app.taxopsapp.com) — mismo patrón que module.cdn para
# la API: Cloudflare como DNS, certificado gestionado por Amplify (no ACM directo, a
# diferencia de CloudFront).
data "cloudflare_zones" "main" {
  name = var.domain_name
}

locals {
  zone_id = data.cloudflare_zones.main.result[0].id
}

# wait_for_verification = false a propósito — este recurso, a diferencia de
# aws_acm_certificate/aws_acm_certificate_validation (2 recursos separados en module.cdn),
# bundlea la creación Y la espera de verificación en uno solo. Con wait_for_verification
# = true, Terraform esperaría a que el dominio verifique ANTES de crear los registros DNS
# de abajo (que son justo lo que hace falta para que verifique) — deadlock. La
# verificación real ocurre async en AWS después del apply, no bloquea nada acá.
resource "aws_amplify_domain_association" "app" {
  app_id                = aws_amplify_app.web.id
  domain_name           = var.domain_name
  wait_for_verification = false

  sub_domain {
    branch_name = aws_amplify_branch.main.branch_name
    prefix      = var.app_subdomain
  }
}

# certificate_verification_dns_record viene como "name CNAME value" en un solo string.
resource "cloudflare_dns_record" "app_cert_validation" {
  zone_id = local.zone_id
  name    = trimsuffix(split(" CNAME ", aws_amplify_domain_association.app.certificate_verification_dns_record)[0], ".")
  type    = "CNAME"
  content = trimsuffix(split(" CNAME ", aws_amplify_domain_association.app.certificate_verification_dns_record)[1], ".")
  ttl     = 300
  proxied = false # obligatorio DNS-only — Amplify necesita leer este valor directo para renovar el cert automáticamente
}

# sub_domain es un set (no list) — no se puede indexar con [0], se extrae con un for.
locals {
  app_sub_domain_dns_record = [for sd in aws_amplify_domain_association.app.sub_domain : sd.dns_record if sd.prefix == var.app_subdomain][0]
}

# sub_domain[*].dns_record es directo el target (ej. "xxxx.cloudfront.net"), no un string
# "name CNAME value" como el de arriba — confirmado contra la doc oficial de AWS para
# Cloudflare (to-add-a-custom-domain-managed-by-cloudflare.html).
resource "cloudflare_dns_record" "app" {
  zone_id = local.zone_id
  name    = "${var.app_subdomain}.${var.domain_name}"
  type    = "CNAME"
  content = local.app_sub_domain_dns_record
  ttl     = 300
  proxied = false # ídem — mantener DNS-only también para el registro final, no solo el de validación (mismo motivo)
}
