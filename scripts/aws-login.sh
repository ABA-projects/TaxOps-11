#!/usr/bin/env bash
# Verifica la sesión SSO del profile taxops-admin y la renueva si expiró.
# Uso: ./scripts/aws-login.sh
set -euo pipefail

PROFILE="taxops-admin"

echo "→ Verificando sesión AWS SSO (profile: ${PROFILE})..."

if aws sts get-caller-identity --profile "${PROFILE}" >/dev/null 2>&1; then
  echo "✅ Sesión activa:"
  aws sts get-caller-identity --profile "${PROFILE}" --output table
else
  echo "⏳ Sesión expirada o no iniciada — abriendo el navegador para reautorizar..."
  aws sso login --profile "${PROFILE}"
  echo "✅ Login completado:"
  aws sts get-caller-identity --profile "${PROFILE}" --output table
fi
