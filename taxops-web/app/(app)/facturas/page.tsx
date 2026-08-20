"use client";

import { useState, useRef } from "react";
import { Upload, Download, X, AlertCircle, CheckCircle, Plus, Trash2, BarChart2, TrendingUp } from "lucide-react";
import { useApi } from "@/lib/api";
import { uploadFiles } from "@/lib/directUpload";
import { PageChatbot } from "@/components/PageChatbot";

type IngresoRow = { periodo: string; gravados: string; excluidos: string };
type ProcessResult = {
  total_archivos: number;
  procesados: number;
  errores: number;
  db_nuevas: number;
  db_duplicadas: number;
  df_base: Record<string, unknown>[];
  df_val: Record<string, unknown>[];
  df_pror: Record<string, unknown>[];
};

const TABS = ["Analítica", "Base Datos", "Validación", "Prorrateo IVA"] as const;

export default function FacturasPage() {
  const { post } = useApi();
  const fileRef = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [ingresos, setIngresos] = useState<IngresoRow[]>([
    { periodo: "", gravados: "", excluidos: "" },
  ]);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>("Analítica");
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");

  function addFiles(newFiles: FileList | null) {
    if (!newFiles) return;
    const valid = Array.from(newFiles).filter(
      (f) => f.name.endsWith(".pdf") || f.name.endsWith(".xml")
    );
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...valid.filter((f) => !names.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  }

  function updateIngreso(idx: number, field: keyof IngresoRow, val: string) {
    setIngresos((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: val } : r)));
  }

  async function handleProcess() {
    if (!files.length) {
      setError("Agrega al menos un archivo PDF o XML");
      return;
    }
    setError("");
    setLoading(true);
    setUploadProgress(0);
    setResult(null);

    const validIngresos = ingresos.filter((r) => r.periodo.match(/^\d{4}-\d{2}$/));
    const ingresosPayload = validIngresos.map((r) => ({
      periodo: r.periodo,
      gravados: parseFloat(r.gravados || "0"),
      excluidos: parseFloat(r.excluidos || "0"),
    }));

    const uploaded = await uploadFiles(files, "facturas", setUploadProgress);
    const failed = uploaded.filter((u) => u.error);
    if (failed.length) {
      setError(`Fallo la subida de: ${failed.map((f) => `${f.filename} (${f.error})`).join(", ")}`);
      setLoading(false);
      return;
    }

    try {
      const data = await post<ProcessResult>("/invoices/process", {
        s3_keys: uploaded.map((u) => u.s3_key),
        ingresos: ingresosPayload,
      });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al procesar");
    } finally {
      setLoading(false);
    }
  }

  async function handleExport() {
    if (!result) return;
    const blob = await post<Blob>("/invoices/export", {
      df_base: result.df_base,
      df_val: result.df_val,
      df_pror: result.df_pror,
    }, true);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "taxops_facturas.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }

  const currentData =
    activeTab === "Base Datos"
      ? result?.df_base
      : activeTab === "Validación"
      ? result?.df_val
      : activeTab === "Prorrateo IVA"
      ? result?.df_pror
      : [];

  /* ─── Analítica ─── */
  const base = result?.df_base ?? [];
  function sumCol(rows: Record<string, unknown>[], col: string) {
    return rows.reduce((acc, r) => {
      const v = parseFloat(String(r[col] ?? "0").replace(/[^0-9.-]/g, ""));
      return acc + (isNaN(v) ? 0 : v);
    }, 0);
  }
  function groupBy(rows: Record<string, unknown>[], key: string, valueCol: string) {
    const map: Record<string, number> = {};
    rows.forEach((r) => {
      const k = String(r[key] ?? "—");
      const v = parseFloat(String(r[valueCol] ?? "0").replace(/[^0-9.-]/g, ""));
      map[k] = (map[k] ?? 0) + (isNaN(v) ? 0 : v);
    });
    return Object.entries(map).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }
  function fmt(n: number) {
    return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);
  }

  const totalBaseCol = base.length ? ["base_iva", "base_gravable", "base", "valor_total"].find((c) => c in base[0]) ?? "" : "";
  const ivaCol = base.length ? ["iva", "valor_iva", "impuesto"].find((c) => c in base[0]) ?? "" : "";
  const provCol = base.length ? ["proveedor", "razon_social", "nombre"].find((c) => c in base[0]) ?? "" : "";

  const totalBase = sumCol(base, totalBaseCol);
  const totalIva = sumCol(base, ivaCol);
  const byProv = provCol ? groupBy(base, provCol, totalBaseCol).slice(0, 10) : [];
  const maxProv = byProv[0]?.value ?? 0;

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Upload zone */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4">Subir documentos</h2>

        <div
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-brand-orange transition-colors cursor-pointer"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            addFiles(e.dataTransfer.files);
          }}
        >
          <Upload size={32} className="text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-600 font-medium">
            Arrastra PDF/XML aquí o{" "}
            <span className="text-brand-orange">haz clic para seleccionar</span>
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Facturas electrónicas, Notas Crédito/Débito, Documentos Soporte
          </p>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.xml"
            className="hidden"
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

        {files.length > 0 && (
          <div className="mt-4 space-y-1 max-h-40 overflow-y-auto">
            {files.map((f) => (
              <div
                key={f.name}
                className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded-lg text-sm"
              >
                <span className="truncate text-gray-700">{f.name}</span>
                <button
                  onClick={() => removeFile(f.name)}
                  className="text-gray-400 hover:text-red-500 ml-2 shrink-0"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ingresos prorrateo */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-1">
          Ingresos para prorrateo IVA{" "}
          <span className="text-gray-400 font-normal text-xs">(Art. 490 ET — opcional)</span>
        </h2>
        <p className="text-xs text-gray-400 mb-4">
          Si no ingresas datos, se usa 100% deducible sin prorrateo.
        </p>

        <div className="space-y-2">
          {ingresos.map((row, i) => (
            <div key={i} className="grid grid-cols-3 gap-2">
              <input
                className="input"
                placeholder="YYYY-MM"
                value={row.periodo}
                onChange={(e) => updateIngreso(i, "periodo", e.target.value)}
              />
              <input
                className="input"
                type="number"
                placeholder="Gravados $"
                value={row.gravados}
                onChange={(e) => updateIngreso(i, "gravados", e.target.value)}
              />
              <div className="flex gap-2">
                <input
                  className="input flex-1"
                  type="number"
                  placeholder="Excluidos $"
                  value={row.excluidos}
                  onChange={(e) => updateIngreso(i, "excluidos", e.target.value)}
                />
                {ingresos.length > 1 && (
                  <button
                    onClick={() => setIngresos((prev) => prev.filter((_, j) => j !== i))}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={() => setIngresos((prev) => [...prev, { periodo: "", gravados: "", excluidos: "" }])}
          className="mt-2 text-sm text-brand-orange hover:underline flex items-center gap-1"
        >
          <Plus size={14} /> Agregar mes
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle size={16} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Process button */}
      <div className="space-y-2">
        <button
          onClick={handleProcess}
          disabled={loading || !files.length}
          className="btn-primary px-8"
        >
          {loading
            ? uploadProgress < 100
              ? `Subiendo... ${uploadProgress}%`
              : "Procesando..."
            : `Procesar ${files.length} archivo${files.length !== 1 ? "s" : ""}`}
        </button>
        {loading && uploadProgress < 100 && (
          <div className="w-full max-w-xs bg-gray-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-1.5 bg-brand-orange transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="flex flex-wrap gap-4">
            <Pill icon={<CheckCircle size={14} />} label={`${result.procesados} procesadas`} color="emerald" />
            <Pill icon={<AlertCircle size={14} />} label={`${result.errores} errores`} color="red" />
            <Pill icon={<CheckCircle size={14} />} label={`${result.db_nuevas} nuevas en DB`} color="blue" />
            {result.db_duplicadas > 0 && (
              <Pill icon={<AlertCircle size={14} />} label={`${result.db_duplicadas} duplicadas`} color="yellow" />
            )}
          </div>

          {/* Export */}
          <button onClick={handleExport} className="btn-secondary flex items-center gap-2">
            <Download size={16} />
            Exportar Excel (3 hojas)
          </button>

          {/* Tabs */}
          <div className="card p-0 overflow-hidden">
            <div className="flex border-b border-gray-200 overflow-x-auto">
              {TABS.map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                    activeTab === t
                      ? "text-brand-orange border-b-2 border-brand-orange bg-orange-50"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {t === "Analítica" && <BarChart2 size={14} />}
                  {t}
                  {t !== "Analítica" && (
                    <span className="text-xs text-gray-400">
                      ({activeTab === t ? (currentData?.length ?? 0) : ""})
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* ── Analítica ── */}
            {activeTab === "Analítica" && (
              <div className="p-6 space-y-6">
                {/* KPIs */}
                <div className="flex flex-wrap gap-4">
                  <div className="card flex-1 min-w-[150px]">
                    <p className="text-xs text-gray-400 mb-1">Total base gravable</p>
                    <p className="text-xl font-bold text-gray-900">{fmt(totalBase)}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{base.length} facturas</p>
                  </div>
                  <div className="card flex-1 min-w-[150px]">
                    <p className="text-xs text-gray-400 mb-1">Total IVA</p>
                    <p className="text-xl font-bold text-gray-900">{fmt(totalIva)}</p>
                  </div>
                  <div className="card flex-1 min-w-[150px]">
                    <p className="text-xs text-gray-400 mb-1">Procesadas</p>
                    <p className="text-xl font-bold text-gray-900">{result.procesados}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{result.db_nuevas} nuevas en DB</p>
                  </div>
                  <div className="card flex-1 min-w-[150px]">
                    <p className="text-xs text-gray-400 mb-1">Errores / Duplicadas</p>
                    <p className="text-xl font-bold text-gray-900">{result.errores} / {result.db_duplicadas}</p>
                  </div>
                </div>

                {/* Top proveedores */}
                {byProv.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                      <TrendingUp size={16} className="text-brand-orange" /> Top proveedores por base gravable
                    </h3>
                    <div className="space-y-2">
                      {byProv.map((r) => (
                        <div key={r.label} className="flex items-center gap-3 text-xs">
                          <span className="w-44 truncate text-gray-600 shrink-0" title={r.label}>{r.label}</span>
                          <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                            <div className="h-2 rounded-full bg-brand-orange" style={{ width: `${maxProv > 0 ? (r.value / maxProv) * 100 : 0}%` }} />
                          </div>
                          <span className="w-28 text-right text-gray-700 font-medium shrink-0">{fmt(r.value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Prorrateo resumen */}
                {(result.df_pror?.length ?? 0) > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                      <BarChart2 size={16} className="text-brand-orange" /> Prorrateo IVA Art. 490 ET
                    </h3>
                    <div className="overflow-x-auto">
                      <DataTable rows={result.df_pror.slice(0, 6)} />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Tablas ── */}
            {activeTab !== "Analítica" && (
              <div className="overflow-x-auto">
                <DataTable rows={currentData ?? []} />
              </div>
            )}
          </div>
        </div>
      )}

      <PageChatbot
        moduleName="Facturas DIAN"
        systemContext={`Eres TaxOps Asistente de Facturas DIAN, experto en facturación electrónica colombiana.
Puedes ayudar con:
- Interpretación de facturas electrónicas DIAN (CUFE, XML, PDF)
- IVA: bases gravadas al 19%, 5%, exentas y excluidas
- Retención en la fuente: tarifa 2.5% compras, topes mínimos ($524,000)
- Notas crédito y débito: manejo y registro
- Prorrateo de IVA (Art. 490 ET): cuando hay operaciones gravadas y excluidas
- Autorretenedores: quiénes son y cómo afectan la retención
- Validación de documentos: campos obligatorios DIAN, resolución de facturación
- Régimen simple de tributación vs régimen ordinario
- Exportación a Excel y cruces de información
Responde en español, de forma clara y concisa. Cita artículos del ET cuando sea relevante.`}
        currentData={result ? { total_archivos: result.total_archivos, procesados: result.procesados, errores: result.errores, registros: result.df_base?.length } : null}
      />
    </div>
  );
}

function Pill({ icon, label, color }: { icon: React.ReactNode; label: string; color: string }) {
  const colors: Record<string, string> = {
    emerald: "bg-emerald-50 text-emerald-700",
    red: "bg-red-50 text-red-700",
    blue: "bg-blue-50 text-blue-700",
    yellow: "bg-yellow-50 text-yellow-700",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${colors[color]}`}>
      {icon}
      {label}
    </span>
  );
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length)
    return <p className="p-6 text-sm text-gray-400 text-center">Sin datos</p>;

  const cols = Object.keys(rows[0]);

  return (
    <table className="text-xs w-full">
      <thead>
        <tr className="bg-gray-50 border-b border-gray-200">
          {cols.map((c) => (
            <th key={c} className="px-3 py-2 text-left text-gray-500 font-medium whitespace-nowrap">
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 200).map((row, i) => (
          <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
            {cols.map((c) => (
              <td key={c} className="px-3 py-1.5 text-gray-700 whitespace-nowrap">
                {String(row[c] ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
