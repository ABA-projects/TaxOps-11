"use client";

import { useEffect, useState } from "react";
import { Target } from "lucide-react";
import { useApi } from "@/lib/api";

type Lead = {
  id: string;
  empresa: string;
  sector: string | null;
  ciudad: string | null;
  contacto: string | null;
  fuente_url: string | null;
  fecha_generado: string;
};

export default function LeadsPage() {
  const { get } = useApi();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    get<Lead[]>("/admin/leads")
      .then(setLeads)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Error cargando leads"))
      .finally(() => setLoading(false));
  }, [get]);

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center gap-2">
        <Target size={20} className="text-brand-orange" />
        <h1 className="text-lg font-semibold text-gray-900">Leads comerciales</h1>
      </div>
      <p className="text-sm text-gray-400">
        Empresas prospectadas automáticamente que podrían necesitar servicios contables.
      </p>

      {loading && <p className="text-sm text-gray-400">Cargando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && leads.length === 0 && (
        <p className="text-sm text-gray-400">Todavía no hay leads publicados.</p>
      )}

      {leads.length > 0 && (
        <div className="card p-0 overflow-hidden overflow-x-auto">
          <table className="text-sm w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Empresa</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Sector</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Ciudad</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Contacto</th>
                <th className="px-3 py-2 text-left text-gray-500 font-medium">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2 text-gray-900">{l.empresa}</td>
                  <td className="px-3 py-2 text-gray-600">{l.sector ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-600">{l.ciudad ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-600">{l.contacto ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-400 text-xs">{l.fecha_generado}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
