"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, ChevronRight, RefreshCw, User, FileText, AlertCircle } from "lucide-react";
import { useApi } from "@/lib/api";

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

const ESTADO_LABELS: Record<string, { label: string; color: string }> = {
  pendiente_docs: { label: "Pendiente docs", color: "bg-yellow-100 text-yellow-800" },
  en_proceso:     { label: "En proceso",     color: "bg-blue-100 text-blue-800" },
  revision:       { label: "En revisión",    color: "bg-purple-100 text-purple-800" },
  completado:     { label: "Completado",     color: "bg-green-100 text-green-800" },
  presentado:     { label: "Presentado",     color: "bg-gray-100 text-gray-700" },
};

const TIPO_DOC_LABELS: Record<string, string> = {
  "13": "Cédula",
  "22": "Cédula Extrangería",
  "41": "Pasaporte",
  "31": "NIT",
};

const AÑOS = [2025, 2024, 2023];

export default function RentaPage() {
  const { get, post, del } = useApi();

  const [contribuyentes, setContribuyentes] = useState<Contribuyente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtroAño, setFiltroAño] = useState<number | "">("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [selected, setSelected] = useState<Contribuyente | null>(null);
  const [info, setInfo] = useState<ContribuyenteInfo | null>(null);

  const [form, setForm] = useState({
    tipo_doc: "13",
    numero_doc: "",
    nombre_completo: "",
    email: "",
    telefono: "",
    ciudad: "",
    año_gravable: 2025,
    observaciones: "",
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  async function loadContribuyentes() {
    setLoading(true);
    setError("");
    try {
      let path = "/renta/contribuyentes?";
      if (filtroAño) path += `año_gravable=${filtroAño}&`;
      if (filtroEstado) path += `estado=${filtroEstado}&`;
      const data = await get<Contribuyente[]>(path);
      setContribuyentes(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar contribuyentes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadContribuyentes(); }, [filtroAño, filtroEstado]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSelect(c: Contribuyente) {
    setSelected(c);
    setInfo(null);
    try {
      const d = await get<ContribuyenteInfo>(`/renta/contribuyentes/${c.id}/info`);
      setInfo(d);
    } catch {
      // info is optional
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.numero_doc || !form.nombre_completo) {
      setFormError("Documento y nombre son obligatorios");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      await post("/renta/contribuyentes", {
        ...form,
        email: form.email || null,
        telefono: form.telefono || null,
        ciudad: form.ciudad || null,
        observaciones: form.observaciones || null,
      });
      setShowForm(false);
      setForm({ tipo_doc: "13", numero_doc: "", nombre_completo: "", email: "", telefono: "", ciudad: "", año_gravable: 2025, observaciones: "" });
      loadContribuyentes();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("¿Eliminar este contribuyente y todos sus documentos?")) return;
    try {
      await del(`/renta/contribuyentes/${id}`);
      if (selected?.id === id) setSelected(null);
      loadContribuyentes();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error al eliminar");
    }
  }

  return (
    <div className="flex h-full gap-4">
      {/* ─── Lista de contribuyentes ─── */}
      <div className="w-80 flex-shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">Renta Personas</h1>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1 rounded-lg bg-[#E05519] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#c44a14]"
          >
            <Plus size={14} /> Nuevo
          </button>
        </div>

        {/* Filtros */}
        <div className="flex gap-2">
          <select
            value={filtroAño}
            onChange={(e) => setFiltroAño(e.target.value ? Number(e.target.value) : "")}
            className="flex-1 rounded border border-gray-200 px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
          >
            <option value="">Todos los años</option>
            {AÑOS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <select
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
            className="flex-1 rounded border border-gray-200 px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#E05519]"
          >
            <option value="">Todos los estados</option>
            {Object.entries(ESTADO_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
          <button onClick={loadContribuyentes} className="rounded border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50">
            <RefreshCw size={14} />
          </button>
        </div>

        {/* Lista */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-gray-200 bg-white">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-sm text-gray-400">Cargando…</div>
          ) : error ? (
            <div className="flex h-32 items-center justify-center gap-2 text-sm text-red-500">
              <AlertCircle size={16} /> {error}
            </div>
          ) : contribuyentes.length === 0 ? (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-sm text-gray-400">
              <User size={24} className="text-gray-300" />
              <span>No hay contribuyentes</span>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {contribuyentes.map((c) => {
                const est = ESTADO_LABELS[c.estado] ?? { label: c.estado, color: "bg-gray-100 text-gray-600" };
                return (
                  <li key={c.id}>
                    <button
                      onClick={() => handleSelect(c)}
                      className={`w-full px-3 py-2.5 text-left transition-colors hover:bg-orange-50 ${selected?.id === c.id ? "bg-orange-50 border-l-2 border-[#E05519]" : ""}`}
                    >
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

      {/* ─── Detalle contribuyente ─── */}
      <div className="flex-1 overflow-y-auto">
        {!selected ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-400">
            <FileText size={48} className="text-gray-200" />
            <p className="text-sm">Selecciona un contribuyente para ver su expediente</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">{selected.nombre_completo}</h2>
                <p className="text-sm text-gray-500">
                  {TIPO_DOC_LABELS[selected.tipo_doc] ?? selected.tipo_doc}: {selected.numero_doc} · Año gravable {selected.año_gravable}
                </p>
                {selected.email && <p className="mt-0.5 text-xs text-gray-400">{selected.email}</p>}
                {selected.ciudad && <p className="text-xs text-gray-400">{selected.ciudad}</p>}
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${ESTADO_LABELS[selected.estado]?.color ?? "bg-gray-100 text-gray-600"}`}>
                  {ESTADO_LABELS[selected.estado]?.label ?? selected.estado}
                </span>
                <button
                  onClick={() => handleDelete(selected.id)}
                  className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"
                  title="Eliminar contribuyente"
                >
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

            {/* Observaciones */}
            {selected.observaciones && (
              <div className="rounded-lg border border-yellow-100 bg-yellow-50 p-3 text-sm text-yellow-800">
                {selected.observaciones}
              </div>
            )}

            {/* Próximamente: upload documentos, declaración, chatbot tributario */}
            <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-400">
              Carga de documentos, OCR y motor de declaración — Semana 2
            </div>
          </div>
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
                  <select
                    value={form.tipo_doc}
                    onChange={(e) => setForm({ ...form, tipo_doc: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                  >
                    {Object.entries(TIPO_DOC_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-gray-600">Número documento *</label>
                  <input
                    value={form.numero_doc}
                    onChange={(e) => setForm({ ...form, numero_doc: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                    placeholder="1000123456"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-gray-600">Nombre completo *</label>
                <input
                  value={form.nombre_completo}
                  onChange={(e) => setForm({ ...form, nombre_completo: e.target.value })}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                  placeholder="Nombre Apellido"
                  required
                />
              </div>

              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-gray-600">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                    placeholder="correo@ejemplo.com"
                  />
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-gray-600">Ciudad</label>
                  <input
                    value={form.ciudad}
                    onChange={(e) => setForm({ ...form, ciudad: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                    placeholder="Bogotá"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-gray-600">Año gravable</label>
                <select
                  value={form.año_gravable}
                  onChange={(e) => setForm({ ...form, año_gravable: Number(e.target.value) })}
                  className="w-full rounded-lg border border-gray-200 px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                >
                  {AÑOS.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs text-gray-600">Observaciones</label>
                <textarea
                  value={form.observaciones}
                  onChange={(e) => setForm({ ...form, observaciones: e.target.value })}
                  rows={2}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#E05519]"
                  placeholder="Notas adicionales…"
                />
              </div>

              {formError && (
                <p className="flex items-center gap-1 text-xs text-red-500">
                  <AlertCircle size={12} /> {formError}
                </p>
              )}

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setFormError(""); }}
                  className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-[#E05519] px-4 py-2 text-sm font-medium text-white hover:bg-[#c44a14] disabled:opacity-50"
                >
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
