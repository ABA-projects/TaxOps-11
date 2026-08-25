"use client";

import { useEffect, useState } from "react";
import { Newspaper } from "lucide-react";
import { useApi } from "@/lib/api";

type Novedad = {
  id: string;
  tipo: string;
  titulo: string;
  resumen: string;
  fecha_generado: string;
};

const TIPO_LABEL: Record<string, string> = { dian: "DIAN", niif: "NIIF" };
const TIPO_COLOR: Record<string, string> = {
  dian: "bg-blue-50 text-blue-700",
  niif: "bg-purple-50 text-purple-700",
};

export default function NovedadesPage() {
  const { get } = useApi();
  const [novedades, setNovedades] = useState<Novedad[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    get<Novedad[]>("/novedades")
      .then(setNovedades)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Error cargando novedades"))
      .finally(() => setLoading(false));
  }, [get]);

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-2">
        <Newspaper size={20} className="text-brand-orange" />
        <h1 className="text-lg font-semibold text-gray-900">Novedades tributarias y NIIF</h1>
      </div>
      <p className="text-sm text-gray-400">
        Resúmenes semanales generados automáticamente — DIAN (resoluciones, circulares, decretos) y NIIF.
      </p>

      {loading && <p className="text-sm text-gray-400">Cargando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && novedades.length === 0 && (
        <p className="text-sm text-gray-400">Todavía no hay novedades publicadas.</p>
      )}

      <div className="space-y-3">
        {novedades.map((n) => (
          <div key={n.id} className="card">
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TIPO_COLOR[n.tipo] ?? "bg-gray-50 text-gray-700"}`}>
                {TIPO_LABEL[n.tipo] ?? n.tipo.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400">{n.fecha_generado}</span>
            </div>
            <h2 className="font-medium text-gray-900 mb-1">{n.titulo}</h2>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{n.resumen}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
