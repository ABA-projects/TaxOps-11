# Guía: Crear y asegurar la cuenta AWS para TaxOps

**Contexto:** cuenta nueva, single-account (no Control Tower / landing zone multi-cuenta — es overkill y tiene costo para un solo producto en etapa de validación). Lo que sigue es el baseline de seguridad/resiliencia/productividad que AWS recomienda incluso para una cuenta sola, sin la complejidad de una organización enterprise.

**Costo total de este setup: ~$0/mes** (todo lo de abajo es gratis o centavos). El único costo fijo de todo el proyecto sigue siendo la hosted zone de Route53 (~$0.50/mes, ver plan de migración).

---

## 1. Crear la cuenta root

- [ ] **Email dedicado**: no uses tu email personal directo. Usa un alias tipo `jaime.henao+aws-root@gmail.com` (Gmail ignora todo lo que va después de `+`, así que te sigue llegando al mismo buzón pero es una dirección única e identificable — útil para filtrar y para que nadie más pueda "adivinar" el email root).
- [ ] **Contraseña**: generada por un gestor de contraseñas (1Password, Bitwarden), 20+ caracteres, guardada ahí — no la escribas en ningún `.env` ni la repitas en otro sitio.
- [ ] **Tarjeta de pago**: AWS la pide aunque uses solo capa gratuita. Es normal.
- [ ] **Plan de soporte**: elegir **Basic (gratis)**. No pagues Developer/Business support todavía — no lo necesitas hasta tener incidentes en producción con usuarios reales.

## 2. Asegurar la cuenta root — hacerlo ANTES de crear ningún recurso

- [ ] **MFA en el usuario root**: obligatorio, sin excepción. Usa una app (Google Authenticator, Authy, o el TOTP de tu gestor de contraseñas) — un hardware key (YubiKey) es el estándar más alto si en algún momento quieres subir el nivel de seguridad, pero TOTP en app está bien para empezar.
- [ ] **Nunca generar Access Keys para el usuario root.** El root no debería usarse casi nunca después de este setup inicial — solo para tareas que *exigen* root (cerrar la cuenta, cambiar el plan de soporte, algunas acciones de billing). Todo lo demás pasa por Identity Center (paso 4).
- [ ] **Contactos alternativos de la cuenta**: en Billing → Account, configura contacto de *Billing*, *Operations* y *Security* (pueden ser el mismo email tuyo) — así AWS te avisa directo si detecta algo raro, sin depender de que revises la consola.

## 3. Billing y control de costos — antes de crear infraestructura

- [ ] **AWS Budgets**: crear 2-3 budgets con alertas por email:
  - $5/mes → alerta al 80% y 100% (tu señal de "algo no está en free tier")
  - $20/mes → alerta al 100% (techo de "para, revisa ya")
  - Un budget de *forecast* (proyección), no solo de gasto real — avisa antes de que pase.
- [ ] **Cost Anomaly Detection**: activarlo (gratis) — detecta patrones de gasto anómalos aunque estés debajo del budget.
- [ ] **Free Tier alerts**: en Billing Preferences, activar "Receive Free Tier Usage Alerts" — AWS te avisa por email cuando te acercas al límite de cualquier servicio en capa gratuita, antes de que te cobren.
- [ ] **Cost Explorer**: activarlo (gratis, tarda 24h en poblarse) — lo vas a usar para el reporte de costos del case study.

## 4. Identidad y accesos — IAM Identity Center, no usuarios IAM clásicos

Este es el punto donde más se desvían los setups "rápidos" y después duele:

