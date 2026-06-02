"""Genera borrador del Formulario 210 DIAN como PDF usando WeasyPrint."""
from __future__ import annotations


def generar_pdf(declaracion: dict, contribuyente: dict) -> bytes:
    from weasyprint import HTML
    html = _render_html(declaracion, contribuyente)
    return HTML(string=html, base_url=None).write_pdf()


def _fmt(v) -> str:
    try:
        return f"$ {float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "$ 0"


def _render_html(decl: dict, contrib: dict) -> str:
    uvt = (decl.get("detalle_calculo") or {}).get("uvt", 49799)
    ajustados = ((decl.get("detalle_calculo") or {}).get("ajustados_manualmente") or [])

    def cas(num: str, campo: str, label: str) -> str:
        val = decl.get(campo, 0) or 0
        manual_mark = " ⚠️" if campo in ajustados else ""
        return f"""
        <tr>
          <td class="cas-num">{num}</td>
          <td class="cas-label">{label}{manual_mark}</td>
          <td class="cas-val">{_fmt(val)}</td>
        </tr>"""

    tipo_ganancia = decl.get("tipo_ganancia") or "venta_activo"
    saldo_pagar = float(decl.get("saldo_pagar") or 0)
    saldo_favor = float(decl.get("saldo_favor") or 0)
    updated_at = str(decl.get("updated_at") or "")[:10]

    if saldo_pagar > 0:
        saldo_row = f"""
        <tr class="saldo-pagar">
          <td class="cas-num">138</td>
          <td class="cas-label">Saldo a pagar</td>
          <td class="cas-val">{_fmt(saldo_pagar)}</td>
        </tr>"""
    else:
        saldo_row = f"""
        <tr class="saldo-favor">
          <td class="cas-num">137</td>
          <td class="cas-label">Saldo a favor</td>
          <td class="cas-val">{_fmt(saldo_favor)}</td>
        </tr>"""

    ajustados_nota = ""
    if ajustados:
        ajustados_nota = f'<p class="nota-ajuste">⚠️ Campos con ajuste manual: {", ".join(ajustados)}</p>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ font-family: Arial, sans-serif; font-size: 9pt; color: #111; }}
  h1 {{ font-size: 13pt; text-align: center; margin: 0 0 4px; }}
  h2 {{ font-size: 10pt; text-align: center; color: #444; margin: 0 0 12px; }}
  .header-box {{ border: 2px solid #222; padding: 8px 12px; margin-bottom: 14px; }}
  .seccion {{ margin-bottom: 12px; }}
  .seccion h3 {{ font-size: 9pt; background: #1e3a5f; color: white; padding: 3px 6px; margin: 0 0 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 2px 4px; border-bottom: 1px solid #ddd; vertical-align: top; }}
  .cas-num {{ width: 30px; font-weight: bold; color: #1e3a5f; }}
  .cas-label {{ width: 60%; }}
  .cas-val {{ text-align: right; font-weight: bold; }}
  .total-row td {{ background: #f0f4ff; font-weight: bold; border-top: 2px solid #1e3a5f; }}
  .saldo-pagar td {{ background: #fff0f0; color: #b00; font-weight: bold; }}
  .saldo-favor td {{ background: #f0fff4; color: #090; font-weight: bold; }}
  .watermark {{
    position: fixed; top: 40%; left: 10%; width: 80%;
    font-size: 72pt; color: rgba(200,0,0,0.08);
    transform: rotate(-35deg); text-align: center;
    font-weight: 900; pointer-events: none; z-index: 0;
  }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; }}
  .info-item {{ font-size: 8pt; }}
  .info-item span {{ font-weight: bold; }}
  .nota-ajuste {{ font-size: 7pt; color: orange; margin: 2px 0; }}
  .pie {{ font-size: 7pt; color: #888; margin-top: 16px; text-align: center; }}
</style>
</head>
<body>
<div class="watermark">BORRADOR</div>

<div class="header-box">
  <h1>DECLARACIÓN DE RENTA Y COMPLEMENTARIO</h1>
  <h2>Personas Naturales y Asimiladas Residentes — Formulario 210</h2>
  <div class="info-grid">
    <div class="info-item">Año gravable: <span>{decl.get("año_gravable", "")}</span></div>
    <div class="info-item">Estado: <span>{str(decl.get("estado", "borrador")).upper()}</span></div>
    <div class="info-item">Nombre: <span>{contrib.get("nombre_completo", "")}</span></div>
    <div class="info-item">NIT/Cédula: <span>{contrib.get("numero_doc", "")}</span></div>
    <div class="info-item">Ciudad: <span>{contrib.get("ciudad", "")}</span></div>
    <div class="info-item">UVT: <span>{_fmt(uvt)}</span></div>
  </div>
</div>

<div class="seccion">
  <h3>PATRIMONIO</h3>
  <table>
    {cas("29", "patrimonio_bruto", "Total patrimonio bruto")}
    {cas("30", "pasivos", "Deudas")}
    {cas("31", "patrimonio_liquido", "Total patrimonio líquido")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA GENERAL — RENTAS DE TRABAJO (Art. 103 ET)</h3>
  <table>
    {cas("32", "ingresos_laborales", "Ingresos brutos rentas de trabajo")}
    {cas("33", "aportes_pension", "Ingresos no constitutivos — aportes pensión")}
    {cas("35", "afc_fvp", "Rentas exentas — AFC / FVP / AVC")}
    {cas("36", "rentas_exentas", "Rentas exentas — 25% num. 10 Art. 206 ET")}
    {cas("38", "intereses_vivienda", "Deducciones — Intereses crédito vivienda")}
    {cas("39", "deducciones", "Deducciones — Salud y dependientes")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA GENERAL — RENTAS DE CAPITAL (Art. 58 ET)</h3>
  <table>
    {cas("58", "rentas_capital", "Ingresos brutos rentas de capital")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA GENERAL — RENTAS NO LABORALES (Art. 74 ET)</h3>
  <table>
    {cas("74", "rentas_no_laborales", "Ingresos brutos rentas no laborales")}
  </table>
</div>

<div class="seccion">
  <h3>CÉDULA DE DIVIDENDOS Y PARTICIPACIONES (Art. 242 ET)</h3>
  <table>
    {cas("107", "dividendos", "Dividendos gravados 2017 y siguientes")}
  </table>
</div>

<div class="seccion">
  <h3>GANANCIAS OCASIONALES (Art. 299-316 ET)</h3>
  <table>
    {cas("111", "ganancias_ocasionales", f"Ingresos ganancias ocasionales ({tipo_ganancia})")}
  </table>
</div>

<div class="seccion">
  <h3>LIQUIDACIÓN</h3>
  <table>
    <tr class="total-row">
      <td class="cas-num">116</td>
      <td class="cas-label">Total impuesto sobre rentas líquidas gravables</td>
      <td class="cas-val">{_fmt(decl.get("impuesto_cargo", 0))}</td>
    </tr>
    {cas("132", "retenciones", "Retenciones en la fuente año gravable")}
    {saldo_row}
  </table>
</div>

{ajustados_nota}
<p class="pie">Borrador generado por TaxOps · {updated_at} · No válido como declaración ante DIAN</p>
</body>
</html>"""
