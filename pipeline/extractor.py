"""Extracción de datos de facturas electrónicas DIAN (PDF y XML)."""

import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import xml.etree.ElementTree as ET

import pdfplumber

logger = logging.getLogger(__name__)

# ── Autorretenedores (DIAN, corte 25/02/2026) ──────────────────────────────
_AUTORRETENEDORES_FILE = Path(__file__).parent / "autorretenedores.txt"
try:
    _AUTORRETENEDORES: frozenset[str] = frozenset(
        _AUTORRETENEDORES_FILE.read_text(encoding="utf-8").splitlines()
    )
except FileNotFoundError:
    _AUTORRETENEDORES = frozenset()
    logger.warning("autorretenedores.txt no encontrado — retención se calculará para todos")

# ── Namespaces UBL usados por DIAN ─────────────────────────────────────────
NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}

# ── Patrones regex ──────────────────────────────────────────────────────────
_RE_CUFE = re.compile(r"CUFE[:\s]+([a-f0-9]{96})", re.I)
_RE_CUDE = re.compile(r"CUDE[:\s]+([a-f0-9]{96})", re.I)
_RE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})")

# ── Folio ──────────────────────────────────────────────────────────────────
# Facturas y notas: "Número de Factura: FE-001"
_RE_FOLIO = re.compile(
    r"n[uú]mero\s+de\s+(?:la\s+)?factura\s*[:\s]+([A-Z0-9][A-Z0-9\-]+)"
    r"|n[uú]mero\s+factura\s*[:\s]+([A-Z0-9][A-Z0-9\-]+)"
    r"|(?:no\.?|nro\.?)\s+(?:de\s+)?factura\s*[:\s#]+([A-Z0-9][A-Z0-9\-]+)"
    r"|factura\s+(?:n[uú]m\.?|n[uú]mero|no\.?|nro\.?)\s*[:\s#]+([A-Z0-9][A-Z0-9\-]+)",
    re.I,
)
# Documentos equivalentes/soporte: "Número de documento: POSE5217"
# Solo captura si empieza con letra (NITs son solo dígitos)
_RE_FOLIO_DOC = re.compile(
    r"n[uú]mero\s+de\s+documento\s*[:\s]+([A-Za-z][A-Z0-9a-z\-]+)",
    re.I,
)

# ── Emisor — etiquetas DIAN estándar ───────────────────────────────────────
_RE_EMISOR_NIT    = re.compile(r"nit\s+del\s+emisor\s*[:\s]+([0-9]{6,12})", re.I)
_RE_EMISOR_NOMBRE = re.compile(r"raz[oó]n\s+social\s*[:\s]+([^\n\r]+)", re.I)

# Documento Equivalente POS: emisor está en "Datos del vendedor" (segunda sección)
_RE_VENDEDOR_NOMBRE = re.compile(
    r"datos\s+del\s+vendedor.{0,300}?raz[oó]n\s+social\s*[:\s]+([^\n\r]+)",
    re.I | re.DOTALL,
)
_RE_VENDEDOR_NIT = re.compile(
    r"datos\s+del\s+vendedor.{0,500}?n[uú]mero\s+de\s+documento\s*[:\s]+([0-9]{6,12})",
    re.I | re.DOTALL,
)

# ── Receptor — etiquetas DIAN estándar ────────────────────────────────────
_RE_RECEPTOR_NIT = re.compile(
    r"n[uú]mero\s+(?:de\s+)?documento\s*[:\s]+([0-9]{6,12})"
    r"|nit\s+(?:del\s+)?(?:adquir|comprador|receptor|cliente)[^\n]{0,30}?([0-9]{6,12})",
    re.I,
)
_RE_RECEPTOR_NOMBRE = re.compile(r"nombre\s+o\s+raz[oó]n\s+social\s*[:\s]+([^\n\r]+)", re.I)