- [ ] **Habilitar IAM Identity Center** (antes "AWS SSO") — gratis, y es lo que AWS recomienda incluso para una sola cuenta, en vez de crear IAM Users con contraseña.
- [ ] Crear tu usuario ahí (ej. `jaime.admin`), asignarle un **Permission Set** `AdministratorAccess` para uso diario en consola/CLI.
- [ ] Configurar `aws configure sso` en tu máquina local — te da credenciales temporales (expiran solas), nunca un Access Key plano guardado en disco.
- [ ] **Para GitHub Actions / Terraform (CI/CD)**: usar **OIDC federation** (GitHub ↔ IAM Role vía `sts:AssumeRoleWithWebIdentity`), no Access Keys de larga duración. Ya está contemplado así en el Chunk 7 del plan de migración (`deploy-aws-lambda.yml`).
- [ ] Principio de menor privilegio real: el rol que usa Terraform/GitHub Actions debería tener permisos acotados a los servicios del plan (Lambda, SQS, DynamoDB, S3, CloudFront, Route53, ECR, SSM, IAM para los roles que crea) — no `AdministratorAccess` en el pipeline. Se puede empezar amplio y acotar después de la primera migración exitosa (no bloquees el Chunk 0 por esto, pero queda anotado como deuda técnica a resolver en Fase 2).

## 5. AWS Organizations — crearla aunque tengas 1 sola cuenta

- [ ] Habilitar **AWS Organizations** (gratis) desde el día 1, aunque hoy solo tengas esta cuenta. Beneficio concreto: el día que quieras una cuenta "sandbox" separada para probar cosas sin miedo a romper prod, o una cuenta "prod" distinta de "dev", crearla dentro de la Organization toma minutos y ya viene con *consolidated billing* (una sola factura).
- [ ] No hace falta configurar Service Control Policies (SCPs) todavía — eso es para cuando haya más de una cuenta con reglas que aplicar entre ellas.

## 6. Guardrails de seguridad base (gratis o casi gratis)

- [ ] **CloudTrail**: activar un *trail* que loguee a un bucket S3 propio (el Event History de 90 días viene gratis por defecto, pero un trail persistente es lo que te permite auditar más atrás e investigar incidentes). Costo: prácticamente $0 al volumen de este proyecto (solo pagas por el storage S3, que es mínimo).
- [ ] **GuardDuty**: **pospuesto a propósito** (decisión 2026-08-06). Es gratis los primeros 30 días, pero después cobra por volumen de logs analizados (~$1-3/mes para este tamaño de cuenta) — es el único guardrail de este paso con costo recurrente real, así que se deja para cuando haya tráfico/ingresos que lo justifiquen, priorizando $0 mientras el producto sigue en validación. Se activa con un solo click cuando se decida (`GuardDuty → Enable GuardDuty`), no hay nada que preparar de antemano.
- [ ] **IAM Access Analyzer**: activar (gratis) — te avisa si algún recurso (bucket S3, rol IAM) queda accesible desde fuera de tu cuenta sin que lo hayas querido.
- [ ] **AWS Config** y **Security Hub**: tienen costo por regla/finding evaluado — déjalos para Fase 2 cuando el presupuesto lo justifique. No son gratis, no los actives todavía.
- [ ] **Fijar una sola región de trabajo** (`us-east-1`, la que ya usa el plan de migración) — evita "recursos fantasma" olvidados en regiones que nunca revisas. Bloquear otras regiones por SCP es un paso de Fase 2 (necesita Organizations con más de un uso real).

## 6.1. Backlog de guardrails pospuestos — activar por trigger, no por calendario

Nada de esto se activa "cuando haya presupuesto" (esa condición nunca se revisita sola). Cada guardrail pospuesto tiene un disparador concreto — cuando pase, se activa esa misma semana:

