# Guía: madurez de CI/CD y GitOps para la infraestructura de TaxOps

**Contexto:** esta guía es sobre el pipeline de **infraestructura** (Terraform), separado del CI/CD de la **aplicación** (`ci.yml`, `deploy-cloud-run.yml` → después `deploy-aws-lambda.yml`, ver Chunk 7 del plan de migración). Infra y app se despliegan por caminos distintos a propósito: cambiar un endpoint de la API no debería poder tocar una tabla de DynamoDB, y viceversa.

## Dónde estás hoy (Etapa 1 — ya implementada)

Desde el Task 1.4/1.4b del plan de migración:

| Evento | Qué corre | Dónde |
|---|---|---|
| Abrís un PR que toca `infra/**` | `terraform-plan.yml`: fmt, validate, plan → el resultado queda en el Job Summary del PR | GitHub Actions |
| Se mergea a `main` | `terraform-apply.yml`: **se pausa esperando aprobación** (environment `production`), luego aplica | GitHub Actions |

Autenticación vía **OIDC** (rol `taxops-github-actions-terraform`), sin llaves de AWS guardadas en GitHub. **Regla de oro**: de aquí en adelante, ningún `terraform apply` manual desde tu laptop salvo emergencia — tu `AWS_PROFILE=taxops-admin` local queda para `plan`/lectura/debug.

**Gate de aprobación manual (2026-08-07, adelantado desde el backlog de abajo):** el job de apply usa el environment `production` de GitHub con required reviewers = tu usuario, y "Allow administrators to bypass configured protection rules" activado — así ningún apply corre sin un click tuyo de por medio, pero ese click lo das vos mismo sin depender de nadie más. Se adelantó porque configurarlo cuesta $0 y el beneficio es inmediato.

Esto ya es "GitOps" en el sentido que importa para un equipo de 1: **el estado deseado vive en Git, y el pipeline es el único camino para aplicarlo** — no hay un humano corriendo `apply` a mano contra producción.

## Qué falta para más madurez (no implementar todavía — por trigger, no por calendario)

Mismo criterio que el backlog de seguridad de `docs/AWS-ACCOUNT-SETUP-GUIDE.md` sección 6.1: cada mejora tiene un disparador concreto.

| Mejora | Qué resuelve | Activar cuando... |
|---|---|---|
| ~~**Aprobación manual antes de apply**~~ | ✅ **Ya implementado** (2026-08-07) — environment `production` + required reviewers, ver nota arriba. | — |
| **Rol de CI acotado (no `AdministratorAccess`)** | El rol `taxops-github-actions-terraform` hoy tiene admin total — cualquier bug en un `.tf` mal escrito podría tocar cualquier cosa de la cuenta. | Antes de invitar a alguien más al repo, o cuando el plan de migración esté 100% ejecutado y se conozca el set final de servicios a acotar (Lambda, SQS, DynamoDB, S3, CloudFront, Route53, ECR, SSM). |
| **Detección de drift** (workflow con `schedule: cron` que corre `terraform plan` semanal y alerta si hay diffs) | Hoy si alguien cambia algo a mano en la consola AWS, nadie se entera hasta el próximo `apply`. | En cuanto termine la migración inicial y la infra esté estable — no tiene sentido antes, todavía va a haber diffs esperados mientras se construye. |
| **Policy-as-code** (`tfsec`/`checkov` como check obligatorio en `terraform-plan.yml`) | Detecta buckets públicos, IAM demasiado permisivo, etc. antes del merge. | Gratis agregarlo, bajo costo de mantenimiento — se puede sumar apenas Chunk 1 esté aplicado, no hay que esperar un trigger de negocio para este. |
| **Multi-ambiente** (`infra/environments/staging/` además de `prod/`) | Hoy solo existe `prod` — cualquier cambio de Terraform se prueba directo contra producción. | Se cree una segunda cuenta AWS (mismo trigger que Config/SCPs en la guía de cuenta) — ahí `staging` vive en esa cuenta separada, no como un workspace dentro de la misma cuenta de prod. |
| **Atlantis / HCP Terraform** (bot de PR automation dedicado, o Terraform Cloud gestionado) | Mejor UX de revisión de planes, locking más robusto, políticas Sentinel. | Solo si GitHub Actions se queda corto de verdad — para un equipo de 1-3 personas, GitHub Actions + OIDC (lo que ya tienes) suele ser suficiente y es $0 extra. No migres a esto "porque es lo que usan las empresas grandes" sin una razón concreta. |

## Por qué no se implementa todo esto ahora

Mismo principio que el resto del proyecto: cada pieza de infraestructura para procesos (no solo para la app) tiene que pagar su costo en complejidad. Un solo desarrollador con `terraform-plan.yml` + `terraform-apply.yml` + regla de "todo por PR" ya elimina el riesgo más común (aplicar algo no revisado, o perder de dónde salió un cambio) sin la sobrecarga operativa de mantener un bot de Atlantis o pagar Terraform Cloud.

## Cuándo revisitar esta guía

Cada vez que se cumpla uno de los triggers de la tabla — no en una fecha fija. Los mismos eventos que dispararían revisar `AWS-ACCOUNT-SETUP-GUIDE.md` sección 6.1 (segunda cuenta AWS, primer colaborador en el repo, primer cliente pagando) son los que disparan esta tabla también — tiene sentido revisarlas juntas.

---

*Ver también: `docs/superpowers/plans/2026-08-05-taxops11-aws-migration.md` (Task 1.4/1.4b — implementación del pipeline actual), `docs/AWS-ACCOUNT-SETUP-GUIDE.md` (backlog de seguridad con el mismo criterio de triggers).*