# "NIT del adquiriente:" (Documento Equivalente POS)
# "adquiriente" tiene "iente" — se necesita i?ente para cubrir ambas grafías
_RE_ADQUIRIENTE_NIT = re.compile(
    r"nit\s+del\s+adquiri?ente\s*[:\s]+([0-9]{6,12})",
    re.I,
)
# "Razón social:" en sección adquiriente (Doc Equivalente / Soporte)
_RE_ADQUIRIENTE_NOMBRE = re.compile(
    r"datos\s+del\s+adquir.{0,300}?raz[oó]n\s+social\s*[:\s]+([^\n\r]+)",
    re.I | re.DOTALL,
)

# NIT genérico (fallback)
_RE_NIT_GENERICO = re.compile(r"NIT[:\s#.]*([0-9]{6,12})", re.I)

# Fecha desde nombre de carpeta: YYYY-MM, YYYY-MM-DD, DD-MM-YYYY, etc.
_RE_FOLDER_YEAR_MONTH = re.compile(r"(\d{4})[-_\s](\d{1,2})(?:[-_\s](\d{1,2}))?")
_RE_FOLDER_DMY        = re.compile(r"(\d{1,2})[-_/](\d{1,2})[-_/](\d{4})")


def _clean_number(value: str) -> float:
    """Convierte '1.234.567,89' o '1,234,567.89' a float."""
    value = value.strip().replace(" ", "")
    if not value:
        return 0.0
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value and value.count(",") == 1 and len(value.split(",")[1]) <= 2:
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_date(raw: str) -> str:
    """Normaliza fecha a YYYY-MM-DD."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw.strip()


def _date_from_folder(path: Path) -> str:
    """Intenta extraer una fecha del nombre de la carpeta que contiene el archivo."""
    folder = path.parent.name
    m = _RE_FOLDER_YEAR_MONTH.search(folder)
    if m:
        year, month = m.group(1), m.group(2).zfill(2)
        day = m.group(3).zfill(2) if m.group(3) else "01"
        return f"{year}-{month}-{day}"
    m2 = _RE_FOLDER_DMY.search(folder)
    if m2:
        day, month, year = m2.group(1).zfill(2), m2.group(2).zfill(2), m2.group(3)
        return f"{year}-{month}-{day}"
    return ""


def _detect_doc_type(text: str, filename: str) -> str:
    tl = (text + filename).lower()
    stem = Path(filename).stem.lower()
    if "nota cr" in tl or "note credit" in tl or stem.startswith("nc-") or stem.startswith("nc_"):
        return "Nota Crédito"
    if "nota déb" in tl or "nota deb" in tl or stem.startswith("nd-") or stem.startswith("nd_"):
        return "Nota Débito"
    if "mandato" in tl or "peaje" in tl:
        return "Mandato/Peaje"
    if "documento soporte" in tl:
        return "Documento Soporte"
    if "documento equivalente" in tl:
        return "Documento Equivalente"
    return "Factura Electrónica"


def _calc_retencion(subtotal: float, nit_emisor: str,
                    base19: float = 0.0, base5: float = 0.0) -> float:
    """Retención en la fuente = subtotal × 2.5%.
    Cero si el emisor es autorretenedor.
    Cero si (base_19 + base_5) ≤ 524.000 (tope mínimo Art. 383 ET ~ 4 UVT 2025).
    """
    if nit_emisor.strip() in _AUTORRETENEDORES:
        return 0.0
    # Si la sumatoria de bases IVA gravadas no supera el tope → no hay retención
    TOPE_RETENCION = 524_000.0
    base_gravada = base19 + base5
    # Si hay bases conocidas y no superan el tope, no retener
    if base_gravada > 0 and base_gravada <= TOPE_RETENCION:
        return 0.0
    return round(subtotal * 0.025, 2)


def _split_iva_bases(subtotal: float, iva19: float, iva5: float,
                     base19_direct: float = 0.0, base5_direct: float = 0.0
                     ) -> tuple[float, float, float]:
    """
    Devuelve (base_iva_19, base_iva_5, no_gravado).
    Si se pasan base19_direct/base5_direct (del XML TaxableAmount) se usan directamente.
    Para PDF se back-calcula desde el monto de IVA.
    no_gravado = subtotal - base_iva_19 - base_iva_5, mínimo 0.
    """
    s = abs(subtotal)
    b19 = base19_direct if base19_direct else (round(iva19 / 0.19, 2) if iva19 else 0.0)
    b5  = base5_direct  if base5_direct  else (round(iva5  / 0.05, 2) if iva5  else 0.0)
    b19 = min(round(b19, 2), s)
    b5  = min(round(b5,  2), max(0.0, s - b19))
    no_grav = max(0.0, round(s - b19 - b5, 2))
    return b19, b5, no_grav


def _clean_name(raw: str) -> str:
    """Limpia un nombre: recorta en etiquetas adyacentes y limita longitud."""
    raw = raw.strip()
    m = re.search(r"\s{2,}[A-Za-záéíóúÁÉÍÓÚñÑ ]{3,30}\s*:", raw)
    if m:
        raw = raw[:m.start()].strip()
    return raw[:80]


# ══════════════════════════════════════════════════════════════════════════════
# XML
# ══════════════════════════════════════════════════════════════════════════════

def _xml_text(root: ET.Element, path: str) -> str:
    el = root.find(path, NS)
    return el.text.strip() if el is not None and el.text else ""


def extract_xml(path: Path) -> dict:
    """Extrae campos de un XML DIAN (UBL 2.1)."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error("XML inválido %s: %s", path.name, e)
        return _empty_row(path.name, "XML inválido")

    tag = root.tag.lower()
    if "creditnote" in tag:
        doc_type = "Nota Crédito"
        cufe_path = "ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/cbc:UUID"
    else:
        doc_type = "Factura Electrónica"
        cufe_path = "cbc:UUID"

    cufe = _xml_text(root, cufe_path) or _xml_text(root, "cbc:UUID")
    folio = _xml_text(root, "cbc:ID")
    fecha = _xml_text(root, "cbc:IssueDate")

    nit_emisor = _xml_text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
    nom_emisor  = (
        _xml_text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")
        or _xml_text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name")
    )
    nit_receptor = _xml_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
    nom_receptor = (
        _xml_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")
        or _xml_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name")
    )

    subtotal = 0.0
    iva19 = 0.0
    iva5  = 0.0
    base19_xml = 0.0
    base5_xml  = 0.0

    for tax in root.findall(".//cac:TaxTotal", NS):
        amount_el = tax.find("cbc:TaxAmount", NS)
        amount = float(amount_el.text) if amount_el is not None and amount_el.text else 0.0
        percent_el = tax.find(".//cac:TaxSubtotal/cbc:Percent", NS)
        pct = float(percent_el.text) if percent_el is not None and percent_el.text else 0.0
        taxable_el = tax.find(".//cac:TaxSubtotal/cbc:TaxableAmount", NS)
        taxable = float(taxable_el.text) if taxable_el is not None and taxable_el.text else 0.0
        if abs(pct - 19) < 0.5:
            iva19 += amount
            base19_xml += taxable
        elif abs(pct - 5) < 0.5:
            iva5 += amount
            base5_xml += taxable

    le = root.find("cac:LegalMonetaryTotal", NS)
    if le is not None:
        subtotal = float((_xml_text(le, "cbc:TaxExclusiveAmount") or "0").replace(",", "."))
        total    = float((_xml_text(le, "cbc:PayableAmount") or "0").replace(",", "."))
    else:
        total = 0.0

    sign = -1 if doc_type == "Nota Crédito" else 1
    subtotal_signed = round(sign * subtotal, 2)
    iva19_signed = round(sign * iva19, 2)
    iva5_signed  = round(sign * iva5,  2)
    base19, base5, no_grav = _split_iva_bases(
        subtotal_signed, abs(iva19_signed), abs(iva5_signed),
        base19_direct=base19_xml, base5_direct=base5_xml,
    )

    return {
        "archivo":           path.name,
        "tipo":              doc_type,
        "cufe":              cufe,
        "folio":             folio,
        "fecha":             _parse_date(fecha),
        "nit_emisor":        nit_emisor,
        "nombre_emisor":     nom_emisor,
        "nit_receptor":      nit_receptor,
        "nombre_receptor":   nom_receptor,
        "subtotal":          subtotal_signed,
        "base_iva_19":       base19,
        "iva_19":            iva19_signed,
        "base_iva_5":        base5,
        "iva_5":             iva5_signed,
        "no_gravado":        no_grav,
        "total":             round(sign * total, 2),
        "retencion_fuente":  _calc_retencion(abs(subtotal_signed), nit_emisor, base19, base5),
        "fuente":            "XML",
    }


