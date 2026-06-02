"""Generador Excel Formulario 210 DIAN — Declaración Renta Personas Naturales.

Layout: 3 columnas (casilla | descripción | valor $) con colores DIAN.
Casillas según instructivo oficial DIAN 2024.
"""
from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ── Paleta DIAN ───────────────────────────────────────────────────────────────
_DARK   = "1F3864"   # azul oscuro — títulos principales
_MED    = "2E75B6"   # azul medio — encabezados de sección
_LIGHT  = "BDD7EE"   # azul claro — sub-secciones
_VLIGHT = "DEEAF1"   # azul muy claro — filas alternas
_WHITE  = "FFFFFF"
_YELLOW = "FFFF00"   # fondo BORRADOR
_RED    = "C00000"

UVT_2025 = 49_799.0
LIMIT_UVT_40 = 1_340 * UVT_2025   # 1340 UVT


# ── Thin border helper ────────────────────────────────────────────────────────
def _thin() -> Border:
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)


# ── Cell writers ──────────────────────────────────────────────────────────────
def _fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color)


def _hdr(ws, row: int, text: str, color: str, *, text_color: str = "FFFFFF",
         bold: bool = True, height: float = 18) -> None:
    """Fila encabezado — span A:C."""
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row=row, column=1)
    c.value = text
    c.font = Font(name="Calibri", size=10, bold=bold, color=text_color)
    c.fill = _fill(color)
    c.alignment = Alignment(horizontal="left", vertical="center",
                             indent=1, wrap_text=True)
    c.border = _thin()
    ws.row_dimensions[row].height = height


def _data(ws, row: int, casilla: int | str, desc: str, value: Any,
          bg: str = _WHITE) -> None:
    """Fila de datos: casilla | descripción | valor."""
    # Casilla
    ca = ws.cell(row=row, column=1, value=str(casilla) if casilla else "")
    ca.font = Font(name="Calibri", size=9, bold=bool(casilla), color=_DARK)
    ca.fill = _fill(bg)
    ca.alignment = Alignment(horizontal="center", vertical="center")
    ca.border = _thin()

    # Descripción
    de = ws.cell(row=row, column=2, value=desc)
    de.font = Font(name="Calibri", size=9, color=_DARK)
    de.fill = _fill(bg)
    de.alignment = Alignment(horizontal="left", vertical="center",
                              indent=1, wrap_text=True)
    de.border = _thin()

    # Valor
    try:
        num = float(value) if value not in (None, "", "—") else None
    except (ValueError, TypeError):
        num = None
    va = ws.cell(row=row, column=3)
    if num is not None:
        va.value = num
        va.number_format = '#,##0'
    elif value not in (None, "", "—"):
        va.value = str(value)
    else:
        va.value = "—"
        va.alignment = Alignment(horizontal="center")
    va.font = Font(name="Calibri", size=9, color=_DARK)
    va.fill = _fill(bg)
    va.alignment = Alignment(horizontal="right", vertical="center")
    va.border = _thin()
    ws.row_dimensions[row].height = 15


def _blank(ws, row: int) -> None:
    for col in range(1, 4):
        ws.cell(row=row, column=col).fill = _fill(_WHITE)
    ws.row_dimensions[row].height = 6


# ── Cálculos intermedios ──────────────────────────────────────────────────────
def _v(d: dict, key: str, default: float = 0.0) -> float:
    return float(d.get(key) or default)


