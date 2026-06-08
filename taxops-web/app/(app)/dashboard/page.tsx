"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// ── Types ─────────────────────────────────────────────────────────────────────

type MonthStat    = { month: string; count: number; total_amount: number };
type ProviderStat = { name: string; count: number; total_amount: number };
type ModuleStat   = { module: string; actions: number };

type Stats = {
  total_invoices: number;
  total_exogenas: number;
  total_users: number;
  total_clients: number;
  total_nomina: number;
  invoices_this_month: number;
  active_users_today: number;
  error_rate: number;
  invoices_by_month: MonthStat[];
  top_providers: ProviderStat[];
  modules_usage: ModuleStat[];
  recent_sessions: Array<{
    id: string; total_archivos: number; nuevas: number;
    errores: number; status: string; started_at: string;
  }>;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatCOP(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000)     return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)         return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toLocaleString("es-CO")}`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min  = Math.floor(diff / 60000);
  if (min < 1)  return "ahora";
  if (min < 60) return `hace ${min}m`;
  const h = Math.floor(min / 60);
  if (h < 24)   return `hace ${h}h`;
  return `hace ${Math.floor(h / 24)}d`;
}

function trend(current: number, prev: number) {
  if (!prev) return { pct: 0, up: true, neutral: true };
  const pct = Math.round(((current - prev) / prev) * 100);
  return { pct: Math.abs(pct), up: pct >= 0, neutral: pct === 0 };
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

function DarkTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number; name: string }[]; label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 dark:bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-slate-200">
          {p.name === "count" ? "Facturas" : "Monto"}:{" "}
          <span className="font-bold text-orange-400">
            {p.name === "total_amount" ? formatCOP(p.value) : p.value.toLocaleString("es-CO")}
          </span>
        </p>
      ))}
    </div>
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, icon, accentLight, accentDark, trendData }: {
  label: string; value: string; sub?: string; icon: string;
  accentLight: string; accentDark: string;
  trendData?: { pct: number; up: boolean; neutral: boolean };
}) {
  return (
    <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-gray-500 dark:text-slate-500 mb-1">{label}</p>
          <p className="text-2xl font-extrabold text-gray-900 dark:text-slate-100">{value}</p>
          {sub && <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-0.5">{sub}</p>}
        </div>
        <div className={`${accentLight} dark:${accentDark} rounded-lg p-2 text-xl`}>{icon}</div>
      </div>
      {trendData && (
        <div className="mt-3 flex items-center gap-2">
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
            trendData.neutral
              ? "bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400"
              : trendData.up
              ? "bg-emerald-50 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400"
              : "bg-red-50 dark:bg-red-900/40 text-red-700 dark:text-red-400"
          }`}>
            {trendData.neutral ? "→ sin cambio" : (trendData.up ? "↑" : "↓") + ` ${trendData.pct}%`}
          </span>
          <span className="text-[10px] text-gray-400 dark:text-slate-600">vs mes anterior</span>
        </div>
      )}
    </div>
  );
}

// ── Quick Action ──────────────────────────────────────────────────────────────

const BORDER_COLORS: Record<string, string> = {
  orange:  "border-t-orange-500",
  blue:    "border-t-blue-500",
  violet:  "border-t-violet-500",
  amber:   "border-t-amber-500",
  cyan:    "border-t-cyan-500",
  emerald: "border-t-emerald-500",
};

function QuickAction({ href, icon, title, sub, color }: {
  href: string; icon: string; title: string; sub: string;
  color: "orange" | "blue" | "violet" | "amber" | "cyan" | "emerald";
}) {
  return (
    <Link href={href}
      className={`bg-gray-50 dark:bg-slate-900 border border-gray-200 dark:border-slate-700 border-t-2 ${BORDER_COLORS[color]} rounded-xl p-3 hover:shadow-md hover:-translate-y-0.5 transition-all block`}>
      <div className="text-2xl mb-2">{icon}</div>
      <p className="text-gray-800 dark:text-slate-200 text-[11px] font-semibold">{title}</p>
      <p className="text-gray-500 dark:text-slate-600 text-[10px] mt-0.5">{sub}</p>
    </Link>
  );
}

// ── Constantes ────────────────────────────────────────────────────────────────

const PIE_COLORS = ["#f97316", "#3b82f6", "#a855f7", "#22c55e", "#f59e0b", "#06b6d4"];
const MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const MODULE_LABELS: Record<string, string> = {
  facturas: "Facturas", exogenas: "Exógenas", renta: "Renta",
  nomina: "Nómina", chatbot: "Chatbot", admin: "Admin",
};

