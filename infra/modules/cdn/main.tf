# CloudFront delante de la Function URL de Lambda + dominio propio vía Cloudflare (DNS,
# no proxy — ver nota en cloudflare_dns_record.api más abajo). Reemplaza el diseño original
# del plan (Route53 + hosted zone, $6/año) — el dominio se registró en Cloudflare, que da
# DNS gratis, así que no hace falta un hosted zone de Route53 en absoluto.
#
# ACM para CloudFront SIEMPRE debe vivir en us-east-1 — la región por defecto de todo el
# proyecto (ver infra/environments/prod/variables.tf) ya es us-east-1, así que no hace
# falta un provider alias aparte, a diferencia del snippet original del plan.

locals {
  api_fqdn        = "${var.api_subdomain}.${var.domain_name}"
  lambda_url_host = trimsuffix(replace(var.lambda_function_url, "https://", ""), "/")
}

# cloudflare_zone (singular) no expone una forma clara de filtrar por nombre de dominio en
# el provider v5 (rewrite completo, ver CHANGELOG) — cloudflare_zones (plural) sí, vía
# el argumento "name" a nivel de filtro.
data "cloudflare_zones" "main" {
  name = var.domain_name
}

locals {
  zone_id = data.cloudflare_zones.main.result[0].id
}

resource "aws_acm_certificate" "api" {
  domain_name       = local.api_fqdn
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Un registro CNAME por cada opción de validación que pida ACM (normalmente 1 — el
# for_each cubre el caso de más de un SAN sin tener que tocar esto a mano). ACM entrega
# los nombres/valores con un "." final (formato DNS estándar); Cloudflare no lo quiere.
resource "cloudflare_dns_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => dvo
  }

  zone_id = local.zone_id
  name    = trimsuffix(each.value.resource_record_name, ".")
  type    = each.value.resource_record_type
  content = trimsuffix(each.value.resource_record_value, ".")
  ttl     = 300
  proxied = false # DNS-only — Cloudflare no debe proxyear un registro de validación de ACM
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn = aws_acm_certificate.api.arn
  # No se puede leer esto de cloudflare_dns_record (el provider v5 no expone un atributo
  # tipo "hostname"/fqdn calculado) — se toma directo de lo que pidió ACM.
  validation_record_fqdns = [for dvo in aws_acm_certificate.api.domain_validation_options : dvo.resource_record_name]

  depends_on = [cloudflare_dns_record.acm_validation]
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled" # API dinámica — no cachear por defecto
}

# Managed-CachingDisabled NO reenvía el header Authorization al origin en GET/HEAD (sí lo
# hacía de rebote en POST/PUT/PATCH/DELETE, por eso /uploads/presign y /exogenas/process
# funcionaban pero GET /exogenas/jobs/{id} devolvía 401 "Not authenticated" — confirmado
# reproduciendo el request directo con curl, ver docs/superpowers/plans/2026-08-18-...).
# Managed-AllViewer reenvía todos los headers/cookies/querystring al origin sin afectar
# cacheo (eso lo sigue controlando cache_policy_id, arriba).
data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

resource "aws_cloudfront_distribution" "api" {
  enabled     = true
  aliases     = [local.api_fqdn]
  price_class = "PriceClass_100" # Solo NA+EU (el tráfico real es Colombia) — el nivel más barato, no afecta latencia real

  origin {
    domain_name = local.lambda_url_host
    origin_id   = "lambda-api"
    custom_origin_config {
      origin_protocol_policy = "https-only"
      http_port              = 80
      https_port             = 443
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id         = "lambda-api"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.api.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}

# proxied = false a propósito — CloudFront ya es el CDN y termina TLS con el cert de ACM;
# si Cloudflare también proxyea (nube naranja) quedarían dos CDNs superpuestos compitiendo
# por cache/TLS sobre el mismo hostname, sin ningún beneficio real.
resource "cloudflare_dns_record" "api" {
  zone_id = local.zone_id
  name    = local.api_fqdn
  type    = "CNAME"
  content = aws_cloudfront_distribution.api.domain_name
  ttl     = 300
  proxied = false
}