def _intermedios(decl: dict) -> dict:
    """Calcula casillas intermedias no almacenadas directamente en la DB."""
    ing_lab   = _v(decl, "ingresos_laborales")
    pen       = _v(decl, "aportes_pension")
    afc       = _v(decl, "afc_fvp")
    int_viv   = _v(decl, "intereses_vivienda")
    med       = _v(decl, "medicina_prepagada")
    dep       = int(_v(decl, "dependientes"))
    cap       = _v(decl, "rentas_capital")
    no_lab    = _v(decl, "rentas_no_laborales")
    div       = _v(decl, "dividendos")
    goc       = _v(decl, "ganancias_ocasionales")
    pat_bruto = _v(decl, "patrimonio_bruto")
    pasivos   = _v(decl, "pasivos")

    # Casilla 34: renta líquida de trabajo
    c34 = max(0.0, ing_lab - pen)

    # Casilla 36: rentas exentas 25% num.10 Art.206 ET
    c36_bruto = round(ing_lab * 0.25, 2)
    c36_cap   = 240 * 12 * UVT_2025   # 240 UVT/mes
    c36       = min(c36_bruto, c36_cap)

    # Casilla 37: total rentas exentas trabajo
    c37 = afc + c36

    # Casilla 39: otras deducciones (salud + dependientes)
    dep_uvt = min(dep * 32 * UVT_2025, ing_lab * 0.10)
    c39 = med + dep_uvt

    # Casilla 40: total deducciones
    c40 = int_viv + c39

    # Base para límite 40%: sum ingresos netos
    ingresos_netos = max(0.0, ing_lab - pen + cap + no_lab)
    bruto_exe_ded  = c37 + c40
    limite = min(bruto_exe_ded, ingresos_netos * 0.40, LIMIT_UVT_40)

    # Casilla 41: rentas exentas y deducciones imputables limitadas
    c41 = round(limite, 2)

    # Casilla 42: renta líquida ordinaria trabajo
    c42 = max(0.0, c34 - c41)

    # Casilla 91: renta líquida cédula general (simplificado: 42 + cap + no_lab)
    c91 = c42 + max(0.0, cap) + max(0.0, no_lab)
    c97 = _v(decl, "renta_gravable") or c91

    # Casilla 115: ganancias ocasionales gravables
    c115 = max(0.0, goc)

    # Impuestos
    imp_cargo  = _v(decl, "impuesto_cargo")
    # Casilla 116 = imp sobre cédula general (usamos detalle si existe)
    detalle = (decl.get("detalle_calculo") or decl.get("datos_calculados") or {})
    if isinstance(detalle, dict):
        c116 = float(detalle.get("impuesto_cedula_general",
               detalle.get("consolidado", {}).get("impuesto_cedula_general", imp_cargo)))
    else:
        c116 = imp_cargo
    c127 = _v(detalle, "impuesto_ocasional") if isinstance(detalle, dict) else 0.0
    c129 = imp_cargo

    ret  = _v(decl, "retenciones")
    c134 = _v(decl, "saldo_pagar")
    c137 = _v(decl, "saldo_favor")

    return {
        "c29": pat_bruto, "c30": pasivos,
        "c31": max(0.0, pat_bruto - pasivos),
        "c32": ing_lab, "c33": pen, "c34": c34,
        "c35": afc, "c36": c36, "c37": c37,
        "c38": int_viv, "c39": c39, "c40": c40,
        "c41": c41, "c42": c42,
        "c58": cap, "c74": no_lab,
        "c91": c91, "c97": c97,
        "c107": div, "c115": c115,
        "c116": c116, "c127": c127, "c129": c129,
        "c132": ret, "c134": c134, "c136": c134,
        "c137": c137,
    }