| Guardrail | Costo aprox. | Activar cuando... |
|---|---|---|
| **GuardDuty** | ~$1-3/mes | El primer usuario que no seas tú (o tu equipo interno) empiece a meter datos reales de un cliente — o apenas cierres el primer cliente pagando, lo que llegue primero. Un solo click (`GuardDuty → Enable`), sin preparación previa. |
| **AWS Config** | Por regla evaluada, variable | Se cree una **segunda cuenta AWS** real (sandbox o prod separada) — Config vale la pena cuando hay más de una cuenta que auditar consistentemente, no en single-account. |
| **Security Hub** | Por finding/check, variable | Junto con Config, o antes si un cliente empresarial pide evidencia formal de compliance/seguridad como parte de un contrato. |
| **SCPs multi-cuenta + bloqueo de regiones no usadas** | $0 (son policies) | Mismo trigger que Config: en cuanto exista una segunda cuenta dentro de la Organization. |
| **Reserved Capacity / Compute Savings Plans** | Ahorro, no costo extra | Cuando haya **3-6 meses de tráfico estable** en Fase 2 (post-migración) — comprometerse antes con patrones de uso todavía inciertos desperdicia el ahorro. |
| **Aurora Serverless v2 (reemplaza Neon)** | ~$45+/mes mínimo | Solo si el free tier de Neon se queda corto de verdad, o si un cliente exige que la DB esté 100% dentro de AWS por contrato. |

**Revisión de este backlog**: revisitarlo cada vez que se cumpla uno de los triggers de arriba (no en una fecha fija) — el disparador natural es "cerré un cliente" o "creé una segunda cuenta AWS", eventos que ya vas a estar registrando en el case study de portafolio.

## 7. Resiliencia y productividad básica

- [ ] **Tags obligatorios desde el primer recurso**: `Project`, `Environment`, `ManagedBy` — ya vienen por `default_tags` en el Terraform del plan de migración (Chunk 1), no hay que hacer nada extra aquí, solo no romper la convención.
- [ ] **Versioning en buckets S3 críticos** (state de Terraform, documentos de Renta) — ya contemplado en el plan.
- [ ] **Terraform state en S3 + lock en DynamoDB** — ya es el Chunk 0 del plan de migración, evita que dos aplicaciones de Terraform se pisen.
- [ ] **No usar Access Keys locales guardadas en `~/.aws/credentials`** — usa SSO (paso 4). Si en algún punto necesitas una excepción, usa `aws-vault` para no tener el secreto en texto plano en disco.

## 8. Errores comunes a evitar

- ❌ Usar la cuenta root para trabajo diario (login, CLI, lo que sea) — root es solo para las ~5 tareas que lo exigen.
- ❌ Generar Access Keys IAM de larga duración para CI/CD — usa OIDC.
- ❌ Crear recursos sin tags — a los 3 meses no vas a saber qué es qué ni qué se puede borrar.
- ❌ Ignorar las alertas de Free Tier cuando lleguen — son la señal más temprana de que algo se está saliendo del plan.
- ❌ Activar Config/Security Hub "porque son buenas prácticas" sin necesitarlos todavía — tienen costo recurrente que no se justifica en esta etapa.

## 9. Checklist ejecutable (orden real de ejecución)

1. Crear cuenta con email alias + contraseña de gestor.
2. MFA en root. Contactos alternativos configurados.
3. Budgets ($5 y $20) + Cost Anomaly Detection + Free Tier alerts + Cost Explorer.
4. Habilitar Organizations.
5. Habilitar IAM Identity Center, crear tu usuario admin, `aws configure sso` local.
6. CloudTrail (trail a S3) + IAM Access Analyzer. GuardDuty pospuesto (tiene costo recurrente ~$1-3/mes) hasta que haya tráfico/ingresos reales.
7. **Recién ahí** → arrancar el Chunk 0 del plan de migración (`infra/bootstrap`, backend de Terraform).

---

*Referencia: Well-Architected Framework, pilares de Seguridad y Excelencia Operacional — adaptado a un contexto de proyecto solo-founder en validación, no de landing zone enterprise. Se revisita con más controles (Config, Security Hub, SCPs multi-cuenta) en la Fase 2 del plan de migración, cuando haya tráfico/ingresos reales que lo justifiquen.*
