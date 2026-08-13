"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  Calculator, FileText, ChevronDown, ChevronUp,
  Download, BarChart3, TrendingUp, AlertCircle,
  Users, Plus, Trash2, Upload, UserCheck, Printer,
  Calendar, Mail, Send, RefreshCw,
} from "lucide-react";
import { useApi } from "@/lib/api";
import { PageChatbot } from "@/components/PageChatbot";

const SMLMV = 1_750_905;
const AUX_T = 249_095;
const COP = (n: number) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);
const NUM = (n: number) => n.toLocaleString("es-CO");

const SALARY_PRESETS = [
  { label: "1 SMLMV",  value: SMLMV },
  { label: "2 SMLMV",  value: SMLMV * 2 },
  { label: "3 SMLMV",  value: SMLMV * 3 },
  { label: "5 SMLMV",  value: SMLMV * 5 },
  { label: "10 SMLMV", value: SMLMV * 10 },
  { label: "Integral", value: SMLMV * 13 },
];

type TabType = "mensual" | "liquidacion" | "analitica" | "empleados" | "periodos";

type CargaPatronal = {
  pension: number; salud_empleador: number; arl: number;
  sena: number; icbf: number; caja_compensacion: number;
  exonerado_sena_icbf: boolean; total: number; costo_total_empresa: number;
};
type ResultadoMensual = {
  devengado: {
    salario_proporcional: number; auxilio_transporte: number; aplica_aux_transporte: boolean;
    horas_extras: Record<string, number>; bonificaciones: number;
    comisiones: number; otros_no_salariales: number; total_devengado: number;
  };
  deducciones: {
    ibc: number; salud_empleado: number; pension_empleado: number;
    fsp: number; retencion_fuente: number; otras: number; total_deducciones: number;
  };
  carga_patronal: CargaPatronal;
  neto_pagar: number;
};
type ResultadoLiq = {
  tiempo: { fecha_ingreso: string; fecha_retiro: string; dias_trabajados: number };
  bases: { salario_base_prestacional: number; salario_base_vacaciones: number; aplica_aux_transporte: boolean };
  prestaciones: { cesantias: number; intereses_cesantias: number; prima_servicios: number; vacaciones: number; salario_pendiente: number };
  indemnizacion: { valor: number; detalle: string };
  dias_auditoria: { cesantias: number; prima: number; vacaciones_causadas: number; vacaciones_a_pagar: number };
  totales: { subtotal_devengado: number; deducciones: number; total_neto: number };
};

type Empleado = {
  id: string; nombre: string; cedula: string; cargo: string;
  salario: number; clase_riesgo_arl: number; tipo_salario: string;
  fecha_ingreso: string; email: string;
};
type PeriodoResumen = {
  id: string; periodo: string; estado: string; empleados_count: number;
  total_devengado: number; total_neto: number; carga_patronal: number; costo_empresa: number;
};
type PeriodoDetalle = PeriodoResumen & {
  detalle: Array<{
    empleado_id: string; nombre: string; cedula: string; cargo: string;
    email: string; salario: number; devengado: number; neto: number;
    carga: number; costo: number; error?: string;
  }>;
};
type BatchRow = {
  nombre: string; salario: number; neto: number; carga: number; costo: number; error?: string;
};

// empleados ahora viven en PostgreSQL — localStorage solo se usa para historial de cálculos locales

type HistEntry = {
  id: string; tipo: "mensual" | "liquidacion"; ts: string;
  salario: number; neto: number; carga?: number; costo?: number;
};
const HIST_KEY = "taxops_nomina_history";
function loadHist(): HistEntry[] {
  try { return JSON.parse(localStorage.getItem(HIST_KEY) || "[]"); } catch { return []; }
}
function saveHist(e: HistEntry) {
  const arr = loadHist().slice(0, 19); arr.unshift(e);
  localStorage.setItem(HIST_KEY, JSON.stringify(arr));
}

function Row({ label, value, bold, sub }: { label: string; value: string | number; bold?: boolean; sub?: boolean }) {
  const v = typeof value === "number" ? COP(value) : value;
  return (
    <div className={`flex justify-between py-1.5 border-b border-gray-100 dark:border-slate-700 text-sm ${bold ? "font-semibold" : ""} ${sub ? "text-xs opacity-75" : ""}`}>
      <span className="text-gray-600 dark:text-gray-300">{label}</span>
      <span className={bold ? "text-gray-900 dark:text-white" : "text-gray-800 dark:text-gray-200"}>{v}</span>
    </div>
  );
}
function Section({ title, children, accent = false }: { title: string; children: React.ReactNode; accent?: boolean }) {
  return (
    <div className={`card mb-4 ${accent ? "border-l-4 border-l-brand-orange" : ""}`}>
      <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-widest">{title}</h3>
      {children}
    </div>
  );
}

function SalaryPresets({ onSelect, currentVal }: { onSelect: (v: number) => void; currentVal: string }) {
  const num = parseFloat(currentVal.replace(/\./g, "").replace(",", ".")) || 0;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2 mb-1">
      {SALARY_PRESETS.map((p) => (
        <button key={p.label} type="button" onClick={() => onSelect(p.value)}
          className={`px-2.5 py-1 text-xs rounded-lg font-medium border transition-colors ${
            Math.abs(num - p.value) < 500
              ? "bg-brand-orange text-white border-brand-orange"
              : "bg-gray-50 dark:bg-slate-700 border-gray-200 dark:border-slate-600 text-gray-600 dark:text-gray-300 hover:border-brand-orange hover:text-brand-orange"
          }`}>
          {p.label}
        </button>
      ))}
    </div>
  );
}

