"""Mapeo ciudad → (cod_dpto, cod_mpio) según codificación DIAN/DIVIPOLA."""

import unicodedata
import re


def _norm(s: str) -> str:
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


# (cod_dpto_2dig, cod_mpio_3dig)
_MUNICIPIOS_RAW: dict[str, tuple[str, str]] = {
    # Capitales departamentales
    "bogota":              ("11", "001"),
    "bogota dc":           ("11", "001"),
    "santafe de bogota":   ("11", "001"),
    "medellin":            ("05", "001"),
    "cali":                ("76", "001"),
    "barranquilla":        ("08", "001"),
    "cartagena":           ("13", "001"),
    "cucuta":              ("54", "001"),
    "bucaramanga":         ("68", "001"),
    "manizales":           ("17", "001"),
    "pereira":             ("66", "001"),
    "ibague":              ("73", "001"),
    "armenia":             ("63", "001"),
    "popayan":             ("19", "001"),
    "valledupar":          ("20", "001"),
    "sincelejo":           ("70", "001"),
    "tunja":               ("15", "001"),
    "neiva":               ("41", "001"),
    "riohacha":            ("44", "001"),
    "santa marta":         ("47", "001"),
    "monteria":            ("23", "001"),
    "villavicencio":       ("50", "001"),
    "pasto":               ("52", "001"),
    "quibdo":              ("27", "001"),
    "florencia":           ("18", "001"),
    "mocoa":               ("86", "001"),
    "yopal":               ("85", "001"),
    "arauca":              ("81", "001"),
    "san andres":          ("88", "001"),
    "inirida":             ("94", "001"),
    "puerto carreno":      ("99", "001"),
    "mitu":                ("97", "001"),
    # Municipios del Valle de Aburrá / Antioquia
    "envigado":            ("05", "266"),
    "bello":               ("05", "088"),
    "itagui":              ("05", "360"),
    "sabaneta":            ("05", "631"),
    "la estrella":         ("05", "380"),
    "caldas":              ("05", "129"),
    "copacabana":          ("05", "212"),
    "girardota":           ("05", "308"),
    "barbosa":             ("05", "079"),
    "rionegro":            ("05", "615"),
    "la ceja":             ("05", "376"),
    "el retiro":           ("05", "607"),
    "guarne":              ("05", "318"),
    "marinilla":           ("05", "440"),
    "el santuario":        ("05", "652"),
    "caucasia":            ("05", "154"),
    "turbo":               ("05", "837"),
    "apartado":            ("05", "045"),
    # Cundinamarca / Bogotá
    "soacha":              ("25", "754"),
    "chia":                ("25", "175"),
    "zipaquira":           ("25", "899"),
    "facatativa":          ("25", "269"),
    "funza":               ("25", "295"),
    "mosquera":            ("25", "473"),
    "la calera":           ("25", "377"),
    "cajica":              ("25", "126"),
    "tocancipa":           ("25", "817"),
    "madrid":              ("25", "430"),
    "girardot":            ("25", "307"),
    # Valle del Cauca
    "palmira":             ("76", "520"),
    "buenaventura":        ("76", "109"),
    "tulua":               ("76", "834"),
    "buga":                ("76", "111"),
    "cartago":             ("76", "147"),
    "jamundi":             ("76", "364"),
    # Santander
    "floridablanca":       ("68", "276"),
    "giron":               ("68", "307"),
    "piedecuesta":         ("68", "572"),
    "barrancabermeja":     ("68", "081"),
    # Atlántico
    "soledad":             ("08", "758"),
    "malambo":             ("08", "433"),
    "sabanalarga":         ("08", "675"),
    # Córdoba / Costa
    "montelbano":          ("23", "466"),
    "lorica":              ("23", "417"),
    # Caldas / Eje Cafetero
    "chinchina":           ("17", "174"),
    "la dorada":           ("17", "380"),
    # Risaralda
    "dosquebradas":        ("66", "170"),
    "la virginia":         ("66", "400"),
    # Nariño
    "tumaco":              ("52", "835"),
    # Meta
    "acacias":             ("50", "006"),
    "granada":             ("50", "313"),
    # Sucre
    "since":               ("70", "820"),
    # Boyacá
    "duitama":             ("15", "238"),
    "sogamoso":            ("15", "759"),
    # Tolima
    "espinal":             ("73", "268"),
    "melgar":              ("73", "449"),
    # Huila
    "garzon":              ("41", "298"),
    "pitalito":            ("41", "551"),
    # Cesar
    "aguachica":           ("20", "011"),
    "bosconia":            ("20", "060"),
    # Norte de Santander
    "ocana":               ("54", "498"),
    "pamplona":            ("54", "518"),
    # Bolívar
    "magangue":            ("13", "430"),
    "turbaco":             ("13", "836"),
    # Quindío
    "calarca":             ("63", "130"),
    "la tebaida":          ("63", "401"),
    # La Guajira
    "maicao":              ("44", "430"),
    "uribia":              ("44", "847"),
}

# Build normalized lookup once at import
MUNICIPIOS: dict[str, tuple[str, str]] = {_norm(k): v for k, v in _MUNICIPIOS_RAW.items()}


def buscar_municipio(ciudad: str) -> tuple[str, str]:
    """
    Retorna (cod_dpto, cod_mpio) para una ciudad colombiana.
    Normaliza tildes, mayúsculas y ruido textual. Retorna ("", "") si no encuentra.
    """
    if not ciudad:
        return ("", "")

    # Limpiar ruido: "BOGOTÁ D.C." → "bogota dc", "La Estrella - Ant" → "la estrella"
    clean = _norm(re.sub(r"[,.\-–].*$", "", ciudad).strip())

    if clean in MUNICIPIOS:
        return MUNICIPIOS[clean]

    # Coincidencia parcial: el token buscado contiene o está contenido en la clave
    tokens = clean.split()
    for k, v in MUNICIPIOS.items():
        if k in clean or clean in k:
            return v
        # Token principal (primer word ≥5 chars) contra claves
        for tok in tokens:
            if len(tok) >= 5 and tok in k:
                return v

    return ("", "")
