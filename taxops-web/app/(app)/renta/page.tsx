"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Plus, Trash2, ChevronRight, RefreshCw, User, FileText,
  AlertCircle, Upload, Loader2, CheckCircle, FolderOpen, Eye, Calculator,
} from "lucide-react";
import { useApi } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

type Contribuyente = {
  id: string;
  tipo_doc: string;
  numero_doc: string;
  nombre_completo: string;
  email: string | null;
  ciudad: string | null;
  año_gravable: number;
  estado: string;
  observaciones: string | null;
  datos_tributarios: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type ContribuyenteInfo = {
  contribuyente_id: string;
  num_docs: number;
  docs_pendientes: number;
  tiene_declaracion: boolean;
  estado: string;
  inconsistencias: unknown[];
};

type Documento = {
  id: string;
  filename: string;
  categoria: string;
  carpeta_virtual: string;
  confianza_clasificacion: number;
  estado_ocr: string;
  estado_validacion: string;
  size_bytes: number | null;
  mime_type: string | null;
  datos_extraidos: Record<string, unknown>;
  created_at: string;
};

type Declaracion = {
  id: string;
  contribuyente_id: string;
  año_gravable: number;
  patrimonio_bruto: number;
  patrimonio_liquido: number;
  ingresos_laborales: number;
  rentas_capital: number;
  rentas_no_laborales: number;
  dividendos: number;
  ganancias_ocasionales: number;
  rentas_exentas: number;
  deducciones: number;
  retenciones: number;
  impuesto_cargo: number;
  saldo_pagar: number;
  saldo_favor: number;
  estado: string;
  inconsistencias: { nivel: string; codigo: string; mensaje: string }[];
  detalle_calculo: Record<string, unknown>;
  updated_at: string;
};

// ─── Constants ────────────────────────────────────────────────────────────────

const ESTADO_LABELS: Record<string, { label: string; color: string }> = {
  pendiente_docs: { label: "Pendiente docs", color: "bg-yellow-100 text-yellow-800" },
  en_proceso:     { label: "En proceso",     color: "bg-blue-100 text-blue-800" },
  revision:       { label: "En revisión",    color: "bg-purple-100 text-purple-800" },
  completado:     { label: "Completado",     color: "bg-green-100 text-green-800" },
  presentado:     { label: "Presentado",     color: "bg-gray-100 text-gray-700" },
};

const TIPO_DOC_LABELS: Record<string, string> = {
  "13": "Cédula", "22": "Cédula Extranjería", "41": "Pasaporte", "31": "NIT",
};

const CATEGORIA_LABELS: Record<string, string> = {
  identificacion: "Identificación",
  ingresos:       "Ingresos",
  bancos:         "Bancos",
  patrimonio:     "Patrimonio",
  bienes:         "Bienes",
  salud:          "Salud",
  pensiones:      "Pensiones",
  tributario:     "Tributario",
  otros:          "Otros",
};

const OCR_COLORS: Record<string, string> = {
  pendiente:   "text-yellow-600",
  procesando:  "text-blue-600",
  completado:  "text-green-600",
  error:       "text-red-600",
};

const AÑOS = [2025, 2024, 2023];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtBytes(b: number | null): string {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function ConfidenceBadge({ v }: { v: number }) {
  const pct = Math.round(v * 100);
  const color = pct >= 80 ? "bg-green-100 text-green-700" : pct >= 50 ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-500";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${color}`}>{pct}%</span>;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RentaPage() {
  const { get, post, postForm, del } = useApi();

  const [contribuyentes, setContribuyentes] = useState<Contribuyente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtroAño, setFiltroAño] = useState<number | "">("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [selected, setSelected] = useState<Contribuyente | null>(null);
  const [info, setInfo] = useState<ContribuyenteInfo | null>(null);
  const [docs, setDocs] = useState<Documento[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);

  // Upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadJobId, setUploadJobId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState("");

  // Declaración state
  const [decl, setDecl] = useState<Declaracion | null>(null);
  const [declLoading, setDeclLoading] = useState(false);
  const [declError, setDeclError] = useState("");

  // Form state
  const [form, setForm] = useState({
    tipo_doc: "13", numero_doc: "", nombre_completo: "",
    email: "", telefono: "", ciudad: "", año_gravable: 2025, observaciones: "",
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // ── Load contribuyentes ────────────────────────────────────────────────────

  const loadContribuyentes = useCallback(async () => {
    setLoading(true); setError("");
    try {
      let path = "/renta/contribuyentes?";
      if (filtroAño) path += `año_gravable=${filtroAño}&`;
      if (filtroEstado) path += `estado=${filtroEstado}&`;
      setContribuyentes(await get<Contribuyente[]>(path));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar");
    } finally { setLoading(false); }
  }, [filtroAño, filtroEstado]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadContribuyentes(); }, [loadContribuyentes]);

  // ── Select contribuyente ──────────────────────────────────────────────────

  async function handleSelect(c: Contribuyente) {
    setSelected(c); setInfo(null); setDocs([]); setDecl(null); setUploadFiles([]); setUploadError(""); setDeclError("");
    try { setInfo(await get<ContribuyenteInfo>(`/renta/contribuyentes/${c.id}/info`)); } catch { /* optional */ }
    await loadDocs(c.id);
    try { setDecl(await get<Declaracion | null>(`/renta/contribuyentes/${c.id}/declaracion`)); } catch { /* optional */ }
  }

  async function handleCalcular() {
    if (!selected) return;
    setDeclLoading(true); setDeclError("");
    try {
      const result = await post<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/calcular`, {});
      setDecl(result);
      try { setInfo(await get<ContribuyenteInfo>(`/renta/contribuyentes/${selected.id}/info`)); } catch { /* optional */ }
    } catch (e: unknown) {
      setDeclError(e instanceof Error ? e.message : "Error calculando declaración");
    } finally { setDeclLoading(false); }
  }

  async function loadDocs(contrib_id: string) {
    setDocsLoading(true);
    try { setDocs(await get<Documento[]>(`/renta/contribuyentes/${contrib_id}/documentos`)); }
    catch { /* silent */ } finally { setDocsLoading(false); }
  }

  // ── Upload ────────────────────────────────────────────────────────────────

  function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const newFiles = Array.from(fileList);
    setUploadFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...newFiles.filter(f => !names.has(f.name))];
    });
  }

  async function handleUpload() {
    if (!selected || !uploadFiles.length) return;
    setUploading(true); setUploadError(""); setUploadProgress(0);
    try {
      const fd = new FormData();
      uploadFiles.forEach(f => fd.append("files", f));
      const { job_id } = await postForm<{ job_id: string; total: number }>(
        `/renta/contribuyentes/${selected.id}/documentos/upload`, fd
      );
      setUploadJobId(job_id);
      setUploadFiles([]);
      await pollJob(job_id, selected.id);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Error al subir");
    } finally { setUploading(false); }
  }

  async function pollJob(job_id: string, contrib_id: string) {
    for (let i = 0; i < 120; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const job = await get<{ status: string; progreso: number }>
          (`/renta/contribuyentes/${contrib_id}/documentos/jobs/${job_id}`);
        setUploadProgress(job.progreso);
        if (job.status === "done") { setUploadJobId(null); await loadDocs(contrib_id); return; }
        if (job.status === "error") { setUploadError("Error procesando documentos"); return; }
      } catch { break; }
    }
    setUploadJobId(null);
    await loadDocs(contrib_id);
  }

  async function handleDeleteDoc(doc_id: string) {
    if (!selected) return;
    if (!confirm("¿Eliminar este documento?")) return;
    try {
      await del(`/renta/contribuyentes/${selected.id}/documentos/${doc_id}`);
      setDocs(prev => prev.filter(d => d.id !== doc_id));
    } catch (e: unknown) { alert(e instanceof Error ? e.message : "Error"); }
  }

  function openPreview(doc_id: string) {
    if (!selected) return;
    window.open(`/api-proxy/renta/contribuyentes/${selected.id}/documentos/${doc_id}/preview`, "_blank");
  }

  // ── Create contribuyente ──────────────────────────────────────────────────

  async function handleCreate(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!form.numero_doc || !form.nombre_completo) { setFormError("Documento y nombre son obligatorios"); return; }
    setSaving(true); setFormError("");
    try {
      await post("/renta/contribuyentes", {
        ...form,
        email: form.email || null, telefono: form.telefono || null,
        ciudad: form.ciudad || null, observaciones: form.observaciones || null,
      });
      setShowForm(false);
      setForm({ tipo_doc: "13", numero_doc: "", nombre_completo: "", email: "", telefono: "", ciudad: "", año_gravable: 2025, observaciones: "" });
      loadContribuyentes();
    } catch (e: unknown) { setFormError(e instanceof Error ? e.message : "Error al guardar"); }
    finally { setSaving(false); }
  }

  async function handleDelete(id: string) {
    if (!confirm("¿Eliminar este contribuyente y todos sus documentos?")) return;
    try { await del(`/renta/contribuyentes/${id}`); if (selected?.id === id) setSelected(null); loadContribuyentes(); }
    catch (e: unknown) { alert(e instanceof Error ? e.message : "Error"); }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full gap-4">
      {/* ─── Lista ─── */}
      <div className="w-80 flex-shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Renta Personas</h1>
          <button onClick={() => setShowForm(true)}
            className="flex items-center gap-1 rounded-lg bg-[#E05519] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#c44a14]">
            <Plus size={14} /> Nuevo
          </button>
        </div>

        <div className="flex gap-2">
          <select value={filtroAño} onChange={e => setFiltroAño(e.target.value ? Number(e.target.value) : "")}
            className="flex-1 rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#E05519]">
            <option value="">Todos los años</option>
            {AÑOS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <select value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}
            className="flex-1 rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#E05519]">
            <option value="">Todos los estados</option>
            {Object.entries(ESTADO_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <button onClick={loadContribuyentes} className="rounded border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50">
            <RefreshCw size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto rounded-lg border border-gray-200 bg-white">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-sm text-gray-400">Cargando…</div>
          ) : error ? (
            <div className="flex h-32 items-center justify-center gap-2 text-sm text-red-500"><AlertCircle size={16} /> {error}</div>
          ) : contribuyentes.length === 0 ? (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-sm text-gray-400">
              <User size={24} className="text-gray-300" /><span>No hay contribuyentes</span>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {contribuyentes.map(c => {
                const est = ESTADO_LABELS[c.estado] ?? { label: c.estado, color: "bg-gray-100 text-gray-600" };
                return (
                  <li key={c.id}>
                    <button onClick={() => handleSelect(c)}
                      className={`w-full px-3 py-2.5 text-left transition-colors hover:bg-orange-50 ${selected?.id === c.id ? "bg-orange-50 border-l-2 border-[#E05519]" : ""}`}>
                      <div className="flex items-start justify-between gap-1">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-gray-900">{c.nombre_completo}</p>
                          <p className="text-xs text-gray-500">{TIPO_DOC_LABELS[c.tipo_doc] ?? c.tipo_doc}: {c.numero_doc}</p>
                          <p className="text-xs text-gray-400">AÑO {c.año_gravable}</p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${est.color}`}>{est.label}</span>
                          <ChevronRight size={12} className="text-gray-300" />
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {/* ─── Detalle ─── */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {!selected ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-400">
            <FileText size={48} className="text-gray-200" />
            <p className="text-sm">Selecciona un contribuyente para ver su expediente</p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">{selected.nombre_completo}</h2>
                <p className="text-sm text-gray-500">
                  {TIPO_DOC_LABELS[selected.tipo_doc] ?? selected.tipo_doc}: {selected.numero_doc} · Año {selected.año_gravable}
                </p>
                {selected.email && <p className="text-xs text-gray-400">{selected.email}</p>}
                {selected.ciudad && <p className="text-xs text-gray-400">{selected.ciudad}</p>}
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${ESTADO_LABELS[selected.estado]?.color ?? "bg-gray-100 text-gray-600"}`}>
                  {ESTADO_LABELS[selected.estado]?.label ?? selected.estado}
                </span>
                <button onClick={() => handleDelete(selected.id)}
                  className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500" title="Eliminar">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>

            {/* Info cards */}
            {info && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <InfoCard label="Documentos" value={info.num_docs} />
                <InfoCard label="Pendientes OCR" value={info.docs_pendientes} />
                <InfoCard label="Declaración" value={info.tiene_declaracion ? "Borrador" : "Sin datos"} />
                <InfoCard label="Inconsistencias" value={info.inconsistencias.length} highlight={info.inconsistencias.length > 0} />
              </div>
            )}

            {/* Upload panel */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <h3 className="mb-3 text-sm font-semibold text-gray-800">Cargar documentos</h3>

              <div
                onDragOver={e => { e.preventDefault(); }}
                onDrop={e => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
                onClick={() => fileInputRef.current?.click()}
                className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-200 p-6 text-center hover:border-[#E05519] hover:bg-orange-50 transition-colors"
              >
                <Upload size={24} className="text-gray-400" />
                <p className="text-sm text-gray-500">Arrastra archivos o <span className="text-[#E05519] font-medium">haz clic</span></p>
                <p className="text-xs text-gray-400">PDF · JPG · PNG · DOCX · XLSX — máx. 20 MB</p>
              </div>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.tiff,.webp,.docx,.xlsx,.xls"
                className="hidden" onChange={e => addFiles(e.target.files)} />

              {uploadFiles.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {uploadFiles.map(f => (
                    <li key={f.name} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-1.5 text-xs text-gray-700">
                      <span className="truncate max-w-xs">{f.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-400">{fmtBytes(f.size)}</span>
                        <button onClick={() => setUploadFiles(prev => prev.filter(x => x.name !== f.name))}
                          className="text-gray-400 hover:text-red-500">✕</button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {uploadError && (
                <p className="mt-2 flex items-center gap-1 text-xs text-red-500"><AlertCircle size={12} /> {uploadError}</p>
              )}

              {uploadJobId && (
                <div className="mt-3">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span className="flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Procesando…</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-gray-100">
                    <div className="h-1.5 rounded-full bg-[#E05519] transition-all" style={{ width: `${uploadProgress}%` }} />
                  </div>
                </div>
              )}

              {uploadFiles.length > 0 && !uploading && (
                <button onClick={handleUpload}
                  className="mt-3 w-full rounded-lg bg-[#E05519] px-4 py-2 text-sm font-medium text-white hover:bg-[#c44a14]">
                  Subir {uploadFiles.length} archivo{uploadFiles.length > 1 ? "s" : ""}
                </button>
              )}
            </div>

            {/* ─── Declaración panel ─── */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                  <Calculator size={15} /> Liquidación Art. 241 ET
                </h3>
                <button
                  onClick={handleCalcular}
                  disabled={declLoading}
                  className="flex items-center gap-1.5 rounded-lg bg-[#E05519] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#c44a14] disabled:opacity-50"
                >
                  {declLoading ? <Loader2 size={12} className="animate-spin" /> : <Calculator size={12} />}
                  {decl ? "Recalcular" : "Calcular declaración"}
                </button>
              </div>

              {declError && (
                <p className="mb-3 flex items-center gap-1 text-xs text-red-500"><AlertCircle size={12} /> {declError}</p>
              )}

              {decl ? (
                <div className="space-y-4">
                  {/* Resultado principal */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-lg bg-gray-50 p-3 text-center">
                      <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">Renta gravable</p>
                      <p className="text-base font-bold text-gray-900">{fmtCOP((decl.detalle_calculo as Record<string, Record<string, number>>)?.consolidado?.renta_gravable ?? 0)}</p>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3 text-center">
                      <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">Impuesto a cargo</p>
                      <p className="text-base font-bold text-gray-900">{fmtCOP(decl.impuesto_cargo)}</p>
                    </div>
                    <div className={`rounded-lg p-3 text-center ${decl.saldo_pagar > 0 ? "bg-red-50" : "bg-green-50"}`}>
                      <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">
                        {decl.saldo_pagar > 0 ? "Saldo a pagar" : "Saldo a favor"}
                      </p>
                      <p className={`text-base font-bold ${decl.saldo_pagar > 0 ? "text-red-600" : "text-green-600"}`}>
                        {fmtCOP(decl.saldo_pagar > 0 ? decl.saldo_pagar : decl.saldo_favor)}
                      </p>
                    </div>
                  </div>

                  {/* Tabla de cédula */}
                  <table className="w-full text-xs">
                    <tbody className="divide-y divide-gray-100">
                      <DeclRow label="Ingresos laborales"    value={decl.ingresos_laborales} />
                      <DeclRow label="Rentas de capital"     value={decl.rentas_capital} />
                      <DeclRow label="Rentas no laborales"   value={decl.rentas_no_laborales} />
                      <DeclRow label="(−) Rentas exentas"    value={decl.rentas_exentas}  negative />
                      <DeclRow label="(−) Deducciones"       value={decl.deducciones}     negative />
                      <DeclRow label="Retenciones en la fuente" value={decl.retenciones} />
                      <DeclRow label="Patrimonio bruto"      value={decl.patrimonio_bruto} />
                      <DeclRow label="Patrimonio líquido"    value={decl.patrimonio_liquido} />
                    </tbody>
                  </table>

                  {/* Tramo aplicado */}
                  {(decl.detalle_calculo as Record<string, Record<string, unknown>>)?.tramo_aplicado && (
                    <p className="text-[10px] text-gray-400">
                      Tramo: {((decl.detalle_calculo as Record<string, Record<string, number>>).tramo_aplicado.renta_en_uvt ?? 0).toFixed(1)} UVT
                      · Tarifa marginal {(((decl.detalle_calculo as Record<string, Record<string, number>>).tramo_aplicado.tarifa_marginal ?? 0) * 100).toFixed(0)}%
                      · UVT {fmtCOP((decl.detalle_calculo as Record<string, number>).uvt as number ?? 49799)}
                    </p>
                  )}

                  {/* Inconsistencias */}
                  {decl.inconsistencias.length > 0 && (
                    <div className="space-y-1">
                      {decl.inconsistencias.map((inc, i) => (
                        <div key={i} className={`flex items-start gap-2 rounded-lg p-2 text-xs ${inc.nivel === "advertencia" ? "bg-yellow-50 text-yellow-800" : "bg-blue-50 text-blue-700"}`}>
                          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
                          <span>{inc.mensaje}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <p className="text-[10px] text-gray-400 text-right">
                    Estado: <span className="font-medium">{decl.estado}</span>
                    {" · "}Actualizado: {new Date(decl.updated_at).toLocaleString("es-CO")}
                  </p>
                </div>
              ) : (
                <p className="text-center text-sm text-gray-400 py-4">
                  Presiona &quot;Calcular declaración&quot; para liquidar con los documentos cargados
                </p>
              )}
            </div>

            {/* Documentos list */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                  <FolderOpen size={15} /> Expediente ({docs.length})
                </h3>
                {selected && (
                  <button onClick={() => loadDocs(selected.id)} className="text-gray-400 hover:text-gray-600">
                    <RefreshCw size={13} />
                  </button>
                )}
              </div>

              {docsLoading ? (
                <div className="flex h-16 items-center justify-center text-sm text-gray-400">
                  <Loader2 size={16} className="animate-spin mr-2" /> Cargando documentos…
                </div>
              ) : docs.length === 0 ? (
                <p className="text-center text-sm text-gray-400 py-4">Sin documentos cargados</p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {docs.map(doc => (
                    <li key={doc.id} className="flex items-center justify-between py-2 gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-gray-800">{doc.filename}</p>
                        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                          <span className="text-xs text-gray-500">{CATEGORIA_LABELS[doc.categoria] ?? doc.categoria}</span>
                          {doc.confianza_clasificacion > 0 && <ConfidenceBadge v={doc.confianza_clasificacion} />}
                          <span className={`text-xs font-medium ${OCR_COLORS[doc.estado_ocr] ?? "text-gray-500"}`}>
                            {doc.estado_ocr === "completado" ? <CheckCircle size={11} className="inline mr-0.5" /> : null}
                            {doc.estado_ocr}
                          </span>
                          {doc.size_bytes && <span className="text-xs text-gray-400">{fmtBytes(doc.size_bytes)}</span>}
                        </div>
                        {doc.datos_extraidos && Object.keys(doc.datos_extraidos).length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {Object.entries(doc.datos_extraidos).slice(0, 3).map(([k, v]) => (
                              <span key={k} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
                                {k}: {String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {doc.estado_ocr === "completado" && (
                          <button onClick={() => openPreview(doc.id)}
                            className="rounded p-1 text-gray-400 hover:bg-blue-50 hover:text-blue-500" title="Ver documento">
                            <Eye size={15} />
                          </button>
                        )}
                        <button onClick={() => handleDeleteDoc(doc.id)}
                          className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500" title="Eliminar">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>

      {/* ─── Modal nuevo contribuyente ─── */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-base font-semibold text-gray-900">Nuevo contribuyente</h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="flex gap-2">
                <div className="w-36">
                  <label className="mb-1 block text-xs text-gray-600">Tipo doc</label>
                  <select value={form.tipo_doc} onChange={e => setForm({ ...form, tipo_doc: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 bg-white px-2 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#E05519]">
                    {Object.entries(TIPO_DOC_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-gray-600">Número documento *</label>
                  <input value={form.numero_doc} onChange={e => setForm({ ...form, numero_doc: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                    placeholder="1000123456" required />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-gray-600">Nombre completo *</label>
                <input value={form.nombre_completo} onChange={e => setForm({ ...form, nombre_completo: e.target.value })}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                  placeholder="Nombre Apellido" required />
              </div>

              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-gray-600">Email</label>
                  <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                    placeholder="correo@ejemplo.com" />
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-gray-600">Ciudad</label>
                  <input value={form.ciudad} onChange={e => setForm({ ...form, ciudad: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                    placeholder="Bogotá" />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-gray-600">Año gravable</label>
                <select value={form.año_gravable} onChange={e => setForm({ ...form, año_gravable: Number(e.target.value) })}
                  className="w-full rounded-lg border border-gray-200 bg-white px-2 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#E05519]">
                  {AÑOS.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs text-gray-600">Observaciones</label>
                <textarea value={form.observaciones} onChange={e => setForm({ ...form, observaciones: e.target.value })} rows={2}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                  placeholder="Notas adicionales…" />
              </div>

              {formError && <p className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={12} /> {formError}</p>}

              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => { setShowForm(false); setFormError(""); }}
                  className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">Cancelar</button>
                <button type="submit" disabled={saving}
                  className="rounded-lg bg-[#E05519] px-4 py-2 text-sm font-medium text-white hover:bg-[#c44a14] disabled:opacity-50">
                  {saving ? "Guardando…" : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoCard({ label, value, highlight }: { label: string; value: number | string; highlight?: boolean }) {
  return (
    <div className={`rounded-xl border p-3 text-center ${highlight ? "border-red-100 bg-red-50" : "border-gray-200 bg-white"}`}>
      <p className={`text-2xl font-bold ${highlight ? "text-red-600" : "text-gray-900"}`}>{value}</p>
      <p className="mt-0.5 text-xs text-gray-500">{label}</p>
    </div>
  );
}

function fmtCOP(v: number): string {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(v);
}

function DeclRow({ label, value, negative }: { label: string; value: number; negative?: boolean }) {
  if (value === 0) return null;
  return (
    <tr>
      <td className="py-1 text-gray-500">{label}</td>
      <td className={`py-1 text-right font-medium ${negative ? "text-red-600" : "text-gray-800"}`}>{fmtCOP(value)}</td>
    </tr>
  );
}
