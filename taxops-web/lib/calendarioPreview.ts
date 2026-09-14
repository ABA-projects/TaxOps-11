// Import estático: webpack lo empaqueta en build, así que también está disponible en ISR/runtime
// (un readFileSync a ../api fallaría en el bundle standalone de Amplify).
import calendario from "../../api/data/calendario_2026.json";

// Un evento tal como está en api/data/calendario_2026.json (fuente de verdad del calendario).
export type EventoDian = {
  id: string;
  fecha: string; // YYYY-MM-DD
  titulo: string;
  tipo: string;
  articulo?: string;
};

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** Los `n` primeros eventos con fecha >= `hoy` (YYYY-MM-DD), en orden cronológico. Función pura. */
export function proximosEventos(eventos: EventoDian[], hoy: string, n = 6): EventoDian[] {
  return eventos
    .filter((e) => e.fecha >= hoy)
    .sort((a, b) => a.fecha.localeCompare(b.fecha))
    .slice(0, n);
}

export function diaYMes(fecha: string): { dia: number; mes: string } {
  const [, m, d] = fecha.split("-").map(Number);
  return { dia: d, mes: MESES[m - 1] ?? "" };
}

/** El calendario del repo (api/data/calendario_2026.json es la fuente de verdad). */
export function leerCalendarioDelRepo(): EventoDian[] {
  return calendario as EventoDian[];
}
