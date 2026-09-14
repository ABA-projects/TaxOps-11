# Tarea actual — TaxOps-11

> Handoff **vivo** entre Claude y Kiro. Quien trabaja, actualiza este archivo al terminar.
> Responde: ¿qué se está haciendo ahora mismo y qué sigue?

**Última actualización:** 2026-09-14 · **Por:** Claude Code (rediseño frontend A+B mergeados; DIAN en investigación)

---

## Tarea activa

**Investigación DIAN: cómo traer las facturas recibidas sin descargarlas a mano.** Sin código aún.

Estado al 2026-09-14:
- **Hallazgo confirmado** (Anexo Técnico 1.9 §7.14.1, textual): `GetXmlByDocumentKey` valida que el
  certificado "corresponda al NIT de la empresa emisora **o receptora**". Es decir, el receptor SÍ
  puede bajar el XML por SOAP con su propio certificado digital, dado el CUFE. Vía oficial.
- **Limitación confirmada**: no hay método SOAP para listar recibidas por NIT/fecha (revisadas las
  753 páginas). Los CUFE hay que conseguirlos: Excel de "Documentos Recibidos" del catálogo (1 clic
  al mes), buzón de correo, o RADIAN (solo portal, sin WS de listado).
- **Sin confirmar**: si un NIT puede habilitarse como "software propio" SOLO para consultar sin
  emitir el set de pruebas; costo real del certificado (~190k COP/año, gratis con el software
  gratuito DIAN). El agente que lo investigaba murió por rate limit; relanzar.
- Descartado: scraping del catálogo (robots.txt Disallow, token de 1 h) y `searchqr` (Turnstile).
- Material extraído (fuera del repo, en el scratchpad de la sesión de Claude):
  `anexo19.txt`, `consulta-eventos-radian.txt`, `acuse.txt`. Si se pierden, se regeneran del PDF.
- Jaime tiene colegas con un sistema privado que lo hace; no sabemos el mecanismo. Pregunta
  abierta: ¿el contador hace algo manual en cada sync (token/link) o corre solo?

Siguiente paso: cerrar lo "sin confirmar", luego brainstorm del conector (spec) con la
recomendación actual: Excel del catálogo → CUFEs → SOAP con certificado del cliente → Fase 1.

## Pendiente

- **Rediseño frontend — Fases A y B HECHAS y mergeadas** (PR #53 landing editorial clara,
  PR #54 tokens de la app: verde, neutros de papel, Fraunces/Source Sans 3/JetBrains Mono).
  Calendario de la landing ya se lee del JSON con ISR diario (deuda pagada).
  **Fase C pendiente (solo si hace falta)**: pulido por página tras ver #54 en prod —
  revisar primero `/facturas` y `/chatbot` (más usos de `gray-*`). Deudas menores: renombrar
  `brand.orange`→`brand.green` (nombre engañoso a propósito, ~120 usos); el formulario de
  contacto de la landing es un `mailto:` sin backend; no se verificó en navegador (Chrome falló).
- **Discovery DIAN/XML — CERRADO (2026-09-10).** Veredicto: tratar el XML como fuente primaria está
  bien fundado legalmente (Res. 000165/2023 Art. 66: el XML tiene valor legal, el PDF es opcional).
  **Gap real:** `extract_xml` parsea UBL plano pero NO desenvuelve el `AttachedDocument` (contenedor
  con la factura en CDATA) que la DIAN entrega predominantemente. Síntesis + recomendación:
  `context/memory/discovery-dian-xml.md`; research crudo con fuentes: `docs/research/dian-xml/FINDINGS.md`.
  **Fase 1 HECHA y mergeada** (PR #50, `ac3ec14`). Queda la deuda de validarla contra 2-3
  AttachedDocument REALES — Jaime los consigue el lunes 2026-09-15. Exógenas/renta en XML = Fase 2,
  sigue diferida (el research la marca como dudosa: esos documentos llegan en PDF).

## Notas de handoff

- Al iniciar sesión: correr `scripts/context-sync.sh`.
- Antes de cambios en `infra/`: regla de oro (PR → plan → merge → aprobación manual → apply).
- Secretos viven en `.envrc` / `infra/**/terraform.tfvars.secret` (gitignored). Nunca copiarlos aquí.
- Los commits van firmados solo por Jaime — sin `Co-Authored-By`.
