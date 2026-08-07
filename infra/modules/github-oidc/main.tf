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

resource "aws_iam_role" "github_actions_terraform" {
  name = "taxops-github-actions-terraform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        # Restringe a este repo específico — sin esto, cualquier repo de tu cuenta de GitHub
        # (o de cualquiera, si el provider quedara mal configurado) podría asumir el rol.
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })
}

# MVP: AdministratorAccess, igual que el usuario humano jaime.admin.
# Deuda técnica documentada (docs/CI-CD-GITOPS-GUIDE.md): acotar a los servicios exactos
# del plan antes de invitar a un segundo colaborador al repo.
resource "aws_iam_role_policy_attachment" "github_actions_admin" {
  role       = aws_iam_role.github_actions_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
