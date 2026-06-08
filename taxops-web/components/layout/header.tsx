"use client";

import { usePathname } from "next/navigation";
import { Bell, Sun, Moon, Monitor, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/facturas": "Facturas DIAN",
  "/exogenas": "Exógenas · Formato 1003",
  "/chatbot": "Asistente Contable IA",
  "/admin": "Administración",
  "/perfil": "Mi Perfil",
  "/superadmin": "Consola de Plataforma",
  "/nomina": "Nómina",
  "/calendario": "Calendario DIAN 2026",
};

// DIAN 2026 upcoming deadlines (next 30 days from today)
type DianAlert = { id: string; label: string; date: string; dias: number };

function getDianAlerts(): DianAlert[] {
  const EVENTOS = [
    { id: "ica-ene", label: "ICA Bogotá bimestre ene-feb", date: "2026-03-20" },
    { id: "ret-ene", label: "Retención enero (GC)", date: "2026-02-09" },
    { id: "ret-feb", label: "Retención febrero (GC)", date: "2026-03-09" },
    { id: "ret-mar", label: "Retención marzo (GC)", date: "2026-04-08" },
    { id: "iva-b1", label: "IVA bimestre 1 (ene-feb)", date: "2026-03-09" },
    { id: "renta-2025", label: "Declaración Renta 2025 (GC)", date: "2026-04-14" },
    { id: "exog-2025", label: "Información Exógena 2025", date: "2026-04-30" },
    { id: "patri-2026", label: "Impuesto Patrimonio 2026", date: "2026-05-12" },
    { id: "ret-abr", label: "Retención abril (GC)", date: "2026-05-08" },
    { id: "iva-b2", label: "IVA bimestre 2 (mar-abr)", date: "2026-05-08" },
  ];

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const limit = new Date(today);
  limit.setDate(limit.getDate() + 30);

  return EVENTOS.flatMap((e) => {
    const d = new Date(e.date + "T00:00:00");
    if (d >= today && d <= limit) {
      const dias = Math.ceil((d.getTime() - today.getTime()) / 86400000);
      return [{ ...e, dias }];
    }
    return [];
  }).sort((a, b) => a.dias - b.dias);
}

type ThemeMode = "light" | "dark" | "auto";

function applyTheme(mode: ThemeMode) {
  const html = document.documentElement;
  if (mode === "dark") {
    html.classList.add("dark");
    localStorage.setItem("taxops_theme", "dark");
  } else if (mode === "light") {
    html.classList.remove("dark");
    localStorage.setItem("taxops_theme", "light");
  } else {
    localStorage.removeItem("taxops_theme");
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      html.classList.add("dark");
    } else {
      html.classList.remove("dark");
    }
  }
}

function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>("auto");

  useEffect(() => {
    const saved = localStorage.getItem("taxops_theme");
    if (saved === "dark") setMode("dark");
    else if (saved === "light") setMode("light");
    else setMode("auto");
  }, []);

  function cycle() {
    const next: ThemeMode = mode === "light" ? "dark" : mode === "dark" ? "auto" : "light";
    setMode(next);
    applyTheme(next);
  }

  const ICONS: Record<ThemeMode, React.ReactNode> = {
    light: <Sun size={18} />,
    dark:  <Moon size={18} />,
    auto:  <Monitor size={18} />,
  };
  const LABELS: Record<ThemeMode, string> = {
    light: "Modo claro — click para oscuro",
    dark:  "Modo oscuro — click para automático",
    auto:  "Automático (sistema) — click para claro",
  };

  return (
    <button
      onClick={cycle}
      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-slate-700 dark:hover:text-gray-200 rounded-lg transition-colors"
      title={LABELS[mode]}
      aria-label={LABELS[mode]}
    >
      {ICONS[mode]}
    </button>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("taxops_notif_dismissed");
      if (saved) setDismissed(JSON.parse(saved));
    } catch {}
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const alerts = getDianAlerts().filter((a) => !dismissed.includes(a.id));

  function dismiss(id: string) {
    const next = [...dismissed, id];
    setDismissed(next);
    localStorage.setItem("taxops_notif_dismissed", JSON.stringify(next));
  }

  function dismissAll() {
    const allIds = getDianAlerts().map((a) => a.id);
    const next = Array.from(new Set([...dismissed, ...allIds]));
    setDismissed(next);
    localStorage.setItem("taxops_notif_dismissed", JSON.stringify(next));
    setOpen(false);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-slate-700 dark:hover:text-gray-200 rounded-lg transition-colors"
        aria-label={`Notificaciones${alerts.length ? ` (${alerts.length})` : ""}`}
      >
        <Bell size={18} />
        {alerts.length > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 bg-[#E05519] text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
            {alerts.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-50 w-80 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-slate-700">
            <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">
              Vencimientos DIAN · próximos 30 días
            </span>
            {alerts.length > 0 && (
              <button onClick={dismissAll} className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                Limpiar todo
              </button>
            )}
          </div>

          {alerts.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-gray-400 dark:text-gray-500">
              Sin vencimientos en los próximos 30 días
            </div>
          ) : (
            <ul className="max-h-72 overflow-y-auto divide-y divide-gray-50 dark:divide-slate-700">
              {alerts.map((a) => (
                <li key={a.id} className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-slate-700/50">
                  <span
                    className={`mt-0.5 shrink-0 w-10 text-center text-xs font-bold px-1 py-0.5 rounded ${
                      a.dias <= 3
                        ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
                        : a.dias <= 10
                        ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400"
                        : "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400"
                    }`}
                  >
                    {a.dias}d
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-800 dark:text-gray-100 leading-tight">{a.label}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{a.date}</p>
                  </div>
                  <button
                    onClick={() => dismiss(a.id)}
                    className="shrink-0 text-gray-300 hover:text-gray-500 dark:hover:text-gray-400"
                    aria-label="Descartar"
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="px-4 py-2 border-t border-gray-100 dark:border-slate-700 text-right">
            <Link href="/calendario" onClick={() => setOpen(false)} className="text-xs text-[#E05519] hover:underline font-medium">
              Ver calendario completo →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const pathname = usePathname();

  const title =
    PAGE_TITLES[pathname] ??
    Object.entries(PAGE_TITLES).find(([key]) => pathname.startsWith(key))?.[1] ??
    "TaxOps";

  return (
    <header className="h-14 bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between px-6">
      <h1 className="text-base font-semibold text-gray-900 dark:text-gray-100">{title}</h1>

      <div className="flex items-center gap-2">
        <ThemeToggle />
        <NotificationBell />
      </div>
    </header>
  );
}
