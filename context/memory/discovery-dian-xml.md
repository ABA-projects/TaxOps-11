# Discovery — DIAN/XML como fuente primaria (spike, 2026-09-10)

> Spike de viabilidad. **No se tocó código.** Research normativo por subagente
> (`kirocrew-research`) + auditoría del código por Kiro. Research crudo con fuentes:
> `docs/research/dian-xml/FINDINGS.md`.

## Pregunta

¿Conviene tratar el XML de la factura electrónica como fuente primaria (en vez del PDF), y qué falta para soportarlo bien?

## Veredicto

**Sí, está bien fundado — y hay un gap concreto que resolver.** El núcleo es soportar el
`AttachedDocument` de la DIAN en `pipeline/extractor.py::extract_xml`.

## Hallazgos normativos (con fuente — ver FINDINGS.md)

- **El XML es el documento con valor legal**; el PDF es solo representación gráfica y **no es obligatorio** entregarlo/conservarlo (Res. DIAN 000165/2023, Art. 66 parágrafo; conservación Art. 64). → Priorizar XML es correcto legalmente.
- Lo que el adquirente recibe **predominantemente** es un **`AttachedDocument`** UBL 2.1 ("Contenedor de Factura Electrónica"), con la factura `<Invoice>`/`<CreditNote>` embebida como **CDATA** en `cac:Attachment/ext:ExternalReference/cbc:Description`, más el **ApplicationResponse** (CUDE, estado "Documento validado por la Dian", fecha de validación).
- Confianza: alta en el estatus legal del XML y en el uso del AttachedDocument; **media** en los paths/códigos exactos (030–034) → verificar contra Anexo Técnico 1.9 oficial antes de codificar.

## Hallazgos del código (auditoría Kiro)

- `pipeline/extractor.py::extract_xml` parsea **UBL plano** (`Invoice`/`CreditNote`) por XPath (CUFE, NIT, IVA, totales). **NO desenvuelve `AttachedDocument`.** Si llega el contenedor real de la DIAN, `root.tag` no matchea → extrae vacío/silencioso. **Este es el gap principal.**
- El extractor ya prioriza XML sobre PDF cuando coexisten (`extract_document`, `_resolver_archivos`).
- **Exógenas** (`exogenas/extractor.py`) y **Renta** (`services/renta/ocr_agent.py`) son **solo PDF/imagen** (pdfplumber + pytesseract). No leen XML. Ampliarlos a XML es trabajo aparte y mayor.

## Impacto por módulo

| Módulo | Hoy | Cambio para "XML primario" | Tamaño |
|---|---|---|---|
| Facturas (`pipeline/extractor.py`) | UBL plano | Desenvolver AttachedDocument (CDATA) + capturar CUDE/estado validación | **Medio, alto valor** |
| Exógenas | PDF/imagen | Leer XML (si el certificado viniera en XML) — incierto que aplique | Grande, dudoso |
| Renta | PDF/imagen (OCR) | Igual — los soportes rara vez son XML DIAN | Grande, dudoso |
| Infra | S3 + worker | Sin cambio: es parsing, no flujo | Nulo |

## Recomendación (alcance mínimo, alto valor)

1. **Fase 1 — Facturas:** que `extract_xml` detecte la raíz; si es `AttachedDocument`, extraer el CDATA de `cbc:Description`, re-parsear el UBL embebido y seguir el flujo actual. Capturar de paso CUDE + estado de validación DIAN. Es un cambio acotado a un módulo, con tests (necesita 1–2 XML reales de AttachedDocument como fixtures).
2. **Fase 2 (opcional, diferir):** exógenas/renta en XML — solo si aparece demanda real; hoy esos documentos llegan en PDF.
3. **Antes de codificar:** conseguir 2–3 AttachedDocument reales (con y sin ApplicationResponse) y validar paths contra el Anexo Técnico 1.9.

## Estado

Discovery cerrado. **No es research pendiente ya.** El siguiente paso, si se aprueba, es un plan
de implementación de la Fase 1 (spec + tests con fixtures reales). No se implementó nada en este spike.
