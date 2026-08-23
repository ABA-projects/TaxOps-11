"use client";

import { useState, useRef, useEffect } from "react";
import {
  Upload, Download, X, AlertCircle, CheckCircle,
  BarChart2, TrendingUp, Bot, Send, ChevronDown,
} from "lucide-react";
import { useApi } from "@/lib/api";
import { uploadFiles } from "@/lib/directUpload";

type ProcessResult = {
  total_archivos: number;
  procesados: number;
  errores: number;
  ica_excluidos: number;
  advertencias: string[];
  df_detalle: Record<string, unknown>[];
  df_1003: Record<string, unknown>[];
};

type ChatMsg = { role: "user" | "assistant"; content: string };

/* ─── helpers analíticos ─────────────────────────────────────── */
function sumCol(rows: Record<string, unknown>[], col: string): number {
  return rows.reduce((acc, r) => {
    const v = parseFloat(String(r[col] ?? "0").replace(/[^0-9.-]/g, ""));
    return acc + (isNaN(v) ? 0 : v);
  }, 0);
}

function fmt(n: number) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);
}

function groupBy(rows: Record<string, unknown>[], key: string, valueCol: string) {
  const map: Record<string, number> = {};
  rows.forEach((r) => {
    const k = String(r[key] ?? "—");
    const v = parseFloat(String(r[valueCol] ?? "0").replace(/[^0-9.-]/g, ""));
    map[k] = (map[k] ?? 0) + (isNaN(v) ? 0 : v);
  });
  return Object.entries(map)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

/* ─── componentes internos ───────────────────────────────────── */
function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card flex-1 min-w-[160px]">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function BarRow({ label, value, max, color = "bg-brand-orange" }: { label: string; value: number; max: number; color?: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-40 truncate text-gray-600 shrink-0" title={label}>{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-28 text-right text-gray-700 font-medium shrink-0">{fmt(value)}</span>
    </div>
  );
}

const COL_LABELS: Record<string, string> = {
  concepto: "Concepto", tipo_doc: "Tipo", nit: "NIT", dv: "DV",
  razon_social: "Razón Social", primer_apellido: "Apellido 1", segundo_apellido: "Apellido 2",
  primer_nombre: "Nombre 1", otros_nombres: "Otros Nombres",
  direccion: "Dirección", ciudad_retencion: "Ciudad", cod_dpto: "Dpto", cod_mpio: "Mpio",
  base: "Base ($)", retencion: "Retención ($)", porcentaje: "% Ret",
  retenido_razon_social: "Retenido (Empresa)", retenido_nit: "Retenido (NIT)",
  tipo_cert: "Tipo Cert", archivo: "Archivo", error: "Error", validacion_tasa: "Tasa Real",
};
const MONEY_COLS = new Set(["base", "retencion"]);
const HIDDEN_COLS = new Set(["es_escaneado", "fuente", "primer_apellido", "segundo_apellido", "primer_nombre", "otros_nombres"]);
const PRIORITY_1003 = ["concepto","nit","dv","razon_social","base","retencion","porcentaje","ciudad_retencion","cod_dpto","cod_mpio","tipo_doc","direccion"];
const PRIORITY_DETALLE = ["archivo","tipo_cert","nit","razon_social","concepto","base","retencion","porcentaje","ciudad_retencion","retenido_razon_social","retenido_nit","error","direccion"];

function fmtCell(col: string, val: unknown): string {
  if (MONEY_COLS.has(col)) {
    const n = parseFloat(String(val ?? "0").replace(/[^0-9.-]/g, ""));
    return isNaN(n) ? "" : new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);
  }
  return String(val ?? "");
}