# ══════════════════════════════════════════════════════════════════════════════
# PDF
# ══════════════════════════════════════════════════════════════════════════════

def _search_money_near(text: str, label: str, line_start: bool = False) -> float:
    """
    Busca el valor monetario en la misma línea que la etiqueta.
    line_start=True requiere que la etiqueta esté al inicio de la línea
    (con espacios opcionales), evitando falsos positivos mid-line.
    """
    prefix = r"^\s*" if line_start else r"^[^\n]*"
    pattern = re.compile(
        rf"{prefix}{re.escape(label)}[^\d\n]{{0,60}}([\d][\d.,]*)",
        re.I | re.MULTILINE,
    )
    m = pattern.search(text)
    if m:
        return _clean_number(m.group(1))
    return 0.0


def _extract_iva_detalle(text: str) -> tuple[float, float]:
    """
    Extrae IVA 19% e IVA 5% sumando los montos desde las líneas de detalle.
    Patrón: {monto_iva} {pct}.00 — el monto aparece justo antes del porcentaje.
    Limita la búsqueda a la sección de productos para evitar falsos positivos.
    """
    m_ini = re.search(r'detalles?\s+de\s+productos?', text, re.I)
    m_fin = re.search(r'notas?\s+finales?|datos?\s+totales?', text, re.I)
    if m_ini and m_fin and m_fin.start() > m_ini.start():
        seccion = text[m_ini.start():m_fin.start()]
    elif m_ini:
        seccion = text[m_ini.start():]
    else:
        seccion = text

    iva19 = sum(
        _clean_number(m.group(1))
        for m in re.finditer(r'([\d.,]+)\s+19\.0+\s', seccion)
    )
    iva5 = sum(
        _clean_number(m.group(1))
        for m in re.finditer(r'([\d.,]+)\s+5\.0+\s', seccion)
    )
    return round(iva19, 2), round(iva5, 2)