// ── Dashboard Page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { get }  = useApi();
  const { user } = useAuth();
  const [stats, setStats]           = useState<Stats | null>(null);
  const [loading, setLoading]       = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isAdmin = user?.role === "owner" || user?.role === "admin";

  const fetchStats = useCallback(() => {
    if (!isAdmin) { setLoading(false); return; }
    get<Stats>("/admin/stats")
      .then((d) => { setStats(d); setLastUpdate(new Date()); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isAdmin, get]);

  useEffect(() => {
    fetchStats();
    intervalRef.current = setInterval(fetchStats, 30_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchStats]);

  const months      = stats?.invoices_by_month ?? [];
  const curMonth    = months[months.length - 1];
  const prevMonth   = months[months.length - 2];
  const trendInv    = trend(curMonth?.count ?? 0, prevMonth?.count ?? 0);
  const trendAmt    = trend(curMonth?.total_amount ?? 0, prevMonth?.total_amount ?? 0);
  const totalFact   = months.reduce((s, m) => s + (m.total_amount ?? 0), 0);
  const secsAgo     = lastUpdate ? Math.round((Date.now() - lastUpdate.getTime()) / 1000) : null;

  const chartData = months.map((m) => {
    const [, mm] = m.month.split("-");
    return { ...m, label: MESES[parseInt(mm)] ?? m.month };
  });

  const sessionDot = (s: string) =>
    s === "done" ? "bg-emerald-500" : s === "failed" ? "bg-red-500" : "bg-amber-500";

  const Skeleton = () => <div className="h-5 w-16 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />;

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100">
            Bienvenido{user?.email ? `, ${user.email.split("@")[0]}` : ""}
          </h2>
          <p className="text-gray-500 dark:text-slate-500 text-xs mt-0.5">Panel de control · TaxOps</p>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg px-3 py-1.5 shadow-sm">
            <span className={`w-2 h-2 rounded-full ${loading ? "bg-amber-400 animate-pulse" : "bg-emerald-500"}`} />
            <span className="text-gray-500 dark:text-slate-400 text-[10px]">
              {loading ? "Cargando…" : secsAgo !== null ? `Actualizado hace ${secsAgo}s` : "En vivo"}
            </span>
          </div>
        )}
      </div>

      {/* ── KPIs ── */}
      {isAdmin && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Facturas totales"
            value={loading ? "…" : (stats?.total_invoices ?? 0).toLocaleString("es-CO")}
            sub={`${stats?.invoices_this_month ?? 0} este mes`}
            icon="📄" accentLight="bg-orange-50" accentDark="bg-orange-950"
            trendData={loading ? undefined : trendInv}
          />
          <KpiCard
            label="Exógenas"
            value={loading ? "…" : (stats?.total_exogenas ?? 0).toLocaleString("es-CO")}
            sub="certificados"
            icon="📋" accentLight="bg-blue-50" accentDark="bg-blue-950"
          />
          <KpiCard
            label="Facturado total"
            value={loading ? "…" : formatCOP(totalFact)}
            sub="COP acumulado"
            icon="💰" accentLight="bg-violet-50" accentDark="bg-violet-950"
            trendData={loading ? undefined : trendAmt}
          />
          <KpiCard
            label="Tasa de error"
            value={loading ? "…" : `${stats?.error_rate ?? 0}%`}
            sub="sesiones fallidas"
            icon={!stats || stats.error_rate <= 10 ? "✅" : "⚠️"}
            accentLight={!stats || stats.error_rate <= 10 ? "bg-emerald-50" : "bg-red-50"}
            accentDark={!stats || stats.error_rate <= 10 ? "bg-emerald-950" : "bg-red-950"}
            trendData={loading ? undefined : { pct: 0, up: !stats || stats.error_rate <= 10, neutral: false }}
          />
        </div>
      )}

      {/* ── Charts ── */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Area chart */}
          <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-4 shadow-sm lg:col-span-2">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-gray-800 dark:text-slate-200 text-sm font-semibold">Facturas por mes</h3>
              <div className="flex gap-3 text-[10px]">
                <span className="flex items-center gap-1 text-orange-500"><span className="w-3 h-0.5 bg-orange-500 inline-block rounded" /> Conteo</span>
                <span className="flex items-center gap-1 text-blue-500"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> Monto</span>
              </div>
            </div>
            {loading ? (
              <div className="h-40 bg-gray-100 dark:bg-slate-700 rounded animate-pulse" />
            ) : chartData.length ? (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f97316" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gAmount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<DarkTooltip />} />
                  <Area type="monotone" dataKey="total_amount" stroke="#3b82f6" strokeWidth={1} strokeDasharray="4 2" fill="url(#gAmount)" />
                  <Area type="monotone" dataKey="count" stroke="#f97316" strokeWidth={2} fill="url(#gCount)" dot={{ fill: "#f97316", r: 3 }} activeDot={{ r: 5 }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-400 dark:text-slate-600 text-sm text-center py-10">Sin datos aún</p>
            )}
          </div>

          {/* Donut + Top providers */}
          <div className="flex flex-col gap-4">
            <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-4 shadow-sm flex-1">
              <h3 className="text-gray-800 dark:text-slate-200 text-sm font-semibold mb-3">Módulos activos</h3>
              {loading ? (
                <div className="h-20 bg-gray-100 dark:bg-slate-700 rounded animate-pulse" />
              ) : stats?.modules_usage?.length ? (
                <div className="flex items-center gap-3">
                  <ResponsiveContainer width={80} height={80}>
                    <PieChart>
                      <Pie data={stats.modules_usage} dataKey="actions" cx="50%" cy="50%"
                        innerRadius={22} outerRadius={36} paddingAngle={2} strokeWidth={0}>
                        {stats.modules_usage.map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-col gap-1">
                    {stats.modules_usage.slice(0, 4).map((m, i) => (
                      <div key={m.module} className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm flex-shrink-0"
                          style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                        <span className="text-[10px] text-gray-500 dark:text-slate-400 truncate max-w-[80px]">
                          {MODULE_LABELS[m.module] ?? m.module}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-xs">Sin datos</p>
              )}
            </div>

            <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-4 shadow-sm flex-1">
              <h3 className="text-gray-800 dark:text-slate-200 text-sm font-semibold mb-3">Top proveedores</h3>
              {loading ? (
                <div className="h-20 bg-gray-100 dark:bg-slate-700 rounded animate-pulse" />
              ) : stats?.top_providers?.length ? (
                <ResponsiveContainer width="100%" height={80}>
                  <BarChart data={stats.top_providers} layout="vertical"
                    margin={{ top: 0, right: 5, left: -20, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9 }}
                      axisLine={false} tickLine={false} width={55} />
                    <Tooltip
                      cursor={{ fill: "rgba(148,163,184,0.08)" }}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: "#94a3b8" }} itemStyle={{ color: "#f8fafc" }}
                    />
                    <Bar dataKey="count" fill="#f97316" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-400 text-xs">Sin datos</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Activity + Quick actions ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {isAdmin && (
          <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
            <h3 className="text-gray-800 dark:text-slate-200 text-sm font-semibold mb-4">Actividad reciente</h3>
            {loading ? (
              <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} />)}</div>
            ) : stats?.recent_sessions?.length ? (
              <div className="space-y-3">
                {stats.recent_sessions.slice(0, 6).map((s) => (
                  <div key={s.id} className="flex items-start gap-3">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${sessionDot(s.status)}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-700 dark:text-slate-300 text-[11px] leading-tight">
                        {s.total_archivos} archivos — {s.nuevas} nuevas
                        {s.errores > 0 && <span className="text-red-500"> · {s.errores} err</span>}
                      </p>
                      <p className="text-gray-400 dark:text-slate-600 text-[10px]">{timeAgo(s.started_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 dark:text-slate-600 text-xs">Sin sesiones recientes</p>
            )}
          </div>
        )}

        <div className={`${isAdmin ? "lg:col-span-2" : "lg:col-span-3"} bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-4 shadow-sm`}>
          <h3 className="text-gray-800 dark:text-slate-200 text-sm font-semibold mb-4">Acceso rápido</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <QuickAction href="/facturas"   icon="🧾" title="Facturas DIAN"     sub="PDF / XML · OCR"         color="orange"  />
            <QuickAction href="/exogenas"   icon="📋" title="Exógenas"          sub="Cert. retención 1003"    color="blue"    />
            <QuickAction href="/renta"      icon="📊" title="Renta Personas"    sub="Art. 241 ET"             color="violet"  />
            <QuickAction href="/nomina"     icon="💼" title="Nómina"            sub="Liquidación CST"         color="amber"   />
            <QuickAction href="/calendario" icon="📅" title="Calendario DIAN"   sub="Fechas tributarias 2026" color="cyan"    />
            <QuickAction href="/chatbot"    icon="🤖" title="Chatbot IA"        sub="Normativa DIAN"          color="emerald" />
          </div>
        </div>
      </div>
    </div>
  );
}
