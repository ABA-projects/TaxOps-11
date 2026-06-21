"""
Liquidación de nómina y cálculo mensual según CST Colombia.

Parámetros legales 2026:
  SMLMV: $1,750,905
  Aux transporte: $249,095 (hasta 2 × SMLMV)
  Jornada máxima: 44h/sem (Ley 2101/2021 gradual)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

# ── Parámetros legales 2026 ───────────────────────────────────────────────────
SMLMV            = 1_750_905
AUX_TRANSPORTE   = 249_095
TOPE_IBC         = SMLMV * 25      # máximo IBC (25 SMLMV)
TOPE_AUX         = SMLMV * 2       # aux transporte hasta 2 SMLMV
SALARIO_INTEGRAL = SMLMV * 13      # 10 SMLMV + 30% factor prestacional

# Porcentajes seguridad social
PCT_SALUD_EMP    = 0.04    # empleado
PCT_PENSION_EMP  = 0.04    # empleado
PCT_PENSION_PATR = 0.12    # empleador
PCT_ARL_I        = 0.00522 # nivel I (más común)

HORAS_MES        = 220     # jornada 44h/sem × (360/12/7)

# Tasas ARL por clase de riesgo (Decreto 1607/2002)
ARL_RATES = {1: 0.00522, 2: 0.01044, 3: 0.02436, 4: 0.04350, 5: 0.06960}
ARL_LABELS = {
    1: "Clase I – Riesgo mínimo (0.522%)",
    2: "Clase II – Riesgo bajo (1.044%)",
    3: "Clase III – Riesgo medio (2.436%)",
    4: "Clase IV – Riesgo alto (4.350%)",
    5: "Clase V – Riesgo máximo (6.960%)",
}

# Porcentajes carga patronal
PCT_SALUD_PATR   = 0.085   # empleador
PCT_SENA         = 0.02    # parafiscal
PCT_ICBF         = 0.03    # parafiscal
PCT_CAJA         = 0.04    # parafiscal (siempre)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fsp(ibc: float) -> float:
    """Fondo Solidaridad Pensional (escala progresiva Art. 27 Ley 100)."""
    if ibc < 4 * SMLMV:
        return 0.0
    if ibc <= 16 * SMLMV:
        return ibc * 0.01
    if ibc <= 17 * SMLMV:
        return ibc * 0.012
    if ibc <= 18 * SMLMV:
        return ibc * 0.014
    if ibc <= 19 * SMLMV:
        return ibc * 0.016
    if ibc <= 20 * SMLMV:
        return ibc * 0.018
    return ibc * 0.02


def _dias_360(d_inicio: date, d_fin: date) -> int:
    """
    Calcula días entre dos fechas en base 360 días/año (Art. 134 CST).
    Fórmula: (Y2-Y1)×360 + (M2-M1)×30 + (D2-D1) + 1
    """
    y1, m1, d1 = d_inicio.year, d_inicio.month, d_inicio.day
    y2, m2, d2 = d_fin.year, d_fin.month, d_fin.day
    return (y2 - y1) * 360 + (m2 - m1) * 30 + (d2 - d1) + 1


def _redondear(v: float) -> int:
    """Redondea al entero más cercano (pesos colombianos)."""
    return int(round(v))


# ── Nómina mensual ────────────────────────────────────────────────────────────

@dataclass
class EntradaNomina:
    """Datos de entrada para liquidar una nómina mensual."""
    salario_basico:     float
    dias_trabajados:    int   = 30
    # Horas extras y recargos (cantidad de horas)
    hed:  float = 0.0   # Extra Diurna +25%
    hen:  float = 0.0   # Extra Nocturna +75%
    rn:   float = 0.0   # Recargo Nocturno +35%
    hod:  float = 0.0   # Dominical/Festivo +75%
    hedd: float = 0.0   # Extra Diurna Dominical +100%
    hend: float = 0.0   # Extra Nocturna Dominical +150%
    rnd:  float = 0.0   # Recargo Nocturno Dominical +110%
    # Otros devengados
    bonificaciones_salariales:    float = 0.0
    comisiones:                   float = 0.0
    otros_no_salariales:          float = 0.0
    # Deducciones manuales
    retencion_fuente:             float = 0.0
    otras_deducciones:            float = 0.0
    clase_riesgo_arl:             int   = 1   # 1=mínimo .. 5=máximo
    tipo_salario: Literal["ordinario", "integral"] = "ordinario"


@dataclass
class ResultadoNomina:
    """Resultado del cálculo de nómina mensual."""
    # Devengado
    salario_proporcional:    int
    auxilio_transporte:      int
    he_hed:  int
    he_hen:  int
    he_rn:   int
    he_hod:  int
    he_hedd: int
    he_hend: int
    he_rnd:  int
    subtotal_horas_extras:   int
    bonificaciones:          int
    comisiones:              int
    otros_no_salariales:     int
    total_devengado:         int
    # Deducciones
    ibc:                     int
    salud_empleado:          int
    pension_empleado:        int
    fsp:                     int
    retencion_fuente:        int
    otras_deducciones:       int
    total_deducciones:       int
    # Neto
    neto_pagar:              int
    # Carga patronal completa (informativa)
    pension_empleador:       int
    arl:                     int
    salud_empleador:         int
    sena:                    int
    icbf:                    int
    caja_compensacion:       int
    exonerado_sena_icbf:     bool   # Art. 114-1 ET: salarios ≤10 SMLMV
    total_carga_patronal:    int
    costo_total_empresa:     int    # total_devengado + total_carga_patronal
    aplica_aux_transporte:   bool


def calcular_nomina(e: EntradaNomina) -> ResultadoNomina:
    s = e.salario_basico
    integral = e.tipo_salario == "integral"

    # Salario proporcional
    sal_prop = _redondear(s / 30 * e.dias_trabajados)

    # Auxilio de transporte (no aplica a salario integral ni a salarios > 2 SMLMV)
    aplica_aux = not integral and s <= TOPE_AUX
    aux = _redondear(AUX_TRANSPORTE / 30 * e.dias_trabajados) if aplica_aux else 0

    # Valor hora ordinaria
    vh = s / HORAS_MES

    # Horas extras y recargos (Art. 168 CST · Ley 2466/2025 jul-2025→jun-2026)
    hed_v  = _redondear(e.hed  * vh * 1.25)
    hen_v  = _redondear(e.hen  * vh * 1.80)  # 75% → 80%
    rn_v   = _redondear(e.rn   * vh * 1.35)
    hod_v  = _redondear(e.hod  * vh * 1.80)  # 75% → 80%
    hedd_v = _redondear(e.hedd * vh * 2.05)  # 100% → 105%
    hend_v = _redondear(e.hend * vh * 2.55)  # 150% → 155%
    rnd_v  = _redondear(e.rnd  * vh * 2.15)  # 110% → 115%
    subtotal_he = hed_v + hen_v + rn_v + hod_v + hedd_v + hend_v + rnd_v

    bonif = _redondear(e.bonificaciones_salariales)
    comis = _redondear(e.comisiones)
    otros = _redondear(e.otros_no_salariales)

    total_dev = sal_prop + aux + subtotal_he + bonif + comis + otros

    # IBC = salario + HE + bonif + comisiones (sin aux transporte ni no salariales)
    # Para salario integral el IBC es el 70% del salario (factor salarial)
    if integral:
        ibc = _redondear(min(s * 0.70, TOPE_IBC))
        salud_emp = 0   # integral paga completo pero está incluido en el 30%
        pension_emp = 0
        fsp_v = 0
    else:
        ibc = _redondear(min(sal_prop + subtotal_he + bonif + comis, TOPE_IBC))
        salud_emp   = _redondear(ibc * PCT_SALUD_EMP)
        pension_emp = _redondear(ibc * PCT_PENSION_EMP)
        fsp_v       = _redondear(_fsp(ibc))

    retf = _redondear(e.retencion_fuente)
    otras_ded = _redondear(e.otras_deducciones)
    total_ded = salud_emp + pension_emp + fsp_v + retf + otras_ded
    neto = total_dev - total_ded

    # Carga patronal completa
    arl_rate     = ARL_RATES.get(int(e.clase_riesgo_arl), ARL_RATES[1])
    pension_patr = _redondear(ibc * PCT_PENSION_PATR)
    arl_v        = _redondear(ibc * arl_rate)
    salud_patr   = _redondear(ibc * PCT_SALUD_PATR)
    # Exoneración SENA e ICBF (Art. 114-1 ET, Ley 1607/2012)
    # Aplica cuando: contrato indefinido/ordinario y salario ≤ 10 SMLMV
    exonerado    = not integral and ibc <= 10 * SMLMV
    sena_v       = 0 if exonerado else _redondear(ibc * PCT_SENA)
    icbf_v       = 0 if exonerado else _redondear(ibc * PCT_ICBF)
    caja_v       = _redondear(ibc * PCT_CAJA)
    total_carga  = pension_patr + arl_v + salud_patr + sena_v + icbf_v + caja_v
    costo_empresa = total_dev + total_carga

    return ResultadoNomina(
        salario_proporcional  = sal_prop,
        auxilio_transporte    = aux,
        he_hed=hed_v, he_hen=hen_v, he_rn=rn_v,
        he_hod=hod_v, he_hedd=hedd_v, he_hend=hend_v, he_rnd=rnd_v,
        subtotal_horas_extras = subtotal_he,
        bonificaciones        = bonif,
        comisiones            = comis,
        otros_no_salariales   = otros,
        total_devengado       = total_dev,
        ibc                   = ibc,
        salud_empleado        = salud_emp,
        pension_empleado      = pension_emp,
        fsp                   = fsp_v,
        retencion_fuente      = retf,
        otras_deducciones     = otras_ded,
        total_deducciones     = total_ded,
        neto_pagar            = neto,
        pension_empleador     = pension_patr,
        arl                   = arl_v,
        salud_empleador       = salud_patr,
        sena                  = sena_v,
        icbf                  = icbf_v,
        caja_compensacion     = caja_v,
        exonerado_sena_icbf   = exonerado,
        total_carga_patronal  = total_carga,
        costo_total_empresa   = costo_empresa,
        aplica_aux_transporte = aplica_aux,
    )


# ── Liquidación definitiva ────────────────────────────────────────────────────

TipoContrato     = Literal["indefinido", "termino_fijo", "obra_labor"]
CausaTerminacion = Literal[
    "renuncia",
    "sin_justa_causa_empleador",
    "justa_causa",
    "mutuo_acuerdo",
    "vencimiento",
]


@dataclass
class EntradaLiquidacion:
    salario_basico:           float
    fecha_ingreso:            date
    fecha_retiro:             date
    tipo_contrato:            TipoContrato      = "indefinido"
    causa_terminacion:        CausaTerminacion  = "renuncia"
    # Promedios del último año (variables salariales)
    promedio_he_recargos:     float = 0.0
    promedio_bonif_salariales: float = 0.0
    # Días ya disfrutados de vacaciones
    dias_vacaciones_disfrutadas: float = 0.0
    # Anticipos/consignaciones previas (descuentan del total)
    anticipo_cesantias:       float = 0.0
    # Deducciones finales (préstamos, embargos, etc.)
    otras_deducciones:        float = 0.0
    tipo_salario: Literal["ordinario", "integral"] = "ordinario"


@dataclass
class ResultadoLiquidacion:
    # Tiempo
    dias_trabajados:        int
    # Bases
    salario_base_prestacional: int   # incluye aux transporte
    salario_base_vacaciones:   int   # sin aux transporte
    salario_base_indemnizacion: int
    aplica_aux_transporte:  bool
    # Prestaciones
    cesantias:              int
    intereses_cesantias:    int
    prima_servicios:        int
    vacaciones_proporcionales: int
    vacaciones_pendientes:  int   # días pendientes × vacaciones por día
    # Indemnización
    indemnizacion:          int
    causa_indemnizacion:    str
    # Últimos pagos
    salario_pendiente:      int   # días proporcionales del último mes
    # Totales
    subtotal_devengado:     int
    otras_deducciones:      int
    total_neto:             int
    # Detalle días para auditoría
    dias_cesantias:         int
    dias_prima:             int
    dias_vacaciones_causadas: float
    dias_vacaciones_a_pagar:  float


def calcular_liquidacion(e: EntradaLiquidacion) -> ResultadoLiquidacion:
    s     = e.salario_basico
    fi    = e.fecha_ingreso
    fr    = e.fecha_retiro
    integral = e.tipo_salario == "integral"

    dias_total = _dias_360(fi, fr)

    aplica_aux = not integral and s <= TOPE_AUX
    aux = AUX_TRANSPORTE if aplica_aux else 0

    # Bases de liquidación
    base_prestacional = s + e.promedio_he_recargos + e.promedio_bonif_salariales + aux
    base_vacaciones   = s + e.promedio_he_recargos + e.promedio_bonif_salariales
    base_indem        = base_vacaciones

    # ── Cesantías (Art. 249 CST) ──────────────────────────────────────────────
    # Días: desde 1/ene del año de retiro hasta fecha retiro (o fecha ingreso si menor)
    inicio_ces = max(fi, date(fr.year, 1, 1))
    dias_ces   = _dias_360(inicio_ces, fr)
    cesantias  = _redondear(base_prestacional * dias_ces / 360)
    cesantias  -= _redondear(e.anticipo_cesantias)
    cesantias  = max(0, cesantias)

    # ── Intereses sobre cesantías (Ley 52/1975) ───────────────────────────────
    intereses = _redondear(cesantias * dias_ces * 0.12 / 360)

    # ── Prima de servicios (Art. 306 CST) ─────────────────────────────────────
    # Semestral: 1/ene–30/jun y 1/jul–31/dic
    if fr.month <= 6:
        inicio_prima = max(fi, date(fr.year, 1, 1))
    else:
        inicio_prima = max(fi, date(fr.year, 7, 1))
    dias_prima = _dias_360(inicio_prima, fr)
    prima      = _redondear(base_prestacional * dias_prima / 360)

    # ── Vacaciones (Art. 186 CST) ─────────────────────────────────────────────
    # 15 días hábiles por año trabajado = 15/360 por día
    dias_vac_causadas = dias_total * 15 / 360
    dias_vac_pagar    = max(0.0, dias_vac_causadas - e.dias_vacaciones_disfrutadas)
    # Vacaciones proporcionales: días pendientes × salario_diario_vacaciones
    # salario_diario_vacaciones = base_vacaciones / 30
    vac_prop = _redondear(base_vacaciones / 30 * dias_vac_pagar)
    # Si hay vacaciones pendientes no disfrutadas (diferente de la proporción)
    vac_pendientes = 0  # incluidas en vac_prop

    # ── Salario pendiente del último periodo ──────────────────────────────────
    # Días del mes de retiro transcurridos
    inicio_ultimo_mes = date(fr.year, fr.month, 1)
    dias_ultimo = _dias_360(inicio_ultimo_mes, fr)
    sal_pendiente = _redondear(s / 30 * dias_ultimo)
    if aplica_aux:
        sal_pendiente += _redondear(AUX_TRANSPORTE / 30 * dias_ultimo)

    # ── Indemnización (Art. 64 CST) ───────────────────────────────────────────
    indem = 0
    causa_txt = ""
    if e.causa_terminacion == "sin_justa_causa_empleador":
        anos = dias_total / 360
        if anos < 1:
            # Menos de 1 año → 30 días de salario
            indem = _redondear(base_indem)
            causa_txt = "< 1 año: 30 días de salario"
        else:
            # ≥ 1 año → 20 días + 15 días por año adicional (fracción proporcional)
            base_20 = _redondear(base_indem * 20 / 30)
            adicional = _redondear(base_indem * 15 / 30 * (anos - 1))
            indem = base_20 + adicional
            causa_txt = f"≥1 año: 20 días + 15/año adicional ({round(anos, 2)} años)"
    else:
        causa_txt = "No aplica indemnización"

    # ── Totales ───────────────────────────────────────────────────────────────
    subtotal = cesantias + intereses + prima + vac_prop + indem + sal_pendiente
    otras_ded = _redondear(e.otras_deducciones)
    total_neto = subtotal - otras_ded

    return ResultadoLiquidacion(
        dias_trabajados              = dias_total,
        salario_base_prestacional    = _redondear(base_prestacional),
        salario_base_vacaciones      = _redondear(base_vacaciones),
        salario_base_indemnizacion   = _redondear(base_indem),
        aplica_aux_transporte        = aplica_aux,
        cesantias                    = cesantias,
        intereses_cesantias          = intereses,
        prima_servicios              = prima,
        vacaciones_proporcionales    = vac_prop,
        vacaciones_pendientes        = vac_pendientes,
        indemnizacion                = indem,
        causa_indemnizacion          = causa_txt,
        salario_pendiente            = sal_pendiente,
        subtotal_devengado           = subtotal,
        otras_deducciones            = otras_ded,
        total_neto                   = total_neto,
        dias_cesantias               = dias_ces,
        dias_prima                   = dias_prima,
        dias_vacaciones_causadas     = round(dias_vac_causadas, 2),
        dias_vacaciones_a_pagar      = round(dias_vac_pagar, 2),
    )
