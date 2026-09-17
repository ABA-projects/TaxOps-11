# Estado del proyecto — TaxOps-11

> Fuente de verdad **compartida** entre Claude Code y Kiro CLI.
> Neutral respecto a la herramienta. Ambos agentes leen y actualizan este archivo.
> Detalle técnico profundo (arquitectura de módulos, regex, schema) vive en `CLAUDE.md` — no se duplica aquí.

**Última actualización:** 2026-09-16 · **Actualizado por:** Claude Code (verificado contra git y GitHub: 0 PRs abiertos)

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
| Agentes contables on-demand + cron | ✅ Terminado y verificado en prod | `agents/` — SQS→worker Lambda→Groq→web→publish→Postgres/S3. PRs #36–#44. Cron semanal reactivado solo para `dian-monitor` y `monitor-niif` (#51) |
| DIAN AttachedDocument (Fase 1) | ⚠️ Hecho, sin validar con XML reales | `pipeline/extractor.py` desenvuelve el contenedor (#50). Fixtures sintéticos; falta probar con 2–3 XML reales de la DIAN |
| Landing + sistema de diseño | ✅ Terminado | Landing editorial clara (#53) y tokens de la app en verde/neutros (#54). Calendario de la landing desde el JSON con ISR diario. Fuentes del canvas en `docs/design/landing/` |
| `.dockerignore` | ✅ Hecho | #47 — no excluye los archivos que el runtime necesita (config.yaml, autorretenedores.txt, calendario JSON, init.sql) |

**Rama/commit actual:** `main` @ `6264e23` (PR #54 mergeado, 0 PRs abiertos — verificado 2026-09-16).

## En progreso

- **Sin tarea de código a medias.** Ver `current-task.md` para el siguiente paso.

## Decisiones cerradas recientes

Ver `context/decisions.md`. Las dos más relevantes: **no se construye conector DIAN** (el cliente
entrega el paquete de facturas; posible integración futura con la solución privada de colegas) y
**el frontend sigue en Amplify** (no Docker/ECR por ahora).

## Pendiente (backlog priorizado)

**Riesgo / seguridad (primero)**
- Validar Fase 1 AttachedDocument con XML reales de la DIAN — depende de conseguir los archivos
- Acotar rol OIDC de GitHub Actions (hoy `AdministratorAccess`) a ECR + Lambda + Amplify + S3 + SSM
- Lambda Node.js 20 EOL (aviso AWS, deadline 2027-03-03): ubicar el origen (probablemente SSR de Amplify) y planear

**Producto**
- Formulario de contacto de la landing sin backend (hoy `mailto:`) → endpoint + SES
- Invitaciones por email (hoy el owner crea usuarios directamente)
- Permisos por grupo (los grupos tienen `modules[]` pero el frontend no bloquea rutas)
- Bugs conocidos del extractor de exógenas (6 casos listados en `CLAUDE.md`)
- Script auto-update calendario DIAN (parsear PDF DIAN anual → JSON) — urge antes de enero 2027

**Plataforma / higiene**
- Rate limiting por organización (sin throttling; Groq comparte 8000 TPM por cuenta)
- Frontend Fase C: pulido por página solo si #54 dejó contraste flojo (revisar `/facturas`, `/chatbot`); renombrar `brand.orange`→`brand.green`

**Diferido a propósito**
- Fase 2 DIAN/XML (exógenas/renta en XML) — el research la marca como dudosa

## Bloqueado / en espera

- Estrategia de negocio (constituir empresa con socio contador) — diferida a sesión dedicada.
  Ver memoria persistente de Claude `taxops11-business-strategy-deferred` y handoff en
  `docs/superpowers/SESSION-2026-08-23-handoff.md`.

## Próximos pasos recomendados

En orden: (1) acotar el rol OIDC — peor relación riesgo/esfuerzo y va por el pipeline de Terraform
que ya funciona; (2) contact form con SES; (3) validar Fase 1 apenas haya XML reales.
