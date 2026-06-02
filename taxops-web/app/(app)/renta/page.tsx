"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Plus, Trash2, ChevronRight, RefreshCw, User, FileText,
  AlertCircle, Upload, Loader2, CheckCircle, FolderOpen, Eye, Calculator,
  Bot, Send, ChevronDown, Pencil, Download,
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
  // Campos S4:
  aportes_pension?: number;
  afc_fvp?: number;
  intereses_vivienda?: number;
  medicina_prepagada?: number;
  dependientes?: number;
  tipo_ganancia?: string | null;
  pasivos?: number;
  ajuste_manual?: Record<string, number> | null;
  estado: string;
  inconsistencias: { nivel: string; codigo: string; mensaje: string }[];
  detalle_calculo: Record<string, unknown>;
  updated_at: string;
};

type DatosTributarios = {
  ingresos_laborales: string;
  rentas_capital: string;
  rentas_no_laborales: string;
  aportes_pension: string;
  afc_fvp: string;
  retenciones: string;
  intereses_vivienda: string;
  medicina_prepagada: string;
  dependientes: string;
  dividendos: string;
  ganancias_ocasionales: string;
  tipo_ganancia: string;
  patrimonio_bruto: string;
  pasivos: string;
};

const DATOS_EMPTY: DatosTributarios = {
  ingresos_laborales: "", rentas_capital: "", rentas_no_laborales: "",
  aportes_pension: "", afc_fvp: "", retenciones: "",
  intereses_vivienda: "", medicina_prepagada: "", dependientes: "",
  dividendos: "", ganancias_ocasionales: "", tipo_ganancia: "venta_activo",
  patrimonio_bruto: "", pasivos: "",
};

