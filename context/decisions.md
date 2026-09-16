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

## 2026-09-16 — No construir conector DIAN; el cliente entrega el paquete de facturas

**Decisión (Jaime):** se mantiene el flujo actual — el cliente/contador entrega XML/PDF y TaxOps los procesa. No se automatiza la obtención de facturas desde la DIAN.

**Por qué:** la investigación (Anexo 1.9 §7.14.1, instructivos de habilitación, Res. 165/2023) mostró que:
- La vía oficial (`GetXmlByDocumentKey` por SOAP) existe para el receptor, pero exige certificado X.509 de ECD ($83k–$195k COP/año) **y** habilitar "software propio" con set de pruebas **por cada NIT**. No hay perfil "solo receptor" ni "consulta por terceros". Inviable para una firma con N clientes.
- No hay método para listar recibidas por NIT/fecha; siempre hace falta el CUFE.
- El catálogo con token es scraping (robots.txt Disallow, sesión de 1 h). `searchqr` tiene Turnstile.
- Las alternativas legales y gratuitas (buzón de correo + Excel del catálogo) son trabajo real de producto sin ingresos que lo justifiquen hoy.

**Si se reabre:** empezar por buzón de correo (Gmail API) → AttachedDocument → Fase 1, con el Excel de "Documentos Recibidos" para conciliar. Pendiente de confirmar si el certificado gratuito de "Facturación Gratuita DIAN" es exportable (bajaría el costo de la vía SOAP a $0 para esos clientes).

## 2026-09-15 — Frontend se queda en Amplify; no Docker/ECR por ahora

**Decisión:** seguir con Amplify Hosting (SSR nativo). **Por qué:** ISR (calendario de la landing) no funciona en Lambda sin OpenNext o caché compartido; cold start de 1–3 s en la landing; costo equivalente (centavos); `output: standalone` ya deja el Dockerfile trivial si hace falta. **Reabrir si:** EOL de Node 20 en Amplify (marzo 2027) obliga a migrar, o se quiere gate de CI antes del deploy. Camino en ese caso: OpenNext → Lambda + CloudFront + S3.
