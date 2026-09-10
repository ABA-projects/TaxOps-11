# DIAN — ¿XML como fuente primaria vs PDF? — Hallazgos

## 1. FORMATO DE ENTREGA — Veredicto: **DEPENDE (predomina AttachedDocument)**
La norma (Res. 000165/2023, Art. 11 num. 7 y Art. 35.1) obliga a entregar al adquirente el **XML de generación + el documento electrónico de validación** con valor "Documento validado por la Dian", ambos dentro de un **"contenedor electrónico"**. En la práctica 2025–2026 ese contenedor se materializa como un **`<AttachedDocument>` UBL 2.1** (raíz `AttachedDocument`, `DocumentType` = "Contenedor de Factura Electrónica") que lleva la factura UBL (`<Invoice>`/`<CreditNote>`) **embebida como CDATA**. El UBL plano existe como el ejemplar *dentro* del contenedor, pero lo que llega por correo/portal suele ser el AttachedDocument. Tu app debe soportar **ambos** (detectar raíz y des-envolver).

## 2. AttachedDocument — Veredicto: **SÍ, el adquirente típicamente lo recibe**
Estructura confirmada por muestras reales: raíz `AttachedDocument` → cabecera propia (`cbc:ID`, `IssueDate`, `DocumentType`) → **la factura UBL va como CDATA escapado dentro de `cac:Attachment/ext:ExternalReference/cbc:Description`**. El mismo AttachedDocument suele incluir además el **ApplicationResponse de la DIAN (CUDE) con el resultado de validación** (en `cac:ParentDocumentLineReference`/`cbc:Description` secundaria o adjunto). El adquirente que recibe factura vía email/proveedor recibe normalmente el AttachedDocument + PDF dentro de un ZIP.

## 3. PDF / REPRESENTACIÓN GRÁFICA — Veredicto: **NO exige PDF; el XML es el de valor legal**
Res. 000165/2023, **Art. 66 parágrafo** (adic. Res. 119/2024): *"El formato de generación electrónica **XML será el que tenga valor legal**… La representación gráfica… puede ser diseñada de acuerdo con las necesidades del sujeto obligado."* La conservación (Art. 64) se exige sobre los documentos electrónicos (XML). El PDF es solo representación gráfica y su forma es libre → **el XML como fuente primaria está bien fundado**.

## 4. CAMPOS CLAVE solo en AttachedDocument (no en el UBL plano)
- **Estado / resultado de validación**: valor `"Documento validado por la Dian"` (Art. 33) — no está en el UBL de factura, viene en el ApplicationResponse.
- **CUDE del ApplicationResponse** (distinto del CUFE de la factura) — identifica la validación DIAN.
- **Fecha/hora de validación DIAN** (`IssueDate`/`IssueTime` del AttachedDocument y del ApplicationResponse).
- **ResponseCode del evento**: p. ej. `030` validado, `031` recibido, `032` acuse, `033` reclamo, `034` aceptación expresa (uso RADian / eventos, tabla anexo 1.9 tipo `96` = ApplicationResponse).
- Cabecera del contenedor: `cbc:ID` y `DocumentType` = "Contenedor de Factura Electrónica".

> Nota de confianza: Q1/Q3 están respaldados por texto normativo directo (fuerte). La ubicación exacta del CDATA y los ResponseCode están respaldados por muestras/implementaciones reales (moderado-fuerte); los códigos 030–034 provienen de un módulo comercial y de la tabla de un PT, no verbatim de la Res. — verifícalos contra el Anexo Técnico 1.9 antes de codificarlos como constantes.

## FUENTES
- Resolución DIAN 000165 de 2023 (texto integral, Arts. 11, 33, 35, 64, 66): https://cijuf.org.co/normatividad/resolucion/2023/resolucion-000165.html
- Resolución 000165/2023 en Normograma DIAN: https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0165_2023.htm
- Documentación técnica DIAN (Anexos Técnicos 1.7/1.8/1.9): https://www.dian.gov.co/impuestos/factura-electronica/documentacion/Paginas/documentacion-tecnica.aspx
- Muestra real de AttachedDocument ("Contenedor de Factura Electrónica", UBL 2.1): https://www.ramajudicial.gov.co/documents/36159272/140240001/007RecursoReposicion.pdf
- Odoo `l10n_co_dian_vendor_bill_import` (envoltorio AttachedDocument, CDATA en cbc:Description, ResponseCodes 030–034): https://apps.odoo.com/apps/modules/18.0/l10n_co_dian_vendor_bill_import
- Misfacturas — "el AttachedDocument es el certificado que emite la DIAN… abrir el ZIP verás el PDF y el XML": https://soporte.misfacturas.com.co/hc/es-419/articles/34958912310292
- Tabla de códigos anexo 1.9 (tipo doc `96` = Eventos/ApplicationResponse), TheFactoryHKA: https://felcowiki.thefactoryhka.com.co/index.php/Tablas_de_c%C3%B3digos_de_propiedades_para_emisi%C3%B3n_de_documentos_-_Indice_Manual_Integraci%C3%B3n_Directa
- ¿Cómo identificar una factura electrónica? (XML es el documento; PDF es representación gráfica): https://www.dian.gov.co/Prensa/Paginas/NG-Como-identificar-una-factura-electronica.aspx