function MiniBarChart({ data }: { data: { label: string; neto: number; carga: number }[] }) {
  const max = Math.max(...data.flatMap((d) => [d.neto, d.carga]), 1);
  const pct = (v: number) => Math.max(2, Math.round((v / max) * 100));
  return (
    <div className="overflow-x-auto">
      <div className="flex gap-3 items-end min-w-0" style={{ minHeight: 100 }}>
        {data.map((d, i) => (
          <div key={i} className="flex flex-col items-center gap-1 flex-1 min-w-[48px]">
            <div className="flex items-end gap-0.5 w-full justify-center" style={{ height: 80 }}>
              <div title={`Neto: ${COP(d.neto)}`} className="bg-brand-orange rounded-t w-4 transition-all duration-500" style={{ height: `${pct(d.neto)}%` }} />
              <div title={`Carga: ${COP(d.carga)}`} className="bg-blue-400 rounded-t w-4 transition-all duration-500" style={{ height: `${pct(d.carga)}%` }} />
            </div>
            <span className="text-[9px] text-gray-400 text-center leading-tight">{d.label}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-4 mt-2 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-brand-orange inline-block" /> Neto a pagar</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-blue-400 inline-block" /> Carga patronal</span>
      </div>
    </div>
  );
}

const NOMINA_SYSTEM = `Eres TaxOps Asistente de Nómina, experto en legislación laboral colombiana (CST 2026).
Puedes ayudar con:
- Cálculo de nómina mensual (salario, HE, parafiscales, IBC, SMLMV $1,750,905)
- Liquidación definitiva (cesantías, intereses, prima, vacaciones, indemnización Art.64 CST)
- Parafiscales: SENA 2%, ICBF 3%, Caja 4%, ARL (clase I-V), Salud empleador 8.5%, Pensión patronal 12%
- Exoneración SENA+ICBF para salarios ≤10 SMLMV (Art.114-1 ET, Ley 1607/2012)
- Tipos de horas extras: HED +25%, HEN +75%, RN +35%, HOD +75%, HEDD +100%, HEND +150%, RND +110%
- Ley 2101/2021 (reducción jornada gradual 44h/sem)
- FSP: aplica IBC ≥4 SMLMV · Aux. transporte $249,095 hasta ≤2 SMLMV
Responde en español, de forma clara y concisa.`;

export default function NominaPage() {
  const { get, post, put, del, postForm, getBlob } = useApi();
  const [tab, setTab] = useState<TabType>("mensual");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<"excel" | "pdf" | null>(null);
  const [error, setError] = useState("");
  const [resultMensual, setResultMensual] = useState<ResultadoMensual | null>(null);
  const [resultLiq, setResultLiq] = useState<ResultadoLiq | null>(null);
  const [showHE, setShowHE] = useState(false);
  const [history, setHistory] = useState<HistEntry[]>([]);
  const [empleados, setEmpleados] = useState<Empleado[]>([]);
  const [empLoading, setEmpLoading] = useState(false);
  const [showNewEmp, setShowNewEmp] = useState(false);
  const [editingEmp, setEditingEmp] = useState<string | null>(null);
  const [nuevoEmp, setNuevoEmp] = useState<Omit<Empleado, "id">>({
    nombre: "", cedula: "", cargo: "", salario: SMLMV,
    clase_riesgo_arl: 1, tipo_salario: "ordinario", fecha_ingreso: "", email: "",
  });
  const [batchResults, setBatchResults] = useState<BatchRow[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  // Períodos
  const [periodos, setPeriodos] = useState<PeriodoResumen[]>([]);
  const [periodoActual, setPeriodoActual] = useState(() => {
    const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
  });
  const [periodoDias, setPeriodoDias] = useState("30");
  const [periodoLoading, setPeriodoLoading] = useState(false);
  const [periodoDetalle, setPeriodoDetalle] = useState<PeriodoDetalle | null>(null);
  const [emailLoading, setEmailLoading] = useState(false);
  // Prima semestral
  const [primaAnio, setPrimaAnio] = useState(() => String(new Date().getFullYear()));
  const [primaSem, setPrimaSem] = useState<"S1"|"S2">(() => new Date().getMonth() < 6 ? "S1" : "S2");
  const [primaDias, setPrimaDias] = useState("180");
  const [primaLoading, setPrimaLoading] = useState(false);
  const [primaResult, setPrimaResult] = useState<{semestre:string; empleados_count:number; total_prima:number; fecha_pago_limite:string; detalle: Array<{empleado_id:string;nombre:string;cedula:string;salario:number;base_liquidacion:number;dias_trabajados:number;prima:number;error?:string}>} | null>(null);

  const fetchEmpleados = useCallback(async () => {
    setEmpLoading(true);
    try { setEmpleados(await get<Empleado[]>("/nomina/empleados")); }
    catch { /* silencioso si no hay DB */ }
    finally { setEmpLoading(false); }
  }, [get]);

  const fetchPeriodos = useCallback(async () => {
    try { setPeriodos(await get<PeriodoResumen[]>("/nomina/periodos")); }
    catch { /* silencioso si no hay DB */ }
  }, [get]);

  useEffect(() => {
    setHistory(loadHist());
    fetchEmpleados();
    fetchPeriodos();
  }, []); // eslint-disable-line

  const [mensual, setMensual] = useState({
    salario_basico: "", dias_trabajados: "30", clase_riesgo_arl: "1",
    hed: "0", hen: "0", rn: "0", hod: "0", hedd: "0", hend: "0", rnd: "0",
    bonificaciones_salariales: "0", comisiones: "0",
    otros_no_salariales: "0", retencion_fuente: "0", otras_deducciones: "0",
    tipo_salario: "ordinario",
  });
  const [liq, setLiq] = useState({
    salario_basico: "", fecha_ingreso: "", fecha_retiro: "",
    tipo_contrato: "indefinido", causa_terminacion: "renuncia",
    promedio_he_recargos: "0", promedio_bonif_salariales: "0",
    dias_vacaciones_disfrutadas: "0", anticipo_cesantias: "0",
    otras_deducciones: "0", tipo_salario: "ordinario",
  });

  const num = (v: string) => parseFloat(v.replace(/\./g, "").replace(",", ".")) || 0;
  const setM = (k: string, v: string) => setMensual((p) => ({ ...p, [k]: v }));
  const setL = (k: string, v: string) => setLiq((p) => ({ ...p, [k]: v }));

  async function calcularMensual() {
    if (!mensual.salario_basico) { setError("Ingresa el salario básico"); return; }
    setError(""); setLoading(true);
    try {
      const body = {
        ...mensual, salario_basico: num(mensual.salario_basico),
        dias_trabajados: parseInt(mensual.dias_trabajados), clase_riesgo_arl: parseInt(mensual.clase_riesgo_arl),
        hed: num(mensual.hed), hen: num(mensual.hen), rn: num(mensual.rn),
        hod: num(mensual.hod), hedd: num(mensual.hedd), hend: num(mensual.hend), rnd: num(mensual.rnd),
        bonificaciones_salariales: num(mensual.bonificaciones_salariales),
        comisiones: num(mensual.comisiones), otros_no_salariales: num(mensual.otros_no_salariales),
        retencion_fuente: num(mensual.retencion_fuente), otras_deducciones: num(mensual.otras_deducciones),
      };
      const data = await post<ResultadoMensual>("/nomina/mensual", body);
      setResultMensual(data);
      saveHist({ id: crypto.randomUUID(), tipo: "mensual", ts: new Date().toISOString(),
        salario: num(mensual.salario_basico), neto: data.neto_pagar,
        carga: data.carga_patronal.total, costo: data.carga_patronal.costo_total_empresa });
      setHistory(loadHist());
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error al calcular"); }
    finally { setLoading(false); }
  }

  async function calcularLiq() {
    if (!liq.salario_basico || !liq.fecha_ingreso || !liq.fecha_retiro) {
      setError("Completa salario, fecha ingreso y fecha retiro"); return;
    }
    setError(""); setLoading(true);
    try {
      const body = {
        ...liq, salario_basico: num(liq.salario_basico),
        promedio_he_recargos: num(liq.promedio_he_recargos),
        promedio_bonif_salariales: num(liq.promedio_bonif_salariales),
        dias_vacaciones_disfrutadas: num(liq.dias_vacaciones_disfrutadas),
        anticipo_cesantias: num(liq.anticipo_cesantias), otras_deducciones: num(liq.otras_deducciones),
      };
      const data = await post<ResultadoLiq>("/nomina/liquidacion", body);
      setResultLiq(data);
      saveHist({ id: crypto.randomUUID(), tipo: "liquidacion", ts: new Date().toISOString(),
        salario: num(liq.salario_basico), neto: data.totales.total_neto });
      setHistory(loadHist());
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error al calcular"); }
    finally { setLoading(false); }
  }

  const exportExcel = useCallback(async (tipo: "mensual" | "liquidacion") => {
    setExporting("excel");
    try {
      const body = tipo === "mensual"
        ? { tipo, ...mensual, salario_basico: num(mensual.salario_basico),
            dias_trabajados: parseInt(mensual.dias_trabajados), clase_riesgo_arl: parseInt(mensual.clase_riesgo_arl) }
        : { tipo, ...liq, salario_basico: num(liq.salario_basico) };
      const blob = await post<Blob>("/nomina/export", body, true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `taxops_nomina_${tipo}_${new Date().toISOString().slice(0,10)}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error exportando Excel"); }
    finally { setExporting(null); }
  }, [mensual, liq, post]);

  const exportPDF = useCallback(async (tipo: "mensual" | "liquidacion") => {
    setExporting("pdf");
    try {
      const body = tipo === "mensual"
        ? { tipo, ...mensual, salario_basico: num(mensual.salario_basico),
            dias_trabajados: parseInt(mensual.dias_trabajados), clase_riesgo_arl: parseInt(mensual.clase_riesgo_arl) }
        : { tipo, ...liq, salario_basico: num(liq.salario_basico) };
      const blob = await post<Blob>("/nomina/export-pdf", body, true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `taxops_nomina_${tipo}_${new Date().toISOString().slice(0,10)}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error generando PDF"); }
    finally { setExporting(null); }
  }, [mensual, liq, post]);

  function ExportButtons({ tipo }: { tipo: "mensual" | "liquidacion" }) {
    const hasResult = tipo === "mensual" ? !!resultMensual : !!resultLiq;
    if (!hasResult) return null;
    return (
      <div className="flex gap-3 mb-4">
        <button onClick={() => exportExcel(tipo)} disabled={!!exporting}
          className="flex items-center gap-1.5 text-sm text-brand-orange hover:text-orange-700 font-medium transition-colors disabled:opacity-50">
          <Download size={15} />{exporting === "excel" ? "Generando..." : "Descargar Excel"}
        </button>
        <span className="text-gray-300 dark:text-slate-600">|</span>
        <button onClick={() => exportPDF(tipo)} disabled={!!exporting}
          className="flex items-center gap-1.5 text-sm text-brand-navy dark:text-blue-400 hover:opacity-75 font-medium transition-colors disabled:opacity-50">
          <Printer size={15} />{exporting === "pdf" ? "Generando..." : "Descargar PDF"}
        </button>
      </div>
    );
  }

  async function guardarEmpleado() {
    if (!nuevoEmp.nombre || !nuevoEmp.salario) { setError("Nombre y salario requeridos"); return; }
    setError("");
    try {
      if (editingEmp) {
        await put(`/nomina/empleados/${editingEmp}`, nuevoEmp);
        setEditingEmp(null);
      } else {
        await post("/nomina/empleados", nuevoEmp);
      }
      await fetchEmpleados();
      setShowNewEmp(false);
      setNuevoEmp({ nombre: "", cedula: "", cargo: "", salario: SMLMV, clase_riesgo_arl: 1, tipo_salario: "ordinario", fecha_ingreso: "", email: "" });
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error guardando empleado"); }
  }

  async function eliminarEmpleado(id: string) {
    try {
      await del(`/nomina/empleados/${id}`);
      await fetchEmpleados();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error eliminando empleado"); }
  }

  function editarEmpleado(e: Empleado) {
    setEditingEmp(e.id);
    setNuevoEmp({ nombre: e.nombre, cedula: e.cedula, cargo: e.cargo, salario: e.salario,
      clase_riesgo_arl: e.clase_riesgo_arl, tipo_salario: e.tipo_salario,
      fecha_ingreso: e.fecha_ingreso, email: e.email || "" });
    setShowNewEmp(true);
  }

  function cargarEnMensual(e: Empleado) {
    setMensual((p) => ({ ...p, salario_basico: NUM(e.salario), clase_riesgo_arl: String(e.clase_riesgo_arl), tipo_salario: e.tipo_salario }));
    setTab("mensual");
  }

  function cargarEnLiq(e: Empleado) {
    setLiq((p) => ({ ...p, salario_basico: NUM(e.salario), tipo_salario: e.tipo_salario, fecha_ingreso: e.fecha_ingreso || "" }));
    setTab("liquidacion");
  }

  async function calcularPeriodo() {
    setPeriodoLoading(true); setError("");
    try {
      const res = await post<PeriodoDetalle>(`/nomina/periodos/${periodoActual}/calcular`, {
        dias_trabajados: parseInt(periodoDias),
      });
      setPeriodoDetalle(res);
      await fetchPeriodos();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error calculando período"); }
    finally { setPeriodoLoading(false); }
  }

  async function abrirPeriodo(p: PeriodoResumen) {
    try {
      const det = await get<PeriodoDetalle>(`/nomina/periodos/${p.periodo}`);
      setPeriodoDetalle(det);
      setPeriodoActual(p.periodo);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error abriendo período"); }
  }

  async function descargarColilla(periodoStr: string, empId: string, nombre: string) {
    try {
      const blob = await getBlob(`/nomina/colilla/${periodoStr}/${empId}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `colilla_${nombre.replace(/ /g,"_")}_${periodoStr}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error descargando colilla"); }
  }

  async function calcularPrima() {
    setPrimaLoading(true); setError(""); setPrimaResult(null);
    const semestre = `${primaAnio}-${primaSem}`;
    try {
      const res = await post<typeof primaResult>(`/nomina/periodos/${semestre}/prima`, {
        dias_trabajados: parseInt(primaDias),
      });
      setPrimaResult(res);
      await fetchPeriodos();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error calculando prima"); }
    finally { setPrimaLoading(false); }
  }

  async function enviarEmails(periodoStr: string) {
    setEmailLoading(true); setError("");
    try {
      const res = await post<{enviados: string[]; sin_email: string[]; errores: string[]}>(`/nomina/periodos/${periodoStr}/email`, {});
      const msg = `Enviados: ${res.enviados.length} · Sin email: ${res.sin_email.length}${res.errores.length ? ` · Errores: ${res.errores.join("; ")}` : ""}`;
      setError(msg);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error enviando emails"); }
    finally { setEmailLoading(false); }
  }

  async function handleBatchFile(file: File) {
    setBatchLoading(true); setBatchResults([]); setError("");
    try {
      const formData = new FormData(); formData.append("file", file);
      const results = await postForm<BatchRow[]>("/nomina/import-batch", formData);
      setBatchResults(results);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error procesando archivo"); }
    finally { setBatchLoading(false); }
  }

  const chatData = tab === "mensual" && resultMensual ? { tipo: "nómina mensual", resultado: resultMensual }
    : tab === "liquidacion" && resultLiq ? { tipo: "liquidación", resultado: resultLiq } : null;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-24">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Liquidación de Nómina</h2>
        <p className="text-gray-500 dark:text-gray-400 mt-1 text-sm">CST Colombia · SMLMV 2026: {COP(SMLMV)} · Aux. transporte: {COP(AUX_T)}</p>
      </div>

      <div className="flex gap-1 bg-gray-100 dark:bg-slate-800 p-1 rounded-xl flex-wrap">
        {([
          ["mensual",     "Nómina Mensual",         Calculator],
          ["liquidacion", "Liquidación",             FileText],
          ["empleados",   `Empleados (${empleados.length})`, Users],
          ["periodos",    "Períodos",                Calendar],
          ["analitica",   "Analítica",               BarChart3],
        ] as const).map(([t, label, Icon]) => (
          <button key={t} onClick={() => { setTab(t); setError(""); }}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t ? "bg-white dark:bg-slate-700 shadow text-gray-900 dark:text-white" : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            }`}><Icon size={14} />{label}</button>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm rounded-lg px-4 py-3">
          <AlertCircle size={15} />{error}
        </div>
      )}

      {/* ══ MENSUAL ══════════════════════════════════════════════════════ */}
      {tab === "mensual" && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-4">Datos del empleado</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">Salario básico mensual *</label>
                  <input className="input" placeholder={NUM(SMLMV)}
                    value={mensual.salario_basico} onChange={(e) => setM("salario_basico", e.target.value)} />
                  <SalaryPresets currentVal={mensual.salario_basico} onSelect={(v) => setM("salario_basico", NUM(v))} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Días trabajados</label>
                  <input className="input" type="number" min={1} max={31}
                    value={mensual.dias_trabajados} onChange={(e) => setM("dias_trabajados", e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Tipo de salario</label>
                  <select className="input" value={mensual.tipo_salario} onChange={(e) => setM("tipo_salario", e.target.value)}>
                    <option value="ordinario">Ordinario</option>
                    <option value="integral">Integral (≥13 SMLMV)</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">Clase ARL (riesgo laboral)</label>
                  <select className="input" value={mensual.clase_riesgo_arl} onChange={(e) => setM("clase_riesgo_arl", e.target.value)}>
                    <option value="1">Clase I – Riesgo mínimo (0.522%)</option>
                    <option value="2">Clase II – Riesgo bajo (1.044%)</option>
                    <option value="3">Clase III – Riesgo medio (2.436%)</option>
                    <option value="4">Clase IV – Riesgo alto (4.350%)</option>
                    <option value="5">Clase V – Riesgo máximo (6.960%)</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="card">
              <button className="flex items-center justify-between w-full text-sm font-semibold text-gray-700 dark:text-gray-200"
                onClick={() => setShowHE(!showHE)}>
                Horas extras y recargos {showHE ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
              {showHE && (
                <div className="mt-3 grid grid-cols-2 gap-3">
                  {([
                    ["hed","Extra Diurna (HED) +25%"], ["hen","Extra Nocturna (HEN) +75%"],
                    ["rn","Recargo Nocturno (RN) +35%"], ["hod","Dominical/Festivo (HOD) +75%"],
                    ["hedd","Extra Diurna Dom. (HEDD) +100%"], ["hend","Extra Nocturna Dom. (HEND) +150%"],
                    ["rnd","Recargo Noct. Dom. (RND) +110%"],
                  ] as const).map(([k, label]) => (
                    <div key={k}>
                      <label className="block text-xs text-gray-500 mb-1">{label}</label>
                      <input className="input" type="number" min={0} step={0.5}
                        value={mensual[k]} onChange={(e) => setM(k, e.target.value)} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Otros conceptos</h3>
              <div className="grid grid-cols-2 gap-3">
                {([
                  ["bonificaciones_salariales","Bonificaciones salariales"],
                  ["comisiones","Comisiones"],
                  ["otros_no_salariales","No salariales (no IBC)"],
                  ["retencion_fuente","Retención en la fuente"],
                  ["otras_deducciones","Otras deducciones"],
                ] as const).map(([k, label]) => (
                  <div key={k}>
                    <label className="block text-xs text-gray-500 mb-1">{label}</label>
                    <input className="input" placeholder="0" value={mensual[k]} onChange={(e) => setM(k, e.target.value)} />
                  </div>
                ))}
              </div>
            </div>
            <button className="btn-primary w-full flex items-center justify-center gap-2" onClick={calcularMensual} disabled={loading}>
              <Calculator size={16} />{loading ? "Calculando..." : "Calcular nómina"}
            </button>
          </div>

          {resultMensual && (
            <div>
              <ExportButtons tipo="mensual" />
              <Section title="Devengado" accent>
                <Row label="Salario proporcional" value={resultMensual.devengado.salario_proporcional} />
                {resultMensual.devengado.aplica_aux_transporte && <Row label="Auxilio de transporte" value={resultMensual.devengado.auxilio_transporte} />}
                {resultMensual.devengado.horas_extras.subtotal > 0 && (
                  <>{(["hed","hen","rn","hod","hedd","hend","rnd"] as const).map((k) =>
                    resultMensual.devengado.horas_extras[k] > 0 && <Row key={k} sub label={`  · ${k.toUpperCase()}`} value={resultMensual.devengado.horas_extras[k]} />)}
                    <Row label="Subtotal HE y recargos" value={resultMensual.devengado.horas_extras.subtotal} /></>
                )}
                {resultMensual.devengado.bonificaciones > 0 && <Row label="Bonificaciones" value={resultMensual.devengado.bonificaciones} />}
                {resultMensual.devengado.comisiones > 0 && <Row label="Comisiones" value={resultMensual.devengado.comisiones} />}
                {resultMensual.devengado.otros_no_salariales > 0 && <Row label="No salariales" value={resultMensual.devengado.otros_no_salariales} />}
                <Row label="TOTAL DEVENGADO" value={resultMensual.devengado.total_devengado} bold />
              </Section>

              <Section title="Deducciones empleado">
                <Row label={`IBC · ${COP(resultMensual.deducciones.ibc)}`} value="" />
                <Row label="Salud empleado (4%)" value={resultMensual.deducciones.salud_empleado} />
                <Row label="Pensión empleado (4%)" value={resultMensual.deducciones.pension_empleado} />
                {resultMensual.deducciones.fsp > 0 && <Row label="FSP – Solidaridad Pensional" value={resultMensual.deducciones.fsp} />}
                {resultMensual.deducciones.retencion_fuente > 0 && <Row label="Retención en la fuente" value={resultMensual.deducciones.retencion_fuente} />}
                {resultMensual.deducciones.otras > 0 && <Row label="Otras deducciones" value={resultMensual.deducciones.otras} />}
                <Row label="TOTAL DEDUCCIONES" value={resultMensual.deducciones.total_deducciones} bold />
              </Section>

              <div className="card bg-brand-navy text-white mb-4">
                <div className="flex justify-between items-center">
                  <span className="font-semibold">NETO A PAGAR</span>
                  <span className="text-2xl font-black text-brand-orange">{COP(resultMensual.neto_pagar)}</span>
                </div>
              </div>

              <Section title="Carga patronal — parafiscales y SS">
                <Row label="Salud empleador (8.5%)" value={resultMensual.carga_patronal.salud_empleador} />
                <Row label="Pensión empleador (12%)" value={resultMensual.carga_patronal.pension} />
                <Row label={`ARL · Clase ${mensual.clase_riesgo_arl}`} value={resultMensual.carga_patronal.arl} />
                <Row label={`SENA (2%)${resultMensual.carga_patronal.exonerado_sena_icbf?" · Exonerado":""}`} value={resultMensual.carga_patronal.sena} />
                <Row label={`ICBF (3%)${resultMensual.carga_patronal.exonerado_sena_icbf?" · Exonerado":""}`} value={resultMensual.carga_patronal.icbf} />
                <Row label="Caja de Compensación (4%)" value={resultMensual.carga_patronal.caja_compensacion} />
                <Row label="TOTAL CARGA PATRONAL" value={resultMensual.carga_patronal.total} bold />
              </Section>

              <div className="card border-2 border-brand-orange">
                <div className="flex justify-between items-center">
                  <div><p className="font-bold text-gray-900 dark:text-white text-sm">COSTO TOTAL EMPRESA</p>
                    <p className="text-xs text-gray-500">Devengado + carga patronal</p></div>
                  <span className="text-xl font-black text-brand-orange">{COP(resultMensual.carga_patronal.costo_total_empresa)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══ LIQUIDACIÓN ══════════════════════════════════════════════════ */}
      {tab === "liquidacion" && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-4">Datos del contrato</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">Salario básico mensual *</label>
                  <input className="input" placeholder={NUM(SMLMV)}
                    value={liq.salario_basico} onChange={(e) => setL("salario_basico", e.target.value)} />
                  <SalaryPresets currentVal={liq.salario_basico} onSelect={(v) => setL("salario_basico", NUM(v))} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Fecha de ingreso *</label>
                  <input className="input" type="date" value={liq.fecha_ingreso} onChange={(e) => setL("fecha_ingreso", e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Fecha de retiro *</label>
                  <input className="input" type="date" value={liq.fecha_retiro} onChange={(e) => setL("fecha_retiro", e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Tipo de contrato</label>
                  <select className="input" value={liq.tipo_contrato} onChange={(e) => setL("tipo_contrato", e.target.value)}>
                    <option value="indefinido">Indefinido</option>
                    <option value="termino_fijo">Término Fijo</option>
                    <option value="obra_labor">Obra o Labor</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Causa de terminación</label>
                  <select className="input" value={liq.causa_terminacion} onChange={(e) => setL("causa_terminacion", e.target.value)}>
                    <option value="renuncia">Renuncia voluntaria</option>
                    <option value="sin_justa_causa_empleador">Sin justa causa (empleador)</option>
                    <option value="justa_causa">Justa causa</option>
                    <option value="mutuo_acuerdo">Mutuo acuerdo</option>
                    <option value="vencimiento">Vencimiento contrato</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Tipo de salario</label>
                  <select className="input" value={liq.tipo_salario} onChange={(e) => setL("tipo_salario", e.target.value)}>
                    <option value="ordinario">Ordinario</option>
                    <option value="integral">Integral</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Variables (último año)</h3>
              <div className="grid grid-cols-2 gap-3">
                {([
                  ["promedio_he_recargos","Prom. HE y recargos/mes"],
                  ["promedio_bonif_salariales","Prom. bonificaciones/mes"],
                  ["dias_vacaciones_disfrutadas","Días vac. ya disfrutadas"],
                  ["anticipo_cesantias","Anticipo cesantías recibido"],
                  ["otras_deducciones","Préstamos / embargos"],
                ] as const).map(([k, label]) => (
                  <div key={k}>
                    <label className="block text-xs text-gray-500 mb-1">{label}</label>
                    <input className="input" placeholder="0" value={liq[k]} onChange={(e) => setL(k, e.target.value)} />
                  </div>
                ))}
              </div>
            </div>
            <button className="btn-primary w-full flex items-center justify-center gap-2" onClick={calcularLiq} disabled={loading}>
              <FileText size={16} />{loading ? "Calculando..." : "Calcular liquidación"}
            </button>
          </div>

          {resultLiq && (
            <div>
              <ExportButtons tipo="liquidacion" />
              <Section title="Tiempo trabajado">
                <Row label="Días (base 360)" value={resultLiq.tiempo.dias_trabajados} />
                <Row label="Base prestacional" value={resultLiq.bases.salario_base_prestacional} />
                <Row label="Base vacaciones" value={resultLiq.bases.salario_base_vacaciones} />
                <Row label="Aux. transporte incluido" value={resultLiq.bases.aplica_aux_transporte ? "Sí" : "No"} />
              </Section>
              <Section title="Prestaciones sociales" accent>
                <Row label={`Cesantías (${resultLiq.dias_auditoria.cesantias} días)`} value={resultLiq.prestaciones.cesantias} />
                <Row label="Intereses sobre cesantías (12%)" value={resultLiq.prestaciones.intereses_cesantias} />
                <Row label={`Prima de servicios (${resultLiq.dias_auditoria.prima} días)`} value={resultLiq.prestaciones.prima_servicios} />
                <Row label={`Vacaciones (${resultLiq.dias_auditoria.vacaciones_a_pagar} días pendientes)`} value={resultLiq.prestaciones.vacaciones} />
                <Row label="Salario pendiente" value={resultLiq.prestaciones.salario_pendiente} />
              </Section>
              {resultLiq.indemnizacion.valor > 0 && (
                <Section title="Indemnización">
                  <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">{resultLiq.indemnizacion.detalle}</p>
                  <Row label="Valor indemnización" value={resultLiq.indemnizacion.valor} bold />
                </Section>
              )}
              <div className="card bg-brand-navy text-white">
                <Row label="Subtotal devengado" value={COP(resultLiq.totales.subtotal_devengado)} />
                {resultLiq.totales.deducciones > 0 && <Row label="(-) Deducciones" value={`-${COP(resultLiq.totales.deducciones)}`} />}
                <div className="flex justify-between items-center mt-3 pt-3 border-t border-white/20">
                  <span className="font-semibold">TOTAL NETO A PAGAR</span>
                  <span className="text-2xl font-black text-brand-orange">{COP(resultLiq.totales.total_neto)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══ EMPLEADOS ════════════════════════════════════════════════════ */}
      {tab === "empleados" && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 dark:text-white">Directorio de empleados</h3>
              <button onClick={() => setShowNewEmp(!showNewEmp)}
                className="flex items-center gap-1.5 text-sm bg-brand-orange text-white px-3 py-1.5 rounded-lg hover:bg-orange-600 transition-colors font-medium">
                <Plus size={14} /> Nuevo empleado
              </button>
            </div>

            {showNewEmp && (
              <div className="bg-gray-50 dark:bg-slate-800 rounded-xl p-4 mb-4 border border-gray-200 dark:border-slate-700">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
                  {editingEmp ? "Editar empleado" : "Nuevo empleado"}
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="block text-xs text-gray-500 mb-1">Nombre completo *</label>
                    <input className="input" placeholder="Juan Pérez" value={nuevoEmp.nombre} onChange={(e) => setNuevoEmp((p) => ({ ...p, nombre: e.target.value }))} /></div>
                  <div><label className="block text-xs text-gray-500 mb-1">Cédula</label>
                    <input className="input" placeholder="123456789" value={nuevoEmp.cedula} onChange={(e) => setNuevoEmp((p) => ({ ...p, cedula: e.target.value }))} /></div>
                  <div><label className="block text-xs text-gray-500 mb-1">Cargo</label>
                    <input className="input" placeholder="Auxiliar contable" value={nuevoEmp.cargo} onChange={(e) => setNuevoEmp((p) => ({ ...p, cargo: e.target.value }))} /></div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Salario básico *</label>
                    <input className="input" placeholder={NUM(SMLMV)}
                      value={nuevoEmp.salario ? NUM(nuevoEmp.salario) : ""}
                      onChange={(e) => setNuevoEmp((p) => ({ ...p, salario: parseFloat(e.target.value.replace(/\./g,"")) || 0 }))} />
                    <SalaryPresets currentVal={String(nuevoEmp.salario)} onSelect={(v) => setNuevoEmp((p) => ({ ...p, salario: v }))} />
                  </div>
                  <div><label className="block text-xs text-gray-500 mb-1">Clase ARL</label>
                    <select className="input" value={nuevoEmp.clase_riesgo_arl} onChange={(e) => setNuevoEmp((p) => ({ ...p, clase_riesgo_arl: parseInt(e.target.value) }))}>
                      <option value={1}>Clase I (0.522%)</option><option value={2}>Clase II (1.044%)</option>
                      <option value={3}>Clase III (2.436%)</option><option value={4}>Clase IV (4.350%)</option>
                      <option value={5}>Clase V (6.960%)</option>
                    </select></div>
                  <div><label className="block text-xs text-gray-500 mb-1">Tipo salario</label>
                    <select className="input" value={nuevoEmp.tipo_salario} onChange={(e) => setNuevoEmp((p) => ({ ...p, tipo_salario: e.target.value }))}>
                      <option value="ordinario">Ordinario</option><option value="integral">Integral</option>
                    </select></div>
                  <div><label className="block text-xs text-gray-500 mb-1">Fecha de ingreso</label>
                    <input className="input" type="date" value={nuevoEmp.fecha_ingreso} onChange={(e) => setNuevoEmp((p) => ({ ...p, fecha_ingreso: e.target.value }))} /></div>
                  <div><label className="block text-xs text-gray-500 mb-1">Email (para colillas)</label>
                    <input className="input" type="email" placeholder="juan@empresa.com" value={nuevoEmp.email} onChange={(e) => setNuevoEmp((p) => ({ ...p, email: e.target.value }))} /></div>
                </div>
                <div className="flex gap-2 mt-3">
                  <button onClick={guardarEmpleado} className="btn-primary flex items-center gap-1.5 text-sm px-4 py-2">
                    <UserCheck size={14} /> {editingEmp ? "Actualizar" : "Guardar"}
                  </button>
                  <button onClick={() => { setShowNewEmp(false); setEditingEmp(null); }} className="text-sm text-gray-400 hover:text-gray-600 px-4 py-2">Cancelar</button>
                </div>
              </div>
            )}

            {empLoading ? (
              <p className="text-sm text-gray-400 text-center py-8">Cargando empleados...</p>
            ) : empleados.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">Sin empleados. Agrega uno para comenzar.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b dark:border-slate-700">
                      <th className="pb-2">Empleado</th><th className="pb-2">Cargo</th>
                      <th className="pb-2 text-right">Salario</th><th className="pb-2 text-center">ARL</th>
                      <th className="pb-2 text-center">Email</th><th className="pb-2">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {empleados.map((e) => (
                      <tr key={e.id} className="border-b dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700/30">
                        <td className="py-2">
                          <p className="font-medium text-gray-900 dark:text-white">{e.nombre}</p>
                          {e.cedula && <p className="text-xs text-gray-400">{e.cedula}</p>}
                        </td>
                        <td className="py-2 text-gray-500 text-xs">{e.cargo || "—"}</td>
                        <td className="py-2 text-right font-medium text-gray-900 dark:text-white">{COP(e.salario)}</td>
                        <td className="py-2 text-center"><span className="text-xs bg-gray-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">{e.clase_riesgo_arl}</span></td>
                        <td className="py-2 text-center">
                          {e.email ? <span className="text-xs text-green-600">✓</span> : <span className="text-xs text-gray-300">—</span>}
                        </td>
                        <td className="py-2">
                          <div className="flex gap-1.5">
                            <button onClick={() => cargarEnMensual(e)} className="text-xs bg-brand-orange text-white px-2 py-1 rounded-md hover:bg-orange-600 transition-colors">Mensual</button>
                            <button onClick={() => cargarEnLiq(e)} className="text-xs bg-brand-navy text-white px-2 py-1 rounded-md hover:bg-brand-navy/80 transition-colors">Liquidar</button>
                            <button onClick={() => editarEmpleado(e)} className="text-xs text-blue-400 hover:text-blue-600 p-1 border border-blue-200 dark:border-blue-800 rounded">Editar</button>
                            <button onClick={() => eliminarEmpleado(e.id)} className="text-xs text-red-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Importar nómina desde archivo</h3>
            <p className="text-xs text-gray-500 mb-4">
              Sube un Excel (.xlsx/.xls) o CSV con columnas:{" "}
              <code className="bg-gray-100 dark:bg-slate-700 px-1 rounded text-brand-orange">nombre</code>,{" "}
              <code className="bg-gray-100 dark:bg-slate-700 px-1 rounded text-brand-orange">salario_basico</code>,{" "}
              <code className="bg-gray-100 dark:bg-slate-700 px-1 rounded text-brand-orange">dias_trabajados</code> (opc),{" "}
              <code className="bg-gray-100 dark:bg-slate-700 px-1 rounded text-brand-orange">clase_riesgo_arl</code> (opc)
            </p>
            <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleBatchFile(f); }} />
            <div className="border-2 border-dashed border-gray-200 dark:border-slate-600 rounded-xl p-8 text-center cursor-pointer hover:border-brand-orange transition-colors"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleBatchFile(f); }}>
              <Upload size={28} className="mx-auto text-gray-300 dark:text-slate-600 mb-2" />
              <p className="text-sm text-gray-500">{batchLoading ? "Procesando..." : "Arrastra tu Excel/CSV aquí o haz clic"}</p>
              <p className="text-xs text-gray-400 mt-1">Formatos: .xlsx, .xls, .csv</p>
            </div>

            {batchResults.length > 0 && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">{batchResults.length} empleados procesados</h4>
                  <button onClick={async () => {
                    try {
                      const blob = await post<Blob>("/nomina/export-batch", { rows: batchResults }, true);
                      const url = URL.createObjectURL(blob); const a = document.createElement("a");
                      a.href = url; a.download = `taxops_nomina_batch_${new Date().toISOString().slice(0,10)}.xlsx`; a.click();
                      URL.revokeObjectURL(url);
                    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error exportando"); }
                  }} className="flex items-center gap-1.5 text-xs text-brand-orange hover:text-orange-700 font-medium">
                    <Download size={13} /> Descargar Excel
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-gray-500 border-b dark:border-slate-700">
                        <th className="pb-2">Nombre</th><th className="pb-2 text-right">Salario</th>
                        <th className="pb-2 text-right">Neto</th><th className="pb-2 text-right">Carga</th><th className="pb-2 text-right">Costo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchResults.map((r, i) => (
                        <tr key={i} className="border-b dark:border-slate-700">
                          <td className="py-1.5 font-medium text-gray-900 dark:text-white">{r.nombre}</td>
                          <td className="py-1.5 text-right text-gray-500">{COP(r.salario)}</td>
                          <td className="py-1.5 text-right font-semibold">{COP(r.neto)}</td>
                          <td className="py-1.5 text-right text-gray-500">{COP(r.carga)}</td>
                          <td className="py-1.5 text-right text-brand-orange font-medium">{COP(r.costo)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="border-t-2 border-gray-200 dark:border-slate-600 font-bold">
                      <tr>
                        <td className="pt-2">TOTALES</td>
                        <td className="pt-2 text-right">{COP(batchResults.reduce((s,r)=>s+r.salario,0))}</td>
                        <td className="pt-2 text-right">{COP(batchResults.reduce((s,r)=>s+r.neto,0))}</td>
                        <td className="pt-2 text-right">{COP(batchResults.reduce((s,r)=>s+r.carga,0))}</td>
                        <td className="pt-2 text-right text-brand-orange">{COP(batchResults.reduce((s,r)=>s+r.costo,0))}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ PERÍODOS ═════════════════════════════════════════════════════ */}
      {tab === "periodos" && (
        <div className="space-y-6">
          {/* Calcular nuevo período */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Calcular nómina batch</h3>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Período (YYYY-MM)</label>
                <input className="input" type="month" value={periodoActual}
                  onChange={(e) => setPeriodoActual(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Días trabajados</label>
                <input className="input" type="number" min={1} max={31} value={periodoDias}
                  onChange={(e) => setPeriodoDias(e.target.value)} />
              </div>
            </div>
            <div className="flex gap-3 items-center">
              <button onClick={calcularPeriodo} disabled={periodoLoading || empleados.length === 0}
                className="btn-primary flex items-center gap-2 disabled:opacity-50">
                {periodoLoading ? <RefreshCw size={14} className="animate-spin" /> : <Calculator size={14} />}
                {periodoLoading ? "Calculando..." : `Calcular ${empleados.length} empleados`}
              </button>
              {empleados.length === 0 && (
                <p className="text-xs text-amber-500">Agrega empleados en la pestaña Empleados primero</p>
              )}
            </div>
          </div>

          {/* Detalle del período calculado */}
          {periodoDetalle && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">Período {periodoDetalle.periodo}</h3>
                  <p className="text-xs text-gray-500">{periodoDetalle.empleados_count} empleados · {periodoDetalle.estado}</p>
                </div>
                <button onClick={() => enviarEmails(periodoDetalle.periodo)} disabled={emailLoading}
                  className="flex items-center gap-1.5 text-sm bg-brand-navy text-white px-3 py-1.5 rounded-lg hover:bg-brand-navy/80 transition-colors disabled:opacity-50">
                  {emailLoading ? <RefreshCw size={13} className="animate-spin" /> : <Mail size={13} />}
                  {emailLoading ? "Enviando..." : "Enviar colillas por email"}
                </button>
              </div>

              {/* Resumen de totales */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                {[
                  { label: "Total devengado",  value: periodoDetalle.total_devengado },
                  { label: "Total neto",        value: periodoDetalle.total_neto },
                  { label: "Carga patronal",    value: periodoDetalle.carga_patronal },
                  { label: "Costo empresa",     value: periodoDetalle.costo_empresa },
                ].map((k) => (
                  <div key={k.label} className="bg-gray-50 dark:bg-slate-800 rounded-lg p-3">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{k.label}</p>
                    <p className="text-sm font-bold text-gray-900 dark:text-white">{COP(k.value)}</p>
                  </div>
                ))}
              </div>

              {/* Tabla de empleados del período */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b dark:border-slate-700">
                      <th className="pb-2">Empleado</th>
                      <th className="pb-2 text-right">Devengado</th>
                      <th className="pb-2 text-right">Neto</th>
                      <th className="pb-2 text-right">Carga</th>
                      <th className="pb-2 text-right">Costo</th>
                      <th className="pb-2">Colilla</th>
                    </tr>
                  </thead>
                  <tbody>
                    {periodoDetalle.detalle.map((d) => (
                      <tr key={d.empleado_id} className="border-b dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700/30">
                        <td className="py-2">
                          <p className="font-medium text-gray-900 dark:text-white">{d.nombre}</p>
                          <p className="text-xs text-gray-400">{d.cargo || d.cedula || "—"}</p>
                        </td>
                        <td className="py-2 text-right text-gray-600 dark:text-gray-300">{d.error ? <span className="text-red-400 text-xs">{d.error}</span> : COP(d.devengado)}</td>
                        <td className="py-2 text-right font-semibold text-gray-900 dark:text-white">{d.error ? "—" : COP(d.neto)}</td>
                        <td className="py-2 text-right text-gray-500">{d.error ? "—" : COP(d.carga)}</td>
                        <td className="py-2 text-right text-brand-orange font-medium">{d.error ? "—" : COP(d.costo)}</td>
                        <td className="py-2">
                          {!d.error && (
                            <button onClick={() => descargarColilla(periodoDetalle.periodo, d.empleado_id, d.nombre)}
                              className="flex items-center gap-1 text-xs text-brand-orange hover:text-orange-700 font-medium">
                              <Download size={12} /> PDF
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="border-t-2 border-gray-200 dark:border-slate-600 font-bold text-sm">
                    <tr>
                      <td className="pt-2">TOTALES</td>
                      <td className="pt-2 text-right">{COP(periodoDetalle.detalle.reduce((s,r)=>s+(r.devengado||0),0))}</td>
                      <td className="pt-2 text-right">{COP(periodoDetalle.detalle.reduce((s,r)=>s+(r.neto||0),0))}</td>
                      <td className="pt-2 text-right">{COP(periodoDetalle.detalle.reduce((s,r)=>s+(r.carga||0),0))}</td>
                      <td className="pt-2 text-right text-brand-orange">{COP(periodoDetalle.detalle.reduce((s,r)=>s+(r.costo||0),0))}</td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}

          {/* Historial de períodos calculados */}
          {periodos.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-3">Historial de períodos</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b dark:border-slate-700">
                      <th className="pb-2">Período</th><th className="pb-2 text-center">Emp.</th>
                      <th className="pb-2 text-right">Neto total</th>
                      <th className="pb-2 text-right">Costo empresa</th>
                      <th className="pb-2 text-center">Estado</th><th className="pb-2">Ver</th>
                    </tr>
                  </thead>
                  <tbody>
                    {periodos.map((p) => (
                      <tr key={p.id} className="border-b dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700/30">
                        <td className="py-2 font-medium text-gray-900 dark:text-white">{p.periodo}</td>
                        <td className="py-2 text-center text-gray-500">{p.empleados_count}</td>
                        <td className="py-2 text-right font-semibold">{COP(p.total_neto)}</td>
                        <td className="py-2 text-right text-brand-orange font-medium">{COP(p.costo_empresa)}</td>
                        <td className="py-2 text-center">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${p.estado==="calculado"?"bg-green-100 text-green-700":"bg-gray-100 text-gray-500"}`}>
                            {p.estado}
                          </span>
                        </td>
                        <td className="py-2">
                          <button onClick={() => abrirPeriodo(p)}
                            className="text-xs text-brand-orange hover:text-orange-700 font-medium">
                            Abrir →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Prima semestral */}
          <div className="card border-l-4 border-l-brand-orange">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Prima semestral · Art. 306 CST</h3>
            <p className="text-xs text-gray-500 mb-4">
              15 días de salario por semestre. Base: salario + aux. transporte (si aplica).
            </p>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Año</label>
                <input className="input" type="number" min={2024} max={2030} value={primaAnio}
                  onChange={(e) => setPrimaAnio(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Semestre</label>
                <select className="input" value={primaSem} onChange={(e) => setPrimaSem(e.target.value as "S1"|"S2")}>
                  <option value="S1">S1 — Ene/Jun (pago 30 jun)</option>
                  <option value="S2">S2 — Jul/Dic (pago 20 dic)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Días trabajados</label>
                <input className="input" type="number" min={1} max={180} value={primaDias}
                  onChange={(e) => setPrimaDias(e.target.value)} />
              </div>
            </div>
            <button onClick={calcularPrima} disabled={primaLoading || empleados.length === 0}
              className="btn-primary flex items-center gap-2 mb-4 disabled:opacity-50">
              {primaLoading ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
              {primaLoading ? "Calculando..." : `Calcular prima · ${empleados.length} empleados`}
            </button>

            {primaResult && (
              <div>
                <div className="flex gap-4 mb-3 flex-wrap">
                  <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg px-4 py-2">
                    <p className="text-xs text-gray-500">Total prima</p>
                    <p className="text-lg font-bold text-brand-orange">{COP(primaResult.total_prima)}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-4 py-2">
                    <p className="text-xs text-gray-500">Pago límite</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">{primaResult.fecha_pago_limite}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-4 py-2">
                    <p className="text-xs text-gray-500">Empleados</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">{primaResult.empleados_count}</p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-gray-500 border-b dark:border-slate-700">
                        <th className="pb-2">Empleado</th>
                        <th className="pb-2 text-right">Salario</th>
                        <th className="pb-2 text-right">Base liq.</th>
                        <th className="pb-2 text-center">Días</th>
                        <th className="pb-2 text-right">Prima</th>
                      </tr>
                    </thead>
                    <tbody>
                      {primaResult.detalle.map((d) => (
                        <tr key={d.empleado_id} className="border-b dark:border-slate-700">
                          <td className="py-1.5 font-medium text-gray-900 dark:text-white">
                            {d.nombre}
                            {d.cedula && <span className="text-xs text-gray-400 ml-1">{d.cedula}</span>}
                          </td>
                          <td className="py-1.5 text-right text-gray-500">{d.error ? "—" : COP(d.salario)}</td>
                          <td className="py-1.5 text-right text-gray-500">{d.error ? <span className="text-red-400 text-xs">{d.error}</span> : COP(d.base_liquidacion)}</td>
                          <td className="py-1.5 text-center text-gray-500">{d.error ? "—" : d.dias_trabajados}</td>
                          <td className="py-1.5 text-right font-bold text-brand-orange">{d.error ? "—" : COP(d.prima)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="border-t-2 border-gray-200 dark:border-slate-600 font-bold">
                      <tr>
                        <td className="pt-2" colSpan={4}>TOTAL PRIMA SEMESTRAL</td>
                        <td className="pt-2 text-right text-brand-orange">{COP(primaResult.total_prima)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ ANALÍTICA ════════════════════════════════════════════════════ */}
      {tab === "analitica" && (
        <div className="space-y-6">
          {history.length === 0 ? (
            <div className="card text-center py-12 text-gray-400">
              <TrendingUp size={40} className="mx-auto mb-3 opacity-20" />
              <p className="font-medium">Sin datos aún</p>
              <p className="text-sm mt-1">Realiza un cálculo para ver analítica aquí.</p>
            </div>
          ) : (<>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: "Cálculos", value: history.length.toString() },
                { label: "Neto promedio", value: COP(history.reduce((s,e)=>s+e.neto,0)/history.length) },
                { label: "Mayor neto", value: COP(Math.max(...history.map((e)=>e.neto))) },
                { label: "Carga promedio", value: COP(history.filter((e)=>e.carga).reduce((s,e)=>s+(e.carga||0),0)/(history.filter((e)=>e.carga).length||1)) },
              ].map((k) => (
                <div key={k.label} className="card text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{k.label}</p>
                  <p className="text-lg font-bold text-gray-900 dark:text-white">{k.value}</p>
                </div>
              ))}
            </div>
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-4">Últimos 8 cálculos · Neto vs Carga patronal</h3>
              <MiniBarChart data={history.slice(0,8).reverse().map((e,i)=>({ label:`#${i+1}`, neto:e.neto, carga:e.carga||0 }))} />
            </div>
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Historial de cálculos</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b dark:border-slate-700">
                      <th className="pb-2">Fecha</th><th className="pb-2">Tipo</th>
                      <th className="pb-2 text-right">Salario</th><th className="pb-2 text-right">Neto</th>
                      <th className="pb-2 text-right">Carga</th><th className="pb-2 text-right">Costo emp.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((e) => (
                      <tr key={e.id} className="border-b dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700/30">
                        <td className="py-2 text-xs text-gray-500">{new Date(e.ts).toLocaleString("es-CO",{dateStyle:"short",timeStyle:"short"})}</td>
                        <td className="py-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${e.tipo==="mensual"?"bg-blue-100 text-blue-700":"bg-orange-100 text-orange-700"}`}>
                            {e.tipo==="mensual"?"Mensual":"Liquidación"}
                          </span>
                        </td>
                        <td className="py-2 text-right text-gray-700 dark:text-gray-300">{COP(e.salario)}</td>
                        <td className="py-2 text-right font-semibold text-gray-900 dark:text-white">{COP(e.neto)}</td>
                        <td className="py-2 text-right text-gray-500">{e.carga?COP(e.carga):"—"}</td>
                        <td className="py-2 text-right text-brand-orange font-medium">{e.costo?COP(e.costo):"—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button onClick={()=>{localStorage.removeItem(HIST_KEY);setHistory([]);}} className="mt-3 text-xs text-gray-400 hover:text-red-500 transition-colors">
                Limpiar historial
              </button>
            </div>
          </>)}
        </div>
      )}

      <PageChatbot moduleName="Nómina" systemContext={NOMINA_SYSTEM} currentData={chatData} />
    </div>
  );
}