def _first_group(*matches) -> str:
    """Retorna el primer grupo no vacío de una lista de match objects."""
    for m in matches:
        if m:
            groups = [g for g in m.groups() if g]
            if groups:
                return groups[0].strip()
    return ""


def _docx_to_text(path: Path) -> str:
    """Extrae texto plano de un archivo .docx."""
    from docx import Document
    doc = Document(str(path))
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def extract_docx(path: Path) -> dict:
    """Extrae campos de un DOCX DIAN convirtiendo a texto y reutilizando el pipeline de PDF."""
    try:
        text = _docx_to_text(path)
    except Exception as e:
        logger.error("Error leyendo DOCX %s: %s", path.name, e)
        return _empty_row(path.name, str(e))

    if not text.strip():
        return _empty_row(path.name, "DOCX sin texto extraíble")

    # Reutiliza la lógica de extracción de texto del pipeline PDF
    return _extract_from_text(path, text)


def _extract_from_text(path: Path, text: str) -> dict:
    """Extrae campos DIAN desde texto plano (usado por PDF y DOCX)."""
    doc_type = _detect_doc_type(text, path.name)
    es_doc_equivalente = doc_type == "Documento Equivalente"

    # ── CUFE / CUDE ────────────────────────────────────────────────────────
    cufe = ""
    m = _RE_CUFE.search(text)
    if m:
        cufe = m.group(1)
    else:
        m2 = _RE_CUDE.search(text)
        cufe = m2.group(1) if m2 else ""

    # ── Folio ──────────────────────────────────────────────────────────────
    # Facturas/notas: "Número de Factura: FE-001"
    # Doc equivalente/soporte: "Número de documento: POSE5217" (inicia con letra)
    folio = (
        _first_group(_RE_FOLIO.search(text))
        or _first_group(_RE_FOLIO_DOC.search(text))
    )

    # ── Fecha de emisión ───────────────────────────────────────────────────
    fecha = ""
    m_fecha = re.search(
        r"fecha\s+(?:de\s+)?(?:emisi[oó]n|generaci[oó]n|expedici[oó]n)\s*[:\s]+(\S+)",
        text, re.I,
    )
    if m_fecha:
        fecha = _parse_date(m_fecha.group(1))
    else:
        for dm in _RE_DATE.finditer(text):
            fecha = _parse_date(dm.group(1))
            break

    # ── Emisor ─────────────────────────────────────────────────────────────
    # Doc Equivalente POS tiene "Datos del vendedor" en lugar de "Datos del emisor".
    # Los demás tipos (Factura, NC, ND, Soporte, Doc Equiv SPD) tienen "Datos del emisor".
    tiene_vendedor = bool(re.search(r'datos\s+del\s+vendedor', text, re.I))

    if es_doc_equivalente and tiene_vendedor:
        m = _RE_VENDEDOR_NIT.search(text)
        nit_emisor = m.group(1).strip() if m else ""
        m = _RE_VENDEDOR_NOMBRE.search(text)
        nom_emisor = _clean_name(m.group(1)) if m else ""
    else:
        m_en = _RE_EMISOR_NIT.search(text)
        nit_emisor = m_en.group(1).strip() if m_en else ""
        m_enombre = _RE_EMISOR_NOMBRE.search(text)
        nom_emisor = _clean_name(m_enombre.group(1)) if m_enombre else ""

    # ── Receptor ───────────────────────────────────────────────────────────
    # Doc Equivalente POS: "NIT del adquiriente:", "Razón social:" en sección adquiriente
    # Resto (Factura, NC, ND, Soporte, Doc Equiv SPD): patrones estándar DIAN
    if es_doc_equivalente and tiene_vendedor:
        m = _RE_ADQUIRIENTE_NIT.search(text)
        nit_receptor = m.group(1).strip() if m else ""
        m = _RE_ADQUIRIENTE_NOMBRE.search(text)
        nom_receptor = _clean_name(m.group(1)) if m else ""
    else:
        m_rn = _RE_RECEPTOR_NIT.search(text)
        nit_receptor = _first_group(m_rn) if m_rn else ""
        m_rnombre = _RE_RECEPTOR_NOMBRE.search(text)
        nom_receptor = _clean_name(m_rnombre.group(1)) if m_rnombre else ""
        # Fallback para doc soporte/equivalente SPD: "Razón social" en sección adquiriente
        if not nom_receptor:
            m = _RE_ADQUIRIENTE_NOMBRE.search(text)
            if m:
                nom_receptor = _clean_name(m.group(1))

    # Fallback genérico por NIT si alguno quedó vacío
    if not nit_emisor or not nit_receptor:
        nits = [m.group(1) for m in _RE_NIT_GENERICO.finditer(text)]
        if not nit_emisor and nits:
            nit_emisor = nits[0]
        if not nit_receptor and len(nits) > 1:
            nit_receptor = nits[1]

    # ── Montos ─────────────────────────────────────────────────────────────
    # Subtotal = Total Bruto Factura/Documento (base después de descuentos)
    subtotal = (
        _search_money_near(text, "Total Bruto Factura")
        or _search_money_near(text, "Total bruto documento")
        or _search_money_near(text, "base gravable")
        or _search_money_near(text, "base imponible")
        or _search_money_near(text, "subtotal")
    )

    # IVA por tasa — primero desde líneas de detalle (más preciso para tasas mixtas)
    iva19, iva5 = _extract_iva_detalle(text)

    if not iva19 and not iva5:
        # Fallback: líneas del resumen de totales
        iva19 = (
            _search_money_near(text, "IVA 19%")
            or _search_money_near(text, "impuesto 19")
            or _search_money_near(text, "IVA", line_start=True)
        )
        iva5 = (
            _search_money_near(text, "IVA 5%")
            or _search_money_near(text, "impuesto 5")
        )
        # Último recurso: "Total IVA" sin discriminar tasa → va a iva_19 por convención
        if not iva19 and not iva5:
            iva19 = _search_money_near(text, "Total IVA")

    # Total: "Total factura/documento" tiene prioridad sobre "Total neto" (más preciso)
    total = (
        _search_money_near(text, "Total factura")
        or _search_money_near(text, "Total documento")
        or _search_money_near(text, "Total neto factura")
        or _search_money_near(text, "Total neto documento")
        or _search_money_near(text, "total a pagar")
        or _search_money_near(text, "valor total")
    )

    # Nota Crédito: valores negativos. Nota Débito y resto: positivos
    sign = -1 if doc_type == "Nota Crédito" else 1
    subtotal_signed = round(sign * subtotal, 2)
    iva19_signed = round(sign * iva19, 2)
    iva5_signed  = round(sign * iva5,  2)
    base19, base5, no_grav = _split_iva_bases(
        subtotal_signed, abs(iva19_signed), abs(iva5_signed),
    )

    return {
        "archivo":           path.name,
        "tipo":              doc_type,
        "cufe":              cufe,
        "folio":             folio,
        "fecha":             fecha,
        "nit_emisor":        nit_emisor,
        "nombre_emisor":     nom_emisor,
        "nit_receptor":      nit_receptor,
        "nombre_receptor":   nom_receptor,
        "subtotal":          subtotal_signed,
        "base_iva_19":       base19,
        "iva_19":            iva19_signed,
        "base_iva_5":        base5,
        "iva_5":             iva5_signed,
        "no_gravado":        no_grav,
        "total":             round(sign * total, 2),
        # Nota Crédito no genera nueva retención (la retención fue de la factura original)
        "retencion_fuente":  0.0 if doc_type == "Nota Crédito" else _calc_retencion(abs(subtotal_signed), nit_emisor, base19, base5),
        "fuente":            path.suffix.upper().lstrip("."),
    }


