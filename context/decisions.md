# Decisiones técnicas (ADR ligero) — TaxOps-11

> Registro **compartido** Claude ↔ Kiro. Una entrada por decisión relevante.
> Aditivo: se agregan entradas nuevas al inicio, nunca se borran las anteriores.
> Formato: decisión · fecha · contexto · alternativas · razón · impacto/consecuencias.

---

## ADR-000 — Coexistencia Claude Code + Kiro CLI sobre fuente de verdad compartida
- **Fecha:** 2026-09-09
- **Contexto:** El proyecto se desarrolla con Claude Code (`CLAUDE.md`, `.claude/commands/`, superpowers). Se quiere usar también Kiro CLI sin perder contexto ni romper Claude.
- **Alternativas consideradas:**
  1. Migrar todo el contexto de Claude a formato Kiro (destructivo — rechazado).
  2. Duplicar `CLAUDE.md` en `AGENTS.md` (dos fuentes divergentes — rechazado).
  3. **Coexistencia con fuente de verdad compartida** (elegida).
- **Razón:** Kiro `kiro_default` carga automáticamente `AGENTS.md`, `README.md` y `.kiro/steering/**/*.md`. Se aprovecha ese mecanismo nativo: `AGENTS.md` es un puente delgado hacia `CLAUDE.md` + `context/`, sin duplicar. `CLAUDE.md` queda intacto.
- **Impacto:** `CLAUDE.md` → instrucciones Claude. `AGENTS.md` → puente Kiro. `context/` → estado/decisiones/tareas/memoria compartidos. `.kiro/steering/` → reglas de Kiro. Ninguna duplicación de contenido.

---

## ADR: decisiones preexistentes del proyecto (registradas retroactivamente en el setup)

> Estas decisiones ya estaban tomadas y documentadas en `CLAUDE.md` / case study / handoff.
> Se listan aquí como índice compartido; el detalle vive en las fuentes citadas.

- **DB se queda en Neon (no RDS/Aurora)** — evita el costo de un NAT Gateway. Detalle: `docs/MIGRACION-AWS-CASE-STUDY.md`.
- **Secretos en SSM Parameter Store (SecureString), no Secrets Manager** — gratis vs. de pago.
- **Todo el stack AWS por Terraform, PR-gated** — ningún `terraform apply` manual salvo bootstrap. Detalle: `README.md` §Infra + `CLAUDE.md`.
- **CI/CD con OIDC (sin llaves AWS de larga duración).**
- **Chatbot: Groq `gpt-oss-120b`/`gpt-oss-20b`** — los `llama-3.x` fueron deprecados por Groq (handoff 2026-08-23, PR #30).
- **Calendario DIAN migrado a S3** — el archivo local no sobrevivía cold starts de Lambda (handoff 2026-08-23).
- **Premisa de costo: "todo gratis, siempre"** — cada recurso AWS nuevo se evalúa primero por capa gratuita.
