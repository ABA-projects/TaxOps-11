# Identity provider OIDC de GitHub Actions — permite que los workflows asuman un rol
# IAM temporal sin llaves de larga duración guardadas como secret en GitHub.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # Dos thumbprints (CA antigua y actual) — GitHub rota su cadena de certificados de vez en
  # cuando, tener ambos evita que el provider quede inválido cuando eso pase.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  oidc_sub   = "token.actions.githubusercontent.com:sub"
  oidc_aud   = "token.actions.githubusercontent.com:aud"
}

# Tres roles en vez de uno, cada uno con el trust más estrecho que su workflow permite.
# Antes un solo rol AdministratorAccess servía a los 4 workflows, así que cualquier PR
# (terraform-plan corre en pull_request) obtenía admin de la cuenta.
#
#   plan      ← sub "repo:X:pull_request"             → solo lectura + lock del state
#   terraform ← sub "repo:X:environment:production"   → PowerUser + IAM acotado a taxops-*
#   deploy    ← sub "repo:X:ref:refs/heads/main"      → ECR push + UpdateFunctionCode + S3 config
#
# El sub de un job que declara `environment:` es "environment:<nombre>", no la rama; por eso el
# apply (gate manual) queda amarrado al environment y no a main.
locals {
  trust = {
    plan      = "repo:${var.github_repo}:pull_request"
    terraform = "repo:${var.github_repo}:environment:production"
    deploy    = "repo:${var.github_repo}:ref:refs/heads/main"
  }
}

data "aws_iam_policy_document" "assume" {
  for_each = local.trust

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = local.oidc_aud
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = local.oidc_sub
      values   = [each.value]
    }
  }
}

# ── plan: terraform-plan.yml en cada PR ──────────────────────────────────────────────────
resource "aws_iam_role" "github_actions_plan" {
  name               = "taxops-github-actions-plan"
  assume_role_policy = data.aws_iam_policy_document.assume["plan"].json
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.github_actions_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# `terraform plan` con use_lockfile escribe/borra <key>.tflock en el bucket del state.
data "aws_iam_policy_document" "state_lock" {
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${var.tfstate_bucket}/${var.tfstate_key}.tflock"]
  }
  # El módulo secrets administra SSM SecureString; el refresh los lee descifrados
  # (GetParameter WithDecryption) y ReadOnlyAccess no trae kms:Decrypt. Se limita a la llave
  # administrada de SSM y solo a través del servicio SSM: no sirve para descifrar otra cosa.
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "plan_state_lock" {
  name   = "tfstate-lock"
  role   = aws_iam_role.github_actions_plan.id
  policy = data.aws_iam_policy_document.state_lock.json
}

# ── terraform: terraform-apply.yml, solo tras aprobación manual del environment ──────────
resource "aws_iam_role" "github_actions_terraform" {
  name               = "taxops-github-actions-terraform"
  assume_role_policy = data.aws_iam_policy_document.assume["terraform"].json
}

# PowerUserAccess = todo menos IAM/Organizations/Account. Lo que Terraform necesita de IAM
# (roles de Lambda, Amplify, scheduler, y estos mismos) se concede aparte, acotado por nombre.
resource "aws_iam_role_policy_attachment" "terraform_poweruser" {
  role       = aws_iam_role.github_actions_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

data "aws_iam_policy_document" "terraform_iam" {
  # Lectura de IAM sin restricción: plan/refresh consultan roles y policies por ARN.
  statement {
    effect    = "Allow"
    actions   = ["iam:Get*", "iam:List*"]
    resources = ["*"]
  }
  # Escritura solo sobre lo que este repo administra. Todos los roles del proyecto se llaman
  # taxops-*; las policies son inline (van con el rol), así que no hace falta policy/*.
  statement {
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:UpdateRole", "iam:UpdateRoleDescription",
      "iam:UpdateAssumeRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy",
      "iam:PassRole",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/taxops-*"]
  }
  # El provider OIDC (este módulo) también es un recurso IAM.
  statement {
    effect = "Allow"
    actions = [
      "iam:CreateOpenIDConnectProvider", "iam:DeleteOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint", "iam:TagOpenIDConnectProvider",
      "iam:AddClientIDToOpenIDConnectProvider", "iam:RemoveClientIDFromOpenIDConnectProvider",
    ]
    resources = ["arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"]
  }
  # Servicios que crean su service-linked role al primer uso (Amplify, Lambda, Scheduler).
  statement {
    effect    = "Allow"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/aws-service-role/*"]
  }
}

resource "aws_iam_role_policy" "terraform_iam" {
  name   = "iam-scoped-to-taxops"
  role   = aws_iam_role.github_actions_terraform.id
  policy = data.aws_iam_policy_document.terraform_iam.json
}

# ── deploy: deploy-lambda.yml y agentes-contables.yml en main ────────────────────────────
resource "aws_iam_role" "github_actions_deploy" {
  name               = "taxops-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.assume["deploy"].json
}

data "aws_iam_policy_document" "deploy" {
  # docker login a ECR: GetAuthorizationToken no admite recurso.
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage",
      "ecr:DescribeImages",
    ]
    resources = ["arn:aws:ecr:${var.region}:${local.account_id}:repository/${var.ecr_repository}"]
  }
  # update-function-code + wait function-updated + get-function-url-config (deploy-lambda.yml).
  statement {
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode", "lambda:GetFunction", "lambda:GetFunctionConfiguration",
      "lambda:GetFunctionUrlConfig",
    ]
    resources = [for f in var.lambda_functions : "arn:aws:lambda:${var.region}:${local.account_id}:function:${f}"]
  }
  # vencimientos-tributarios/publish.py lee y reescribe config/calendario_2026.json.
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::${var.job_artifacts_bucket}/config/*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy-ecr-lambda-s3config"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
