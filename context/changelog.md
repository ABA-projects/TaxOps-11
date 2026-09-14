## 2026-09-13 — Fase 1 DIAN/XML: soporte de AttachedDocument (Claude Code) — PR #50 MERGEADO (`ac3ec14`)

- `pipeline/extractor.py`: `extract_xml` desenvuelve el contenedor `AttachedDocument` de la DIAN
  (factura embebida como CDATA) y captura `cude` / `estado_dian` / `fecha_validacion_dian` del
  ApplicationResponse. El camino de UBL plano queda intacto.
- Cierra el gap que identificó el discovery: si llegaba el contenedor real, `extract_xml`
  devolvía una fila vacía **en silencio**.
- TDD: 6 tests nuevos en `tests/test_extractor.py` (4 en rojo antes del fix, 2 de regresión).
  49 passed en el archivo; 263 passed / 2 skipped en la suite; flake8 limpio.
- **Deuda:** fixtures sintéticos. Validar contra XML reales de la DIAN antes de considerarlo
  productivo. XPath del CDATA tolerante a `ext:`/`cac:ExternalReference` por no poder verificar
  contra el Anexo Técnico 1.9.

# Changelog de contexto — TaxOps-11

> Registro **incremental** de cambios relevantes por sesión (Claude o Kiro).
> No es el changelog de releases del producto — es la bitácora de trabajo entre agentes.
> Entradas nuevas al inicio. No registrar ruido (formateo, typos menores).

Formato por entrada:
```
## YYYY-MM-DD — <agente> — <título corto>
- Qué cambió · Por qué · Archivos/componentes · Decisiones · Problemas · Estado · Próximos pasos
```

---

## 2026-09-13 — Kiro CLI — EOL Node 20 CERRADO (#48/#49 mergeados + apply OK)
- **Qué:** PRs #48 (app) y #49 (infra Amplify) mergeados. `Terraform Apply` completó con **success** → Node 22 aplicado en el compute SSR de producción. CI en verde.
- **Estado:** EOL Node 20 resuelto end-to-end. `main` en `206b35c`.
- **Próximos pasos:** decidir si arrancar la Fase 1 del discovery DIAN/XML (AttachedDocument).

---

## 2026-09-10 — Kiro CLI — Discovery DIAN/XML (spike, con subagente de research)
- **Qué:** spike de viabilidad para tratar el XML como fuente primaria. Research normativo por subagente `kirocrew-research` + auditoría de código por Kiro. Cero código tocado.
- **Veredicto:** bien fundado legalmente (Res. 000165/2023 Art. 66 — XML tiene valor legal, PDF opcional). Gap real: `pipeline/extractor.py::extract_xml` lee UBL plano pero no desenvuelve el `AttachedDocument` (factura en CDATA) que la DIAN entrega. Exógenas/renta son solo PDF/imagen.
- **Archivos:** `context/memory/discovery-dian-xml.md` (síntesis), `docs/research/dian-xml/FINDINGS.md` (research crudo con fuentes, generado por el subagente).
- **Decisión:** recomendar Fase 1 acotada (AttachedDocument en facturas + CUDE/estado validación, con fixtures reales); diferir exógenas/renta en XML.
- **Estado:** discovery cerrado; pendiente decisión de Jaime para el plan de implementación.
- **Próximos pasos:** si se aprueba, spec + tests de Fase 1.

## 2026-09-10 — Kiro CLI — Migración a Node 22 por EOL de Node 20 → PRs #48/#49
- **Qué cambió:** capa app (`taxops-web/.nvmrc`=22, `engines.node>=22`) en PR #48; capa infra (`build_spec` de Amplify con `nvm use 22`) en PR #49.
- **Por qué:** Node 20 EOL 2026-04-30; Amplify corta deploys con Node 20 el 2027-03-03 y no migra solo.
- **Diagnóstico verificado:** el aviso NO es de nuestras Lambdas (`package_type = Image`, Python; no hay `runtime =` en `infra/`), sino del compute SSR de Amplify (`WEB_COMPUTE` + `Next.js - SSR`). Confirmado con grep en infra + web_search (EOL, comportamiento de Amplify).
- **Decisiones:** Node 22 (LTS, compatible Next 15.3, soportado por Amplify). Separado en 2 PRs porque infra va por el flujo Terraform (plan→aprobación→apply) y la app por PR normal.
- **Verificación:** app → `next lint`+`next build` en verde con Node v22.18.0; infra → `terraform fmt` limpio (validate/plan los corre el workflow del PR).
- **Estado:** PRs #48 y #49 abiertos, pendientes de merge (#49 con gate manual de Terraform).
- **Próximos pasos:** mergear #48/#49; el próximo pendiente grande es el discovery DIAN/XML.

