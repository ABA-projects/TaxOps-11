# direnv: aislamiento del profile de AWS de este proyecto

**Problema que resuelve:** Jaime usa AWS también para trabajo (British Airways/Nexus). Sin aislamiento, es fácil terminar con `AWS_PROFILE` apuntando a la cuenta equivocada en la terminal equivocada — desde algo inofensivo (`aws s3 ls` contra la cuenta que no era) hasta algo serio (`terraform apply`/`terraform destroy` contra la cuenta de trabajo por accidente, o al revés).

**Solución:** [direnv](https://direnv.net/) activa variables de entorno **automáticamente al entrar a una carpeta específica** y las desactiva al salir. El profile de AWS de TaxOps solo existe mientras estás dentro de `TaxOps-11/` — en cualquier otra terminal, carpeta o proyecto, no interfiere con nada.

## Qué se configuró

| Archivo | Contenido | ¿Se commitea? |
|---|---|---|
| `~/.zshrc` | `eval "$(direnv hook zsh)"` | N/A — es de tu máquina, no del repo |
| `TaxOps-11/.envrc` | `export AWS_PROFILE=taxops-admin` | **No** — está en `.gitignore` |
| `~/.aws/config` | Profile `[profile taxops-admin]` (SSO, cuenta `786567028012`, región `us-east-1`) | N/A — es de tu máquina |

El `.envrc` no se commitea a propósito: es configuración local de cada desarrollador, no del proyecto. Si en el futuro alguien más clona el repo, crea su propio `.envrc` con su propio profile — por eso también existe (o debería existir) un `.envrc.example` sin valores reales, ver sección "Para otro desarrollador" abajo.

## Cómo funciona en el día a día

```bash
cd ~/otra-carpeta-cualquiera
echo $AWS_PROFILE          # vacío, o el que tengas seteado para trabajo

cd .../TaxOps-11
# direnv: loading .../TaxOps-11/.envrc
# direnv: export +AWS_PROFILE
echo $AWS_PROFILE          # taxops-admin

cd ..
# direnv: unloading
echo $AWS_PROFILE          # vuelve a estar vacío / al de trabajo
```

No hace falta hacer nada manual para activarlo o desactivarlo — es automático por el simple hecho de estar parado en esa carpeta (o cualquier subcarpeta, incluyendo `infra/environments/prod/` donde corre Terraform).

## Primera vez / después de editar `.envrc`

Por seguridad, direnv **nunca ejecuta un `.envrc` nuevo o modificado sin autorización explícita** — así evita que un `.envrc` malicioso (ej. en un repo clonado de alguien más) ejecute código solo por hacer `cd`. Vas a ver:

```
direnv: error /path/to/TaxOps-11/.envrc is blocked. Run `direnv allow` to approve its content
```

Se resuelve una sola vez por cambio:

```bash
direnv allow
```

Si en algún momento editas el `.envrc` (agregas otra variable, por ejemplo), va a volver a pedir `direnv allow` — es intencional, no es un bug.

## Verificar que está bien configurado

```bash
cd .../TaxOps-11
echo $AWS_PROFILE                  # → taxops-admin
aws sts get-caller-identity        # → Account: 786567028012, role AdministratorAccess/jaime.admin
```

## Para Terraform

Con `AWS_PROFILE` ya activo por `.envrc`, el provider de Terraform no necesita el profile hardcodeado — igual se deja explícito en el código por claridad y para que funcione también en CI (donde no hay direnv, se usa OIDC — ver `docs/CI-CD-GITOPS-GUIDE.md`):

```hcl
provider "aws" {
  region  = var.aws_region
  profile = "taxops-admin"
}
```

## Para otro desarrollador que clone el repo

1. Instalar direnv: `brew install direnv` + agregar el hook a su shell (`eval "$(direnv hook zsh)"` o el equivalente en bash/fish).
2. Crear su propio `AWS_PROFILE` local (`aws configure sso`, ver `docs/AWS-ACCOUNT-SETUP-GUIDE.md`).
3. Copiar `TaxOps-11/.envrc` (o crearlo) con el nombre de **su** profile.
4. `direnv allow`.

## Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| `echo $AWS_PROFILE` sale vacío dentro de la carpeta | Falta el hook en el shell, o no se abrió una terminal nueva después de agregarlo | `source ~/.zshrc`, o abrir una terminal nueva |
| `.envrc is blocked` | Primera vez, o el archivo cambió | `direnv allow` |
| `AWS_PROFILE` sigue activo fuera de la carpeta | No debería pasar — si pasa, revisar que no haya un `export AWS_PROFILE=...` suelto en `~/.zshrc` (no debería haberlo, ver tabla de arriba) | `grep AWS_PROFILE ~/.zshrc` — debe salir vacío |
| `aws sts get-caller-identity` da error de sesión expirada | Las credenciales SSO expiran (normalmente 8-12h) | `aws sso login --profile taxops-admin` |