function DataTable({ rows, priority }: { rows: Record<string, unknown>[]; priority?: string[] }) {
  if (!rows.length) return <p className="p-6 text-sm text-gray-400 text-center">Sin datos</p>;
  const allCols = Object.keys(rows[0]).filter((c) => !HIDDEN_COLS.has(c));
  const ordered = priority
    ? [...priority.filter((c) => allCols.includes(c)), ...allCols.filter((c) => !priority.includes(c))]
    : allCols;
  return (
    <table className="text-xs w-full">
      <thead>
        <tr className="bg-gray-50 border-b border-gray-200">
          {ordered.map((c) => (
            <th key={c} className="px-3 py-2 text-left text-gray-500 font-medium whitespace-nowrap">
              {COL_LABELS[c] ?? c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 300).map((row, i) => (
          <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
            {ordered.map((c) => (
              <td key={c} className={`px-3 py-1.5 whitespace-nowrap ${MONEY_COLS.has(c) ? "text-right font-mono text-gray-800" : "text-gray-700"}`}>
                {fmtCell(c, row[c])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ─── página principal ───────────────────────────────────────── */

export default function ExogenasPage() {
  const { get, post } = useApi();
  const fileRef = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [tab, setTab] = useState<"analytics" | "exogenas" | "detalle">("analytics");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);

  // Chatbot
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([{
    role: "assistant",
    content: "Hola, soy tu asistente de exógenas. Puedo ayudarte a interpretar los certificados de retención, validar conceptos del Formato 1003 y resolver dudas sobre retención en la fuente. ¿Qué necesitas?",
  }]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMsgs]);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const VALID_EXT = /\.(pdf|jpg|jpeg|png|tiff?|bmp|webp|xlsx?|docx?)$/i;
    const valid = Array.from(list).filter((f) => VALID_EXT.test(f.name));
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...valid.filter((f) => !names.has(f.name))];
    });
  }

  async function pollJob(job_id: string) {
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const job = await get<{ status: string; progreso: number; result?: ProcessResult; error?: string }>(
          `/exogenas/jobs/${job_id}`
        );
        setProgress(job.progreso);
        if (job.status === "done" && job.result) {
          setResult(job.result);
          setTab("analytics");
          setLoading(false);
          return;
        }
        if (job.status === "error") {
          setError(job.error || "Error procesando los certificados");
          setLoading(false);
          return;
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Error consultando el estado del job");
        setLoading(false);
        return;
      }
    }
    setError("El procesamiento está tardando más de lo esperado — refresca en unos minutos");
    setLoading(false);
  }

  async function handleProcess() {
    if (!files.length) { setError("Agrega al menos un certificado PDF"); return; }
    setError(""); setLoading(true); setResult(null); setProgress(0);

    const uploaded = await uploadFiles(files, "exogenas", setProgress);
    const failed = uploaded.filter((u) => u.error);
    if (failed.length) {
      setError(`Fallo la subida de: ${failed.map((f) => `${f.filename} (${f.error})`).join(", ")}`);
      setLoading(false);
      return;
    }

    try {
      const { job_id } = await post<{ job_id: string; total: number }>("/exogenas/process", {
        s3_keys: uploaded.map((u) => u.s3_key),
      });
      setProgress(0); // reset — la barra pasa de "subiendo" a "procesando"
      await pollJob(job_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al enviar archivos");
      setLoading(false);
    }
  }

  async function handleExport() {
    if (!result) return;
    const blob = await post<Blob>(
      "/exogenas/export",
      { df_detalle: result.df_detalle, df_1003: result.df_1003 },
      true
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "taxops_exogenas.xlsx"; a.click();
    URL.revokeObjectURL(url);
  }

  async function sendChat() {
    const text = chatInput.trim();
    if (!text || chatLoading) return;
    setChatInput("");
    const userMsg: ChatMsg = { role: "user", content: text };
    setChatMsgs((p) => [...p, userMsg]);
    setChatLoading(true);

    const contextNote = result
      ? `\n\n[Contexto: el usuario procesó ${result.procesados} certificados. Total retenciones detectadas en Formato 1003: ${result.df_1003.length} registros.]`
      : "";

    try {
      const res = await post<{ content: string }>("/chatbot/ask", {
        message: text + contextNote,
        provider: "groq",
        model: "openai/gpt-oss-120b",
        history: chatMsgs.slice(-8),
        system_prompt: "Eres un experto contable colombiano especializado en exógenas, retención en la fuente, Formato 1003 DIAN y certificados de retención. Responde de forma clara y práctica.",
      });
      setChatMsgs((p) => [...p, { role: "assistant", content: res.content }]);
    } catch {
      setChatMsgs((p) => [...p, { role: "assistant", content: "Error de conexión. Intenta de nuevo." }]);
    } finally {
      setChatLoading(false);
    }
  }

  /* Analítica */
  const detalle = result?.df_detalle ?? [];
  const f1003 = result?.df_1003 ?? [];

  const valorCol = detalle.length
    ? ["valor_retencion", "retencion", "valor", "valor_retenido"].find((c) => c in detalle[0]) ?? Object.keys(detalle[0])[3] ?? ""
    : "";
  const nit1003Col = f1003.length
    ? ["nit_retenedor", "nit", "nit_agente"].find((c) => c in f1003[0]) ?? Object.keys(f1003[0])[0] ?? ""
    : "";
  const val1003Col = f1003.length
    ? ["valor_retencion", "retencion", "valor"].find((c) => c in f1003[0]) ?? Object.keys(f1003[0]).find((c) => c !== nit1003Col) ?? ""
    : "";

  const totalRetencion = sumCol(detalle, valorCol);
  const byRetenedor = groupBy(f1003, nit1003Col, val1003Col).slice(0, 10);
  const conceptoCol = detalle.length ? ["concepto", "tipo_retencion", "tipo"].find((c) => c in detalle[0]) ?? "" : "";
  const byConcepto = conceptoCol ? groupBy(detalle, conceptoCol, valorCol).slice(0, 8) : [];
  const maxRetenedor = byRetenedor[0]?.value ?? 0;
  const maxConcepto = byConcepto[0]?.value ?? 0;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Upload */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-1">Certificados de retención · Exógenas</h2>
        <p className="text-xs text-gray-400 mb-4">Sube certificados (PDF, imagen, Excel, Word) para generar el reporte de exógenas DIAN automáticamente.</p>

        <div
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-brand-orange transition-colors cursor-pointer"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
        >
          <Upload size={32} className="text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-600 font-medium">Arrastra archivos aquí o <span className="text-brand-orange">haz clic para seleccionar</span></p>
          <p className="text-xs text-gray-400 mt-1">PDF · JPG · PNG · Excel · Word — Retenciones de renta, IVA e ICA</p>
          <input ref={fileRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.bmp,.webp,.xlsx,.xls,.docx,.doc" className="hidden" onChange={(e) => addFiles(e.target.files)} />
        </div>

        {files.length > 0 && (
          <div className="mt-4 space-y-1 max-h-40 overflow-y-auto">
            {files.map((f) => (
              <div key={f.name} className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded-lg text-sm">
                <span className="truncate text-gray-700">{f.name}</span>
                <button onClick={() => setFiles((p) => p.filter((x) => x.name !== f.name))} className="text-gray-400 hover:text-red-500 ml-2">
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle size={16} className="shrink-0" />{error}
        </div>
      )}

      <div>
        <button onClick={handleProcess} disabled={loading || !files.length} className="btn-primary px-8">
          {loading ? `Procesando... ${progress}%` : `Procesar ${files.length} archivo${files.length !== 1 ? "s" : ""}`}
        </button>

        {loading && (
          <div className="mt-3 space-y-1.5">
            <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
              <div
                className="h-1.5 rounded-full bg-brand-orange transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-400">Esto puede tomar varios minutos con muchos archivos.</p>
          </div>
        )}
      </div>

      {result && (
        <div className="space-y-4">
          {/* Badges de resumen */}
          <div className="flex flex-wrap gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">
              <CheckCircle size={14} /> {result.procesados} procesados
            </span>
            {result.errores > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700">
                <AlertCircle size={14} /> {result.errores} errores
              </span>
            )}
            {result.ica_excluidos > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-yellow-50 text-yellow-700">
                {result.ica_excluidos} ICA excluidos
              </span>
            )}
          </div>

          {result.advertencias.length > 0 && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-700 space-y-1">
              {result.advertencias.map((a, i) => <p key={i}>⚠️ {a}</p>)}
            </div>
          )}

          <button onClick={handleExport} className="btn-secondary flex items-center gap-2">
            <Download size={16} /> Exportar Exógenas DIAN
          </button>

          {/* Tabs */}
          <div className="card p-0 overflow-hidden">
            <div className="flex border-b border-gray-200">
              {(["analytics", "exogenas", "detalle"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                    tab === t ? "text-brand-orange border-b-2 border-brand-orange bg-orange-50" : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {t === "analytics" && <BarChart2 size={14} />}
                  {t === "analytics" ? "Analítica" : t === "exogenas" ? "Exógenas" : "Detalle"}
                </button>
              ))}
            </div>

            {/* ── Analítica ── */}
            {tab === "analytics" && (
              <div className="p-6 space-y-6">
                <div className="flex flex-wrap gap-4">
                  <StatCard label="Total retenciones" value={fmt(totalRetencion)} sub={`${detalle.length} registros`} />
                  <StatCard label="Retenedores únicos" value={String(byRetenedor.length)} sub="en exógenas" />
                  <StatCard label="Conceptos" value={String(byConcepto.length)} />
                  <StatCard label="Archivos procesados" value={String(result.procesados)} sub={`de ${result.total_archivos}`} />
                </div>

                {byRetenedor.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                      <TrendingUp size={16} className="text-brand-orange" /> Top retenedores (por valor)
                    </h3>
                    <div className="space-y-2">
                      {byRetenedor.map((r) => (
                        <BarRow key={r.label} label={r.label} value={r.value} max={maxRetenedor} />
                      ))}
                    </div>
                  </div>
                )}

                {byConcepto.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                      <BarChart2 size={16} className="text-brand-orange" /> Retenciones por concepto
                    </h3>
                    <div className="space-y-2">
                      {byConcepto.map((r) => (
                        <BarRow key={r.label} label={r.label} value={r.value} max={maxConcepto} color="bg-blue-500" />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Tablas ── */}
            {(tab === "exogenas" || tab === "detalle") && (
              <div className="overflow-x-auto">
                <DataTable
                  rows={tab === "exogenas" ? f1003 : detalle}
                  priority={tab === "exogenas" ? PRIORITY_1003 : PRIORITY_DETALLE}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Chatbot flotante de exógenas ── */}
      <div className="fixed bottom-6 right-6 z-50">
        {chatOpen && (
          <div className="mb-3 w-96 bg-white border border-gray-200 rounded-2xl shadow-2xl flex flex-col overflow-hidden" style={{ height: "480px" }}>
            <div className="bg-brand-navy px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot size={18} className="text-brand-orange" />
                <span className="text-white text-sm font-semibold">Asistente Exógenas</span>
              </div>
              <button onClick={() => setChatOpen(false)} className="text-slate-400 hover:text-white">
                <ChevronDown size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
              {chatMsgs.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-xl px-3 py-2 text-xs whitespace-pre-wrap ${
                    m.role === "user" ? "bg-brand-orange text-white" : "bg-white border border-gray-200 text-gray-700"
                  }`}>
                    {m.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-xs text-gray-400">Escribiendo...</div>
                </div>
              )}
              <div ref={chatBottomRef} />
            </div>

            <div className="p-3 border-t border-gray-200 flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendChat()}
                placeholder="Pregunta sobre retenciones..."
                className="flex-1 input text-xs py-1.5"
              />
              <button onClick={sendChat} disabled={!chatInput.trim() || chatLoading} className="btn-primary px-3 py-1.5">
                <Send size={14} />
              </button>
            </div>
          </div>
        )}

        <button
          onClick={() => setChatOpen((p) => !p)}
          className="w-14 h-14 rounded-full bg-brand-orange shadow-lg flex items-center justify-center hover:bg-orange-600 transition-colors"
        >
          {chatOpen ? <ChevronDown size={22} className="text-white" /> : <Bot size={24} className="text-white" />}
        </button>
      </div>
    </div>
  );
}