---

## 2026-09-09 — PRs #45 y #46 MERGED en main (`c0be2cf`)
- **#45** (`fix/landing-claims-honestos`, `b846d08`) — claims falsos de la landing eliminados.
- **#46** (`chore/claude-kiro-coexistence`, `c0be2cf`) — sistema de coexistencia Claude+Kiro versionado.
- `main` local actualizado por fast-forward. `CLAUDE.md` y `.claude/` intactos.

## 2026-09-09 — Kiro CLI — Corregidos los claims falsos de la landing → PR #45
- **PR:** https://github.com/ABA-projects/TaxOps-11/pull/45 (rama `fix/landing-claims-honestos`, commit `46d0bad`).
- **Qué cambió:** `taxops-web/app/page.tsx` — eliminados testimonios inventados (array + render), quitado "SLA 99.9%", reemplazada feature "Funciona Sin Internet" por "Deduplicación por CUFE", corregidas cifras del hero (+500/100% → 3.286 autorretenedores/Art. 490), badge del hero y sección OFFLINE→"Sin instalar nada", nueva sección "Construido sobre la norma colombiana" con datos verificables. Limpiados imports huérfanos.
- **Por qué:** los claims eran falsos (SaaS en AWS, no offline; cifras y testimonios inventados) — riesgo legal/reputacional señalado por Jaime.
- **Verificación:** `tsc --noEmit` OK, `next lint` sin warnings, `next build` exit 0.
- **Decisiones:** se corrigieron los claims manteniendo el diseño actual; el rediseño visual "dirección C" queda como tarea aparte (fuentes a recuperar del canvas de Claude).
- **Estado:** landing sin claims falsos, compila.
- **Próximos pasos:** decidir commit; opcionalmente abordar rediseño dirección C y `.dockerignore`.

## 2026-09-09 — Kiro CLI — Integración de memoria de Claude (estado 2026-09-05)
- **Qué cambió:** se sincronizó el contexto compartido con la memoria de Claude `taxops11-estado-2026-09-05`, verificada contra git.
- **Por qué:** Claude avanzó el proyecto desde el setup de coexistencia; había que reflejarlo sin duplicar la nota.
- **Hallazgos verificados:** `main` avanzó a `fc0401e` (PRs #43, #44 mergeados desde `f397206`); agentes on-demand terminados y verificados en prod (#36–#44); claims falsos de la landing confirmados vivos por grep (`page.tsx` 45, 138, 165-167).
- **Archivos:** `context/current-task.md` (tarea activa = landing), `context/project-state.md` (agentes ✅, rama actual), `context/memory/known-issues.md` (tabla de claims + deuda `.dockerignore`).
- **Decisiones:** ninguna nueva (se referenció la memoria de Claude, no se copió entera).
- **Estado:** contexto compartido al día con lo último de Claude.
- **Próximos pasos:** ejecutar la corrección de la landing (empezar por testimonios líneas 165-167).

## 2026-09-09 — Kiro CLI — Setup del sistema de coexistencia Claude + Kiro
- **Qué cambió:** se creó la fuente de verdad compartida `context/`, el puente `AGENTS.md`, las reglas de Kiro en `.kiro/steering/` y el script `scripts/context-sync.sh`.
- **Por qué:** poder trabajar con Claude Code y Kiro CLI sobre el mismo proyecto sin perder contexto ni romper la configuración de Claude.
- **Archivos/componentes:** `context/*`, `AGENTS.md`, `.kiro/steering/taxops.md`, `scripts/context-sync.sh`, `context/README.md`.
- **Decisiones:** ver ADR-000 en `decisions.md`.
- **Problemas:** ninguno.
- **Estado:** setup completo; `CLAUDE.md` intacto.
- **Próximos pasos:** al abrir Kiro, correr `scripts/context-sync.sh`; retomar backlog cuando aplique.

## 2026-09-14 — Rediseño frontend (A+B) y hallazgo DIAN
- PR #53: landing editorial clara (neutros de papel columnar, Fraunces + Source Sans 3), hero con el
  asistente real, ilustración SVG del flujo AttachedDocument → Excel. Calendario leído del JSON con
  ISR diario. Copy unificado a tuteo. Sin cifras ni testimonios.
- PR #54: la app entera adopta el sistema por tokens (brand.orange = verde, gray/slate = neutros
  nuevos, fuentes de next/font). Login/signup/invite a fondo claro; dashboard con charts verde/ámbar.
- DIAN: confirmado en Anexo 1.9 §7.14.1 que el RECEPTOR puede bajar XML por SOAP con su
  certificado (dado el CUFE). No hay listado por NIT. Ver context/current-task.md.