def extract_pdf(path: Path) -> dict:
    """Extrae campos de un PDF DIAN con pdfplumber."""
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        logger.error("Error leyendo PDF %s: %s", path.name, e)
        return _empty_row(path.name, str(e))
    return _extract_from_text(path, text)


def _empty_row(filename: str, error: str) -> dict:
    return {
        "archivo": filename, "tipo": "ERROR", "cufe": "", "folio": "",
        "fecha": "", "nit_emisor": "", "nombre_emisor": "",
        "nit_receptor": "", "nombre_receptor": "",
        "subtotal": 0.0,
        "base_iva_19": 0.0, "iva_19": 0.0,
        "base_iva_5":  0.0, "iva_5":  0.0,
        "no_gravado":  0.0,
        "total": 0.0, "retencion_fuente": 0.0,
        "fuente": f"ERROR: {error}",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Dispatcher principal
# ══════════════════════════════════════════════════════════════════════════════

def extract_one(path: Path) -> Optional[dict]:
    """
    Extrae un único documento (PDF o XML). Sin gestión de `processed`;
    la deduplicación se hace antes en el escaneo de main.py.
    Thread-safe: no comparte estado mutable.
    """
    try:
        suf = path.suffix.lower()
        if suf == ".xml":
            row = extract_xml(path)
        elif suf in (".docx", ".doc"):
            row = extract_docx(path)
        else:
            row = extract_pdf(path)
        if not row.get("fecha"):
            fd = _date_from_folder(path)
            if fd:
                row["fecha"] = fd
        return row
    except Exception as e:
        logger.error("FALLO %s: %s", path.name, e)
        return None


def extract_document(path: Path, processed: set[str]) -> Optional[dict]:
    """Interfaz legada (watcher/app.py). Para lotes grandes usar extract_one."""
    name_key = str(path.with_suffix("")).lower()
    if name_key in processed:
        return None
    processed.add(name_key)

    xml_sibling = path.with_suffix(".xml")
    if path.suffix.lower() == ".pdf" and xml_sibling.exists():
        processed.add(str(xml_sibling.with_suffix("")).lower())
        path = xml_sibling

    return extract_one(path)
