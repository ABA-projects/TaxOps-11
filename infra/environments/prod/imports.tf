# Bloques import{} — vacío tras la migración a la cuenta 562548008942 (2026-09-21).
#
# En la cuenta vieja (786567028012) estos import adoptaban los CloudWatch Log
# Groups que AWS auto-creaba antes de declararlos en Terraform. En la cuenta
# NUEVA esos log groups NO existen todavía, así que un import{} fallaría con
# "resource not found". Terraform los crea normalmente en el primer apply
# (module.lambda_api.aws_cloudwatch_log_group.{api,worker}).
#
# Si en el futuro se re-adopta algún recurso preexistente, agregar el import{}
# aquí (solo se permiten en el root module).
