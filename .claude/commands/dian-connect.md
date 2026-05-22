Actúa como especialista en integración con la DIAN Colombia para descarga y consulta de facturas electrónicas recibidas.

## Realidad del ecosistema DIAN

La DIAN **NO expone una API REST pública** para descargar facturas recibidas de forma programática.
Las opciones reales van de mayor a menor viabilidad:

---

## Opción 1 — IMAP sobre correo electrónico (RECOMENDADA)

Las facturas DIAN llegan al email registrado como attachments XML+PDF.
Este proyecto ya procesa XMLs perfectamente → solo falta leerlos del correo.

```python
import imaplib, email
from pathlib import Path

def descargar_facturas_email(host, usuario, clave, carpeta_destino="facturas"):
    with imaplib.IMAP4_SSL(host) as imap:
        imap.login(usuario, clave)
        imap.select("INBOX")
        _, ids = imap.search(None, 'UNSEEN BODY "factura"')
        for uid in ids[0].split():
            _, data = imap.fetch(uid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            for part in msg.walk():
                if part.get_filename() and part.get_filename().endswith(".xml"):
                    xml_bytes = part.get_payload(decode=True)
                    dest = Path(carpeta_destino) / part.get_filename()
                    dest.write_bytes(xml_bytes)
```

**Hosts comunes:**
- Gmail: `imap.gmail.com` (requiere App Password, no la clave normal)
- Outlook/Hotmail: `outlook.office365.com`
- Otros: revisar configuración IMAP del proveedor

**Ventajas:** Sin depender de portales DIAN, funciona con las credenciales del correo, los XML ya están en el estándar UBL 2.1 que el extractor procesa.

**Limitaciones:** Solo captura facturas nuevas (no descarga historial anterior). Para historial: buscar también en SEEN o en carpetas específicas.

---

## Opción 2 — Portal VPFE con Selenium

Portal oficial: `https://catalogo-vpfe.dian.gov.co/User/SearchDocument`

Permite buscar por NIT receptor + rango de fechas y descargar XMLs manualmente. Se puede automatizar con Selenium:

```python
from selenium import webdriver
from selenium.webdriver.common.by import By

# Pasos:
# 1. Login con usuario/clave DIAN (cuenta en portal facturación)
# 2. Buscar por rango de fechas
# 3. Iterar resultados y descargar cada XML
```

**Ventajas:** Accede al historial completo de facturas recibidas.
**Limitaciones:** Frágil si DIAN cambia el portal. Requiere cuenta activa en el portal de facturación electrónica. Puede violar términos de uso si se hace en exceso.

---

## Opción 3 — Operadores Tecnológicos Autorizados (APIs de terceros)

Empresas autorizadas por DIAN que ofrecen REST API propia:

| Proveedor | Enfoque | Notas |
|-----------|---------|-------|
| [MATIAS API](https://matias-api.com/) | Emisión + consulta | REST, Postman docs, +8M docs procesados |
| [Factus](https://www.factus.com.co/) | Emisión REST completa | Swagger disponible |
| [Plemsi](https://plemsi.com/) | Emisión + validación | Autorizado DIAN |
| [Aliaddo](https://aliaddo.com/productos/api/) | Integración ERP | REST |
| [soenac/api-dian](https://github.com/soenac/api-dian) | Open source UBL 2.1 | Gratuito, GitHub |
| [bit4bit/facho](https://github.com/bit4bit/facho) | Open source Colombia | Gratuito, GitHub |

**Nota:** Estas APIs son principalmente para **emitir** facturas. La consulta de facturas **recibidas** es limitada en la mayoría. Consultar documentación individual.

---

## Opción 4 — Webservices SOAP oficiales DIAN

Solo aplica para **emisores** de facturas. No sirve para consultar facturas recibidas.

- Documentación técnica: `micrositios.dian.gov.co/sistema-de-facturacion-electronica/documentacion-tecnica/`
- Guía Web Services (PDF): `dian.gov.co/impuestos/factura-electronica/Documents/Guia-Herramienta-para-el-Consumo-de-Web-Services.pdf`

---

## Roadmap sugerido para este proyecto

```
Fase 2B: Integración IMAP
  → Leer correo donde llegan las facturas
  → Descargar XMLs a facturas/YYYY-MM/ automáticamente
  → watcher.py o main.py las procesa sin intervención manual

Fase 3+: Selenium VPFE (si se necesita historial)
  → Automatizar descarga histórica desde portal DIAN
  → Guardar en estructura de carpetas por mes
```

## Variables de entorno necesarias (Fase 2B)

```env
DIAN_EMAIL_HOST=imap.gmail.com
DIAN_EMAIL_USER=contabilidad@empresa.com
DIAN_EMAIL_PASS=xxxx-xxxx-xxxx-xxxx   # App Password de Google
DIAN_EMAIL_FOLDER=INBOX
DIAN_FACTURAS_DIR=facturas
```

$ARGUMENTS
