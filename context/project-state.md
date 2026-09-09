# Estado del proyecto — TaxOps-11

> Fuente de verdad **compartida** entre Claude Code y Kiro CLI.
> Neutral respecto a la herramienta. Ambos agentes leen y actualizan este archivo.
> Detalle técnico profundo (arquitectura de módulos, regex, schema) vive en `CLAUDE.md` — no se duplica aquí.

**Última actualización:** 2026-09-09 · **Actualizado por:** Kiro CLI (integrando memoria de Claude 2026-09-05, verificada contra git)

---

## Qué se está construyendo

TaxOps — plataforma contable SaaS para Colombia. Automatiza facturas electrónicas DIAN,
nómina CST 2026, calendario tributario, exógenas Formato 1003, renta (Formulario 210) y
un chatbot contable con IA. Multi-tenant.

Detalle de módulos y arquitectura: ver `README.md` (visión de producto) y `CLAUDE.md` (arquitectura de código).

## Arquitectura actual (resumen)

Producción en AWS (migrada desde GCP Cloud Run + Vercel):

- **API**: AWS Lambda (container) detrás de CloudFront — `api.taxopsapp.com`
- **Worker**: AWS Lambda disparado por SQS (OCR/exógenas, jobs largos)
- **Frontend**: AWS Amplify Hosting — `app.taxopsapp.com` (Next.js 15.3 SSR)
- **Estado de jobs**: DynamoDB + SQS · **Storage**: S3 · **Secretos**: SSM Parameter Store
- **DB**: PostgreSQL 16 en Neon (fuera de AWS a propósito — evita NAT Gateway)
- **DNS**: Cloudflare · **IaC**: Terraform (`infra/`, PR-gated) · **CI/CD**: GitHub Actions (OIDC)

## Estado por componente

| Componente | Estado | Nota |
|---|---|---|
| Facturas DIAN (extracción/validación/prorrateo) | ✅ Terminado | Pipeline `pipeline/` + `services/processor.py` |
| Nómina CST 2026 | ✅ Terminado | `services/nomina.py` |
| Exógenas Formato 1003 (12+ layouts) | ✅ Terminado, con bugs conocidos | `exogenas/extractor.py` — ver memory/known-issues.md |
| Renta (Formulario 210 + OCR) | ✅ Terminado | `services/renta/` |
| Calendario DIAN 2026 | ✅ Terminado | 31 eventos, migrado a S3 (sobrevive cold start) |
| Chatbot IA (multi-provider) | ✅ Terminado | Groq gpt-oss-120b/20b (los llama-3.x fueron deprecados) |
| Admin (usuarios/grupos/audit) | ✅ Terminado | |
| Auth JWT + Google OAuth | ✅ Terminado | |
| Migración GCP→AWS | ✅ Completa (chunks 0-8) | Verificada con archivos reales |
| Agentes contables on-demand | ✅ Terminado y verificado en prod | `agents/` — SQS→worker Lambda→Groq→web→publish→Postgres/S3. PRs #36–#44 |

**Rama/commit actual:** `main` @ `fc0401e` (PR #44 mergeado, nada en vuelo — verificado 2026-09-09).

## En progreso

- **Sin tarea de código a medias.** Claims falsos de la landing corregidos (2026-09-09, ver changelog).
- Pendiente aparte (no bloqueante): rediseño visual dirección C y `.dockerignore`. Ver `current-task.md`.

## Pendiente (backlog priorizado)

- Decomisión completa de Vercel (soak period de Amplify) — según README v1.1
- Rate limiting por organización
- Invitaciones por email (hoy el owner crea usuarios directamente)
- Permisos por grupo (bloqueo de rutas frontend según grupo)
- Script auto-update calendario DIAN (parsear PDF DIAN anual → JSON)
- Acotar rol OIDC de GitHub Actions (hoy `AdministratorAccess`, deuda técnica)

## Bloqueado / en espera

- Estrategia de negocio (constituir empresa con socio contador) — diferida a sesión dedicada.
  Ver memoria persistente de Claude `taxops11-business-strategy-deferred` y handoff en
  `docs/superpowers/SESSION-2026-08-23-handoff.md`.

## Próximos pasos recomendados

La tarea activa es **sacar los claims falsos de la landing** (ver `current-task.md`), empezando por
los testimonios inventados (riesgo legal/reputacional). Después, el backlog de arriba.