# ── Generador principal ───────────────────────────────────────────────────────
def generar_excel(declaracion: dict, contribuyente: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "F210"

    # Anchos
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 60
    ws.column_dimensions["C"].width = 20

    v    = _intermedios(declaracion)
    año  = declaracion.get("año_gravable", 2025)
    est  = (declaracion.get("estado") or "borrador").upper()
    nombre = (contribuyente.get("nombre_completo") or "").upper()
    nit    = contribuyente.get("numero_doc", "")
    ciudad = contribuyente.get("ciudad", "")

    r = 1

    # ── Título ────────────────────────────────────────────────────────────────
    ws.merge_cells(f"A{r}:C{r}")
    c = ws.cell(row=r, column=1,
                value="DECLARACIÓN DE RENTA Y COMPLEMENTARIO"
                      "  —  PERSONAS NATURALES Y ASIMILADAS RESIDENTES")
    c.font = Font(name="Calibri", size=12, bold=True, color=_WHITE)
    c.fill = _fill(_DARK)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = _thin()
    ws.row_dimensions[r].height = 24
    r += 1

    ws.merge_cells(f"A{r}:C{r}")
    c = ws.cell(row=r, column=1,
                value=f"FORMULARIO 210  —  AÑO GRAVABLE {año}  —  "
                      f"UVT: $ {UVT_2025:,.0f}")
    c.font = Font(name="Calibri", size=11, bold=True, color=_WHITE)
    c.fill = _fill(_DARK)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = _thin()
    ws.row_dimensions[r].height = 20
    r += 1

    # Borrador banner
    ws.merge_cells(f"A{r}:C{r}")
    c = ws.cell(row=r, column=1,
                value=f"⚠  BORRADOR — NO VÁLIDO COMO DECLARACIÓN ANTE LA DIAN")
    c.font = Font(name="Calibri", size=10, bold=True, color=_RED)
    c.fill = _fill(_YELLOW)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = _thin()
    ws.row_dimensions[r].height = 18
    r += 1

    _blank(ws, r); r += 1

    # Datos del declarante
    _hdr(ws, r, "DATOS DEL DECLARANTE", _MED); r += 1
    _data(ws, r, "", "Nombre / Razón Social",  nombre, _VLIGHT); r += 1
    _data(ws, r, "", "NIT / Cédula",           nit,    _WHITE);  r += 1
    _data(ws, r, "", "Ciudad",                 ciudad, _VLIGHT); r += 1
    _data(ws, r, "", "Estado declaración",     est,    _WHITE);  r += 1
    _data(ws, r, "", "Período gravable",        año,    _VLIGHT); r += 1

    _blank(ws, r); r += 1

    # Encabezado columnas
    for col, (txt, align, w) in enumerate([
        ("CASILLA", "center", None),
        ("CONCEPTO", "left", None),
        ("VALOR  ($)", "right", None),
    ], start=1):
        c = ws.cell(row=r, column=col, value=txt)
        c.font = Font(name="Calibri", size=9, bold=True, color=_WHITE)
        c.fill = _fill(_MED)
        c.alignment = Alignment(horizontal=align, vertical="center")
        c.border = _thin()
    ws.row_dimensions[r].height = 16
    r += 1

    # ── PATRIMONIO ────────────────────────────────────────────────────────────
    _hdr(ws, r, "PATRIMONIO", _MED); r += 1
    _data(ws, r, 28, "Uno por ciento (1%) compras con factura electrónica", 0, _VLIGHT); r += 1
    _data(ws, r, 29, "Total patrimonio bruto",                  v["c29"], _WHITE);  r += 1
    _data(ws, r, 30, "Deudas",                                  v["c30"], _VLIGHT); r += 1
    _data(ws, r, 31, "Total patrimonio líquido  (29 − 30)",     v["c31"], _WHITE);  r += 1

    _blank(ws, r); r += 1

    # ── CÉDULA GENERAL ────────────────────────────────────────────────────────
    _hdr(ws, r, "CÉDULA GENERAL", _DARK); r += 1

    # RENTAS DE TRABAJO
    _hdr(ws, r, "  RENTAS DE TRABAJO  (Art. 103 ET)", _MED); r += 1
    _data(ws, r, 32, "Ingresos brutos rentas de trabajo",               v["c32"], _WHITE);  r += 1
    _data(ws, r, 33, "Ingresos no constitutivos de renta — aportes pensión", v["c33"], _VLIGHT); r += 1
    _data(ws, r, 34, "Renta líquida rentas de trabajo  (32 − 33)",      v["c34"], _WHITE);  r += 1
    _data(ws, r, 35, "Rentas exentas — AFC / FVP / AVC",                v["c35"], _VLIGHT); r += 1
    _data(ws, r, 36, "Rentas exentas — 25%  núm. 10 Art. 206 ET",       v["c36"], _WHITE);  r += 1
    _data(ws, r, 37, "Total rentas exentas rentas de trabajo  (35 + 36)", v["c37"], _VLIGHT); r += 1
    _data(ws, r, 38, "Deducciones — Intereses crédito de vivienda",     v["c38"], _WHITE);  r += 1
    _data(ws, r, 39, "Deducciones — Salud, dependientes y otras",       v["c39"], _VLIGHT); r += 1
    _data(ws, r, 40, "Total deducciones imputables  (38 + 39)",         v["c40"], _WHITE);  r += 1
    _data(ws, r, 41, "Rentas exentas y deduc. imputables LIMITADAS — 40% / 1.340 UVT  (Art. 336 ET)", v["c41"], _VLIGHT); r += 1
    _data(ws, r, 42, "Renta líquida ordinaria rentas de trabajo  (34 − 41)", v["c42"], _WHITE); r += 1

    _blank(ws, r); r += 1

    # RENTAS DE TRABAJO NO LABORALES (43-57) — no aplica, mostrar 0
    _hdr(ws, r, "  RENTAS DE TRABAJO — NO RELACIÓN LABORAL  (Art. 103 ET)", _MED); r += 1
    for cas, desc in [
        (43, "Ingresos brutos"), (44, "Ingresos no constitutivos de renta"),
        (45, "Costos y deducciones procedentes"),
        (46, "Renta líquida"), (47, "Rentas exentas — AFC / FVP / AVC"),
        (48, "Rentas exentas — 25%  núm. 10 Art. 206 ET"),
        (53, "Renta líquida ordinaria  (46 − 51 − 52)"),
    ]:
        bg = _VLIGHT if cas % 2 else _WHITE
        _data(ws, r, cas, desc, 0, bg); r += 1

    _blank(ws, r); r += 1

    # RENTAS DE CAPITAL (58-73)
    _hdr(ws, r, "  RENTAS DE CAPITAL  (Art. 58 ET)", _MED); r += 1
    _data(ws, r, 58, "Ingresos brutos rentas de capital",     v["c58"], _WHITE);  r += 1
    _data(ws, r, 59, "Ingresos no constitutivos de renta",    0, _VLIGHT); r += 1
    _data(ws, r, 60, "Costos y deducciones procedentes",      0, _WHITE);  r += 1
    _data(ws, r, 61, "Renta líquida  (58 − 59 − 60)",         max(0.0, v["c58"]), _VLIGHT); r += 1
    _data(ws, r, 65, "Total rentas exentas",                  0, _WHITE);  r += 1
    _data(ws, r, 68, "Total deducciones imputables",          0, _VLIGHT); r += 1
    _data(ws, r, 73, "Renta líquida ordinaria rentas de capital", v["c58"], _WHITE); r += 1

    _blank(ws, r); r += 1

    # RENTAS NO LABORALES (74-90)
    _hdr(ws, r, "  RENTAS NO LABORALES  (Art. 74 ET)", _MED); r += 1
    _data(ws, r, 74, "Ingresos brutos rentas no laborales",   v["c74"], _WHITE);  r += 1
    _data(ws, r, 75, "Devoluciones, rebajas y descuentos",    0, _VLIGHT); r += 1
    _data(ws, r, 76, "Ingresos no constitutivos de renta",    0, _WHITE);  r += 1
    _data(ws, r, 77, "Costos y deducciones procedentes",      0, _VLIGHT); r += 1
    _data(ws, r, 78, "Renta líquida  (74 − 75 − 76 − 77)",    max(0.0, v["c74"]), _WHITE); r += 1
    _data(ws, r, 82, "Total rentas exentas",                  0, _VLIGHT); r += 1
    _data(ws, r, 85, "Total deducciones imputables",          0, _WHITE);  r += 1
    _data(ws, r, 90, "Renta líquida ordinaria rentas no laborales", v["c74"], _VLIGHT); r += 1

    _blank(ws, r); r += 1

    # CONSOLIDADO CÉDULA GENERAL (91-97)
    _hdr(ws, r, "  CONSOLIDADO CÉDULA GENERAL", _MED); r += 1
    _data(ws, r, 91, "Renta líquida cédula general  (42 + 53 + 57 + 73 + 90)", v["c91"], _WHITE);  r += 1
    _data(ws, r, 92, "Rentas gravables cédula general",       0, _VLIGHT); r += 1
    _data(ws, r, 93, "Renta líquida ordinaria cédula general  (91 − 92)", v["c91"], _WHITE); r += 1
    _data(ws, r, 94, "Compensaciones por pérdidas año 2018 y anteriores", 0, _VLIGHT); r += 1
    _data(ws, r, 95, "Compensaciones por exceso renta presuntiva", 0, _WHITE); r += 1
    _data(ws, r, 96, "Rentas gravables",                      0, _VLIGHT); r += 1
    _data(ws, r, 97, "Renta líquida gravable cédula general  (93 + 96 − 94 − 95)", v["c97"], _WHITE); r += 1

    _blank(ws, r); r += 1

    # CÉDULA PENSIONES (98-103)
    _hdr(ws, r, "CÉDULA DE PENSIONES  (Art. 337 ET)", _DARK); r += 1
    for cas, desc in [
        (99, "Ingresos brutos por rentas de pensiones"),
        (100, "Ingresos no constitutivos de renta"),
        (101, "Renta líquida  (99 − 100)"),
        (102, "Rentas exentas de pensiones"),
        (103, "Renta líquida gravable cédula de pensiones  (101 − 102)"),
    ]:
        bg = _VLIGHT if cas % 2 else _WHITE
        _data(ws, r, cas, desc, 0, bg); r += 1

    _blank(ws, r); r += 1

    # CÉDULA DIVIDENDOS (104-111)
    _hdr(ws, r, "CÉDULA DE DIVIDENDOS Y PARTICIPACIONES  (Art. 242 ET)", _DARK); r += 1
    _data(ws, r, 104, "Dividendos y participaciones año 2016 y anteriores", 0, _WHITE);  r += 1
    _data(ws, r, 105, "Ingresos no constitutivos de renta",  0, _VLIGHT); r += 1
    _data(ws, r, 106, "Renta líquida ordinaria 2016 y anteriores  (104 − 105)", 0, _WHITE); r += 1
    _data(ws, r, 107, "1a. Subcédula años 2017 y siguientes — núm. 3 Art. 49 ET", v["c107"], _VLIGHT); r += 1
    _data(ws, r, 108, "2a. Subcédula años 2017 y siguientes — par. 2° Art. 49 ET", 0, _WHITE); r += 1
    _data(ws, r, 109, "Dividendos y participaciones recibidos del exterior", 0, _VLIGHT); r += 1
    _data(ws, r, 110, "Rentas exentas de la casilla 109",    0, _WHITE);  r += 1

    _blank(ws, r); r += 1

    # GANANCIAS OCASIONALES (112-115)
    _hdr(ws, r, "GANANCIAS OCASIONALES  (Art. 299–316 ET)", _DARK); r += 1
    _data(ws, r, 112, "Ingresos por ganancias ocasionales del país y del exterior", v["c115"], _WHITE);  r += 1
    _data(ws, r, 113, "Costos por ganancias ocasionales",    0, _VLIGHT); r += 1
    _data(ws, r, 114, "Ganancias ocasionales no gravadas y exentas", 0, _WHITE); r += 1
    _data(ws, r, 115, "Ganancias ocasionales gravables  (112 − 113 − 114)", v["c115"], _VLIGHT); r += 1

    _blank(ws, r); r += 1

    # ── LIQUIDACIÓN ───────────────────────────────────────────────────────────
    _hdr(ws, r, "LIQUIDACIÓN PRIVADA", _DARK); r += 1
    _data(ws, r, 116, "Impuesto sobre renta cédula general  (Art. 241 ET)", v["c116"], _WHITE);  r += 1
    _data(ws, r, 119, "Impuesto cédula dividendos 2016  (base casilla 106)", 0, _VLIGHT); r += 1
    _data(ws, r, 120, "Impuesto cédula dividendos 2017 y siguientes",       0, _WHITE);  r += 1
    _data(ws, r, 121, "Impuesto a cargo antes de descuentos  (116+119+120)", v["c116"], _VLIGHT); r += 1
    _data(ws, r, 122, "Descuentos tributarios — impuestos pagados exterior", 0, _WHITE);  r += 1
    _data(ws, r, 123, "Descuentos tributarios — donaciones",                0, _VLIGHT); r += 1
    _data(ws, r, 124, "Descuentos tributarios — dividendos y participaciones", 0, _WHITE); r += 1
    _data(ws, r, 125, "Total descuentos tributarios  (122 + 123 + 124)",   0, _VLIGHT); r += 1
    _data(ws, r, 126, "Impuesto neto de renta  (121 − 125)",               v["c116"], _WHITE);  r += 1
    _data(ws, r, 127, "Impuesto de ganancias ocasionales",                  v["c127"], _VLIGHT); r += 1
    _data(ws, r, 128, "Descuento impuestos pagados exterior — gan. ocasionales", 0, _WHITE); r += 1
    _data(ws, r, 129, "Total impuesto a cargo  (126 + 127 − 128)",         v["c129"], _VLIGHT); r += 1

    _blank(ws, r); r += 1

    _hdr(ws, r, "  ANTICIPO Y RETENCIONES", _MED); r += 1
    _data(ws, r, 130, "Anticipo renta liquidado año gravable anterior",    0, _WHITE);  r += 1
    _data(ws, r, 131, "Saldo a favor año gravable anterior",               0, _VLIGHT); r += 1
    _data(ws, r, 132, "Retenciones año gravable a declarar",               v["c132"], _WHITE);  r += 1
    _data(ws, r, 133, "Anticipo renta para el año gravable siguiente",     0, _VLIGHT); r += 1

    _blank(ws, r); r += 1

    _hdr(ws, r, "  SALDO A PAGAR / SALDO A FAVOR", _MED); r += 1
    _data(ws, r, 134, "Saldo a pagar por impuesto  (129+133−130−131−132)", v["c134"], _WHITE);  r += 1
    _data(ws, r, 135, "Sanciones",                                         0, _VLIGHT); r += 1
    _data(ws, r, 136, "Total saldo a pagar  (129+133+135−130−131−132)",    v["c136"], _WHITE);  r += 1
    _data(ws, r, 137, "Total saldo a favor  (130+131+132−129−133−135)",    v["c137"], _VLIGHT); r += 1

    _blank(ws, r); r += 1

    # DATOS ADICIONALES (138-141)
    _hdr(ws, r, "DATOS ADICIONALES", _MED); r += 1
    dep_count = int(declaracion.get("dependientes") or 0)
    tipo_gan  = declaracion.get("tipo_ganancia") or "—"
    _data(ws, r, 138, "Número de dependientes económicos",  dep_count, _WHITE);  r += 1
    _data(ws, r, 139, "Adición por dependientes a casilla 92", 0, _VLIGHT); r += 1
    _data(ws, r, 140, "Superó tope indicativo Art. 336-1 ET (X si aplica)", "—", _WHITE); r += 1
    _data(ws, r, 141, "Aporte voluntario", 0, _VLIGHT); r += 1

    _blank(ws, r); r += 1

    # Pie de página
    ws.merge_cells(f"A{r}:C{r}")
    c = ws.cell(row=r, column=1,
                value="Generado por TaxOps  —  Sólo para referencia interna  —  "
                      "No constituye declaración formal ante la DIAN")
    c.font = Font(name="Calibri", size=8, italic=True, color="808080")
    c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[r].height = 14

    # ── Serializar ────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