type ChatMsg = { role: "user" | "assistant"; content: string };

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
  const { get, post, patch, postForm, del, getBlob } = useApi();

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
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

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

  // Datos tributarios (Zona A)
  const [datosForm, setDatosForm] = useState<DatosTributarios>(DATOS_EMPTY);
  const [datosTab, setDatosTab] = useState<"general" | "dividendos" | "ganancias" | "patrimonio">("general");
  const [datosOpen, setDatosOpen] = useState(false);
  const [datosSaving, setDatosSaving] = useState(false);
  const [datosError, setDatosError] = useState("");

  // Editor post-cálculo (Zona B)
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [editingField, setEditingField] = useState<string | null>(null);

  // Chatbot state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([{
    role: "assistant",
    content: "Hola, soy tu asistente de renta. Puedo ayudarte con el Art. 241 ET 2025, tabla de UVT, cédula general, rentas exentas y deducciones admisibles para personas naturales. ¿Qué necesitas?",
  }]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMsgs]);

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
    setSelected(c); setInfo(null); setDocs([]); setDecl(null); setUploadFiles([]);
    setUploadError(""); setDeclError(""); setOverrides({}); setEditingField(null); setSelectedDocs(new Set());
    try { setInfo(await get<ContribuyenteInfo>(`/renta/contribuyentes/${c.id}/info`)); } catch { /* optional */ }
    await loadDocs(c.id);
    try {
      const result = await get<Declaracion | null>(`/renta/contribuyentes/${c.id}/declaracion`);
      setDecl(result);
      if (result) {
        setDatosForm({
          ingresos_laborales:    String(result.ingresos_laborales || ""),
          rentas_capital:        String(result.rentas_capital || ""),
          rentas_no_laborales:   String(result.rentas_no_laborales || ""),
          aportes_pension:       String(result.aportes_pension || ""),
          afc_fvp:               String(result.afc_fvp || ""),
          retenciones:           String(result.retenciones || ""),
          intereses_vivienda:    String(result.intereses_vivienda || ""),
          medicina_prepagada:    String(result.medicina_prepagada || ""),
          dependientes:          String(result.dependientes || ""),
          dividendos:            String(result.dividendos || ""),
          ganancias_ocasionales: String(result.ganancias_ocasionales || ""),
          tipo_ganancia:         result.tipo_ganancia || "venta_activo",
          patrimonio_bruto:      String(result.patrimonio_bruto || ""),
          pasivos:               String(result.pasivos || ""),
        });
      } else {
        setDatosForm(DATOS_EMPTY);
      }
    } catch { /* optional */ }
  }

  async function handleCalcular() {
    if (!selected) return;
    setDeclLoading(true); setDeclError("");
    try {
      const body = Object.keys(overrides).length > 0 ? { ajuste_manual: overrides } : {};
      const result = await post<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/calcular`, body);
      setDecl(result);
      try { setInfo(await get<ContribuyenteInfo>(`/renta/contribuyentes/${selected.id}/info`)); } catch { /* optional */ }
    } catch (e: unknown) {
      setDeclError(e instanceof Error ? e.message : "Error calculando declaración");
    } finally { setDeclLoading(false); }
  }

  async function handleGuardarDatos() {
    if (!selected) return;
    setDatosSaving(true); setDatosError("");
    try {
      const num = (v: string) => v === "" ? undefined : parseFloat(v.replace(/[^0-9.-]/g, ""));
      const body: Record<string, unknown> = {
        ingresos_laborales:    num(datosForm.ingresos_laborales),
        rentas_capital:        num(datosForm.rentas_capital),
        rentas_no_laborales:   num(datosForm.rentas_no_laborales),
        aportes_pension:       num(datosForm.aportes_pension),
        afc_fvp:               num(datosForm.afc_fvp),
        retenciones:           num(datosForm.retenciones),
        intereses_vivienda:    num(datosForm.intereses_vivienda),
        medicina_prepagada:    num(datosForm.medicina_prepagada),
        dependientes:          datosForm.dependientes ? parseInt(datosForm.dependientes) : undefined,
        dividendos:            num(datosForm.dividendos),
        ganancias_ocasionales: num(datosForm.ganancias_ocasionales),
        tipo_ganancia:         datosForm.ganancias_ocasionales ? datosForm.tipo_ganancia : undefined,
        patrimonio_bruto:      num(datosForm.patrimonio_bruto),
        pasivos:               num(datosForm.pasivos),
      };
      Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);
      const result = await patch<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/datos`, body);
      setDecl(result);
    } catch (e: unknown) {
      setDatosError(e instanceof Error ? e.message : "Error guardando datos");
    } finally { setDatosSaving(false); }
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

  async function handleBulkDelete() {
    if (!selected || selectedDocs.size === 0) return;
    if (!confirm(`¿Eliminar ${selectedDocs.size} documento(s) seleccionado(s)?`)) return;
    setBulkDeleting(true);
    try {
      await Promise.all(
        Array.from(selectedDocs).map(id =>
          del(`/renta/contribuyentes/${selected.id}/documentos/${id}`).catch(() => null)
        )
      );
      setDocs(prev => prev.filter(d => !selectedDocs.has(d.id)));
      setSelectedDocs(new Set());
    } finally {
      setBulkDeleting(false);
    }
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

  // ── Chatbot ───────────────────────────────────────────────────────────────

  async function sendChat() {
    const text = chatInput.trim();
    if (!text || chatLoading) return;
    setChatInput("");
    const userMsg: ChatMsg = { role: "user", content: text };
    setChatMsgs(p => [...p, userMsg]);
    setChatLoading(true);

    const contextNote = selected
      ? `\n\n[Contexto: contribuyente "${selected.nombre_completo}", año gravable ${selected.año_gravable}${decl ? `, impuesto a cargo ${decl.impuesto_cargo.toLocaleString("es-CO")} COP` : ""}.]`
      : "";

    try {
      const res = await post<{ content: string }>("/chatbot/ask", {
        message: text + contextNote,
        provider: "groq",
        model: "llama-3.3-70b-versatile",
        history: chatMsgs.slice(-8),
        system_prompt: "Eres un experto contable colombiano especializado en declaración de renta personas naturales. Conoces el Art. 241 ET 2025, la tabla progresiva en UVT ($49,799), cédula general, rentas exentas Art. 206 numeral 10, deducciones admisibles, patrimonio y el sistema de retenciones en la fuente. Responde de forma clara y práctica.",
      });
      setChatMsgs(p => [...p, { role: "assistant", content: res.content }]);
    } catch {
      setChatMsgs(p => [...p, { role: "assistant", content: "Error de conexión. Intenta de nuevo." }]);
    } finally {
      setChatLoading(false);
    }
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

            {/* ─── Zona A: Formulario datos tributarios ─── */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <button
                onClick={() => setDatosOpen(p => !p)}
                className="flex w-full items-center justify-between text-sm font-semibold text-gray-800"
              >
                <span className="flex items-center gap-2"><FileText size={15} /> Datos tributarios</span>
                <ChevronRight size={14} className={`transition-transform ${datosOpen ? "rotate-90" : ""}`} />
              </button>

              {datosOpen && (
                <div className="mt-3">
                  <div className="flex gap-1 mb-3 border-b border-gray-200">
                    {(["general", "dividendos", "ganancias", "patrimonio"] as const).map(tab => (
                      <button key={tab} onClick={() => setDatosTab(tab)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-t transition-colors ${datosTab === tab ? "bg-[#E05519] text-white" : "text-gray-500 hover:text-gray-800"}`}>
                        {tab === "general" ? "Cédula General" : tab === "dividendos" ? "Dividendos" : tab === "ganancias" ? "Gan. Ocasionales" : "Patrimonio"}
                      </button>
                    ))}
                  </div>

                  {datosTab === "general" && (
                    <div className="grid grid-cols-2 gap-2">
                      {([
                        ["ingresos_laborales",  "Ingresos laborales"],
                        ["rentas_capital",      "Rentas de capital"],
                        ["rentas_no_laborales", "Rentas no laborales"],
                        ["aportes_pension",     "Aportes pensión (INCR)"],
                        ["afc_fvp",             "AFC / FVP / AVC"],
                        ["retenciones",         "Retenciones del año"],
                        ["intereses_vivienda",  "Intereses vivienda"],
                        ["medicina_prepagada",  "Medicina prepagada"],
                      ] as [keyof DatosTributarios, string][]).map(([k, label]) => (
                        <div key={k}>
                          <label className="block text-[10px] text-gray-500 mb-0.5">{label}</label>
                          <input type="number" value={datosForm[k]}
                            onChange={e => setDatosForm(p => ({ ...p, [k]: e.target.value }))}
                            className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                            placeholder="0" />
                        </div>
                      ))}
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">Dependientes económicos</label>
                        <input type="number" min="0" max="4" value={datosForm.dependientes}
                          onChange={e => setDatosForm(p => ({ ...p, dependientes: e.target.value }))}
                          className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                          placeholder="0" />
                      </div>
                    </div>
                  )}

                  {datosTab === "dividendos" && (
                    <div>
                      <label className="block text-[10px] text-gray-500 mb-0.5">Dividendos gravados 2017+ (cas. 107)</label>
                      <input type="number" value={datosForm.dividendos}
                        onChange={e => setDatosForm(p => ({ ...p, dividendos: e.target.value }))}
                        className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                        placeholder="0" />
                      <p className="mt-2 text-[10px] text-gray-400">Tarifa: 0% hasta 300 UVT · 15% sobre el exceso (Art. 242 ET)</p>
                    </div>
                  )}

                  {datosTab === "ganancias" && (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">Tipo de ganancia</label>
                        <select value={datosForm.tipo_ganancia}
                          onChange={e => setDatosForm(p => ({ ...p, tipo_ganancia: e.target.value }))}
                          className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]">
                          <option value="venta_activo">Venta activo fijo &gt;2 años — 10%</option>
                          <option value="herencia">Herencia / donación — 10%</option>
                          <option value="loteria">Lotería / rifa — 20%</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">Valor ganancia ocasional</label>
                        <input type="number" value={datosForm.ganancias_ocasionales}
                          onChange={e => setDatosForm(p => ({ ...p, ganancias_ocasionales: e.target.value }))}
                          className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                          placeholder="0" />
                      </div>
                    </div>
                  )}

                  {datosTab === "patrimonio" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">Patrimonio bruto (cas. 29)</label>
                        <input type="number" value={datosForm.patrimonio_bruto}
                          onChange={e => setDatosForm(p => ({ ...p, patrimonio_bruto: e.target.value }))}
                          className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                          placeholder="0" />
                      </div>
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">Pasivos / deudas (cas. 30)</label>
                        <input type="number" value={datosForm.pasivos}
                          onChange={e => setDatosForm(p => ({ ...p, pasivos: e.target.value }))}
                          className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
                          placeholder="0" />
                      </div>
                    </div>
                  )}

                  {datosError && (
                    <p className="mt-2 flex items-center gap-1 text-xs text-red-500"><AlertCircle size={12} /> {datosError}</p>
                  )}

                  <button onClick={handleGuardarDatos} disabled={datosSaving}
                    className="mt-3 w-full rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">
                    {datosSaving ? "Guardando…" : "Guardar datos tributarios"}
                  </button>
                </div>
              )}
            </div>

            {/* ─── Declaración panel ─── */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                  <Calculator size={15} /> Liquidación Art. 241 ET
                </h3>
                <div className="flex items-center gap-2">
                  {Object.keys(overrides).length > 0 && (
                    <button onClick={handleCalcular} disabled={declLoading}
                      className="text-xs text-[#E05519] underline hover:text-[#c44a14]">
                      Recalcular con ajustes
                    </button>
                  )}
                  <button
                    onClick={handleCalcular}
                    disabled={declLoading}
                    className="flex items-center gap-1.5 rounded-lg bg-[#E05519] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#c44a14] disabled:opacity-50"
                  >
                    {declLoading ? <Loader2 size={12} className="animate-spin" /> : <Calculator size={12} />}
                    {decl ? "Recalcular" : "Calcular declaración"}
                  </button>
                </div>
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

                  {/* Tabla de cédula — Zona B con editor */}
                  <table className="w-full text-xs">
                    <tbody className="divide-y divide-gray-100">
                      {([
                        ["ingresos_laborales",  "Ingresos laborales",       false],
                        ["rentas_capital",      "Rentas de capital",        false],
                        ["rentas_no_laborales", "Rentas no laborales",      false],
                        ["rentas_exentas",      "(−) Rentas exentas",       true],
                        ["deducciones",         "(−) Deducciones",          true],
                        ["retenciones",         "Retenciones en la fuente", false],
                        ["patrimonio_bruto",    "Patrimonio bruto",         false],
                        ["patrimonio_liquido",  "Patrimonio líquido",       false],
                      ] as [keyof Declaracion, string, boolean][]).map(([campo, label, negative]) => (
                        <DeclRow
                          key={campo}
                          label={label}
                          value={decl[campo] as number ?? 0}
                          campo={campo}
                          negative={negative}
                          overrides={overrides}
                          editingField={editingField}
                          onEdit={f => setEditingField(f)}
                          onSave={() => setEditingField(null)}
                          onOverrideChange={(f, v) => setOverrides(p => ({ ...p, [f]: v }))}
                        />
                      ))}
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

                  {/* Inconsistencias del motor */}
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

            {/* ─── Zona C: Validaciones + PDF ─── */}
            {decl && (() => {
              const ingresosTotales = (decl.ingresos_laborales || 0) + (decl.rentas_capital || 0)
                + (decl.rentas_no_laborales || 0) + (decl.dividendos || 0);
              const bloqueos: string[] = [];
              const advertencias: string[] = [];

              if (ingresosTotales === 0)
                bloqueos.push("Sin ingresos declarados en ninguna cédula");

              const tope40 = ingresosTotales * 0.40;
              const exentasDeduc = (decl.rentas_exentas || 0) + (decl.deducciones || 0);
              if (exentasDeduc > tope40 && ingresosTotales > 0)
                advertencias.push(`Rentas exentas + deducciones (${fmtCOP(exentasDeduc)}) superan el 40% de ingresos netos — Art. 336 ET`);

              if ((decl.retenciones || 0) > (decl.impuesto_cargo || 0) && (decl.impuesto_cargo || 0) > 0)
                advertencias.push("Retenciones superiores al impuesto a cargo — saldo a favor probable");

              if ((decl.patrimonio_bruto || 0) === 0 && ingresosTotales > 0)
                advertencias.push("Patrimonio bruto $0 con ingresos declarados — verificar activos");

              decl.inconsistencias.forEach(inc => {
                if (inc.nivel === "advertencia") advertencias.push(inc.mensaje);
              });

              return (
                <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-2">
                  <h3 className="text-sm font-semibold text-gray-800">Validaciones</h3>
                  {bloqueos.map((b, i) => (
                    <div key={i} className="flex items-start gap-2 rounded-lg bg-red-50 p-2 text-xs text-red-700">
                      <AlertCircle size={12} className="mt-0.5 flex-shrink-0" /> {b}
                    </div>
                  ))}
                  {advertencias.map((a, i) => (
                    <div key={i} className="flex items-start gap-2 rounded-lg bg-yellow-50 p-2 text-xs text-yellow-800">
                      <AlertCircle size={12} className="mt-0.5 flex-shrink-0" /> {a}
                    </div>
                  ))}
                  {bloqueos.length === 0 && advertencias.length === 0 && (
                    <p className="text-xs text-green-600 flex items-center gap-1">
                      <CheckCircle size={12} /> Sin inconsistencias detectadas
                    </p>
                  )}
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={async () => {
                        try {
                          const blob = await getBlob(`/renta/contribuyentes/${selected!.id}/declaracion/pdf`);
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `formulario210_${selected?.año_gravable ?? 2025}.pdf`;
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch { /* silent */ }
                      }}
                      className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">
                      <Download size={12} /> PDF
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          const blob = await getBlob(`/renta/contribuyentes/${selected!.id}/declaracion/excel`);
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `formulario210_${selected?.año_gravable ?? 2025}.xlsx`;
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch { /* silent */ }
                      }}
                      className="flex items-center gap-1.5 rounded-lg border border-green-200 px-3 py-1.5 text-xs text-green-700 hover:bg-green-50">
                      <Download size={12} /> Excel
                    </button>
                    <button
                      onClick={async () => {
                        if (!selected || bloqueos.length > 0) return;
                        try {
                          const result = await patch<Declaracion>(`/renta/contribuyentes/${selected.id}/declaracion/datos`, { estado: "revision" });
                          setDecl(result);
                        } catch { /* silent */ }
                      }}
                      disabled={bloqueos.length > 0}
                      className="flex-1 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-40">
                      {decl?.estado === "revision" ? "✓ Lista para presentar" : "Marcar lista para presentar"}
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* Documentos list */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                  <FolderOpen size={15} /> Expediente ({docs.length})
                </h3>
                <div className="flex items-center gap-2">
                  {selectedDocs.size > 0 && (
                    <button
                      onClick={handleBulkDelete}
                      disabled={bulkDeleting}
                      className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium text-red-600 border border-red-200 hover:bg-red-50 disabled:opacity-50">
                      {bulkDeleting ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                      Eliminar ({selectedDocs.size})
                    </button>
                  )}
                  {selected && (
                    <button onClick={() => loadDocs(selected.id)} className="text-gray-400 hover:text-gray-600">
                      <RefreshCw size={13} />
                    </button>
                  )}
                </div>
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
                      <input
                        type="checkbox"
                        checked={selectedDocs.has(doc.id)}
                        onChange={e => setSelectedDocs(prev => {
                          const next = new Set(prev);
                          e.target.checked ? next.add(doc.id) : next.delete(doc.id);
                          return next;
                        })}
                        className="flex-shrink-0 rounded border-gray-300 text-red-500 cursor-pointer"
                      />
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

      {/* ─── Chatbot flotante ─── */}
      <div className="fixed bottom-6 right-6 z-50">
        {chatOpen && (
          <div className="mb-3 w-96 bg-white border border-gray-200 rounded-2xl shadow-2xl flex flex-col overflow-hidden" style={{ height: "480px" }}>
            <div className="bg-[#0F172A] px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot size={18} className="text-[#E05519]" />
                <span className="text-white text-sm font-semibold">Asistente Renta</span>
              </div>
              <button onClick={() => setChatOpen(false)} className="text-slate-400 hover:text-white">
                <ChevronDown size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
              {chatMsgs.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-xl px-3 py-2 text-xs whitespace-pre-wrap ${
                    m.role === "user" ? "bg-[#E05519] text-white" : "bg-white border border-gray-200 text-gray-700"
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
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendChat()}
                placeholder="Pregunta sobre renta personas naturales..."
                className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
              />
              <button onClick={sendChat} disabled={!chatInput.trim() || chatLoading}
                className="rounded-lg bg-[#E05519] px-3 py-1.5 text-white hover:bg-[#c44a14] disabled:opacity-50">
                <Send size={14} />
              </button>
            </div>
          </div>
        )}

        <button
          onClick={() => setChatOpen(p => !p)}
          className="w-14 h-14 rounded-full bg-[#E05519] shadow-lg flex items-center justify-center hover:bg-[#c44a14] transition-colors"
        >
          {chatOpen ? <ChevronDown size={22} className="text-white" /> : <Bot size={24} className="text-white" />}
        </button>
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

function DeclRow({
  label, value, campo, negative, overrides, editingField, onEdit, onSave, onOverrideChange,
}: {
  label: string; value: number; campo: string; negative?: boolean;
  overrides: Record<string, number>;
  editingField: string | null;
  onEdit: (campo: string) => void;
  onSave: () => void;
  onOverrideChange: (campo: string, val: number) => void;
}) {
  const isOverridden = campo in overrides;
  const isEditing = editingField === campo;
  const displayVal = isOverridden ? overrides[campo] : value;
  if (displayVal === 0 && !isOverridden) return null;

  return (
    <tr className="group">
      <td className="py-1 text-gray-500">{label}</td>
      <td className={`py-1 text-right font-medium ${negative ? "text-red-600" : "text-gray-800"}`}>
        {isEditing ? (
          <input
            type="number"
            autoFocus
            defaultValue={displayVal}
            onBlur={e => { onOverrideChange(campo, parseFloat(e.target.value) || 0); onSave(); }}
            onKeyDown={e => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="w-28 rounded border border-[#E05519] bg-white px-1 py-0.5 text-xs text-right text-gray-900 focus:outline-none"
          />
        ) : (
          <span className="flex items-center justify-end gap-1">
            {isOverridden && (
              <span className="rounded bg-orange-100 px-1 py-0.5 text-[9px] font-semibold text-orange-700">manual</span>
            )}
            {fmtCOP(displayVal)}
            <button onClick={() => onEdit(campo)}
              className="ml-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-[#E05519] transition-opacity">
              <Pencil size={11} />
            </button>
          </span>
        )}
      </td>
    </tr>
  );
}
