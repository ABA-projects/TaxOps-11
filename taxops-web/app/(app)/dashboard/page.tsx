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

type MonthStat  = { month: string; count: number; total_amount: number };
type ProviderStat = { name: string; count: number; total_amount: number };
type ModuleStat = { module: string; actions: number };

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
    id: string;
    total_archivos: number;
    nuevas: number;
    errores: number;
    status: string;
    started_at: string;
  }>;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const COP = new Intl.NumberFormat("es-CO", {
  style: "currency", currency: "COP", maximumFractionDigits: 0,
});

function formatCOP(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000)     return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)         return `$${(v / 1_000).toFixed(0)}K`;
  return COP.format(v);
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1)   return "ahora";
  if (min < 60)  return `hace ${min}m`;
  const h = Math.floor(min / 60);
  if (h < 24)    return `hace ${h}h`;
  return `hace ${Math.floor(h / 24)}d`;
}

function trendVsPrev(current: number, prev: number): { pct: number; up: boolean; neutral: boolean } {
  if (!prev) return { pct: 0, up: true, neutral: true };
  const pct = Math.round(((current - prev) / prev) * 100);
  return { pct: Math.abs(pct), up: pct >= 0, neutral: pct === 0 };
}

// ── Tooltip personalizado ─────────────────────────────────────────────────────

function DarkTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number; name: string }[]; label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0f172a] border border-[#334155] rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-slate-200">
          {p.name === "count" ? "Facturas" : "Monto"}: <span className="font-bold text-orange-400">
            {p.name === "total_amount" ? formatCOP(p.value) : p.value.toLocaleString("es-CO")}
          </span>
        </p>
      ))}
    </div>
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({
  label, value, sub, icon, accentColor, trend,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: string;
  accentColor: string;
  trend?: { pct: number; up: boolean; neutral: boolean };
}) {
  return (
    <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-4">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">{label}</p>
          <p className="text-2xl font-extrabold text-slate-100">{value}</p>
          {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
        </div>
        <div className={`${accentColor} rounded-lg p-2 text-xl`}>{icon}</div>
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-2">
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
            trend.neutral ? "bg-slate-700 text-slate-400" :
            trend.up      ? "bg-emerald-900 text-emerald-400" :
                            "bg-red-900 text-red-400"
          }`}>
            {trend.neutral ? "→ sin cambio" : (trend.up ? "↑" : "↓") + ` ${trend.pct}%`}
          </span>
          <span className="text-[10px] text-slate-600">vs mes anterior</span>
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
      className={`bg-[#0f172a] border border-[#334155] border-t-2 ${BORDER_COLORS[color]} rounded-xl p-3 hover:border-[#475569] hover:-translate-y-0.5 transition-all block`}>
      <div className="text-2xl mb-2">{icon}</div>
      <p className="text-slate-200 text-[11px] font-semibold">{title}</p>
      <p className="text-slate-600 text-[10px] mt-0.5">{sub}</p>
    </Link>
  );
}

// ── Colores Pie ───────────────────────────────────────────────────────────────

const PIE_COLORS = ["#f97316", "#3b82f6", "#a855f7", "#22c55e", "#f59e0b", "#06b6d4"];

const MODULE_LABELS: Record<string, string> = {
  facturas: "Facturas", exogenas: "Exógenas", renta: "Renta",
  nomina: "Nómina", chatbot: "Chatbot", admin: "Admin",
};

// ── Dashboard Page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { get } = useApi();
  const { user } = useAuth();
  const [stats, setStats]       = useState<Stats | null>(null);
  const [loading, setLoading]   = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isAdmin = user?.role === "owner" || user?.role === "admin";

  const fetchStats = useCallback(() => {
    if (!isAdmin) { setLoading(false); return; }
    get<Stats>("/admin/stats")
      .then((data) => { setStats(data); setLastUpdate(new Date()); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isAdmin, get]);

  useEffect(() => {
    fetchStats();
    intervalRef.current = setInterval(fetchStats, 30_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchStats]);

  // Trend: comparar mes actual vs mes anterior usando invoices_by_month
  const months = stats?.invoices_by_month ?? [];
  const currentMonth = months[months.length - 1];
  const prevMonth    = months[months.length - 2];
  const trendInv  = trendVsPrev(currentMonth?.count ?? 0, prevMonth?.count ?? 0);
  const trendAmt  = trendVsPrev(currentMonth?.total_amount ?? 0, prevMonth?.total_amount ?? 0);
  const totalFact = months.reduce((s, m) => s + (m.total_amount ?? 0), 0);

  // Relabel months (YYYY-MM → mes abreviado)
  const MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const chartData = months.map((m) => {
    const [, mm] = m.month.split("-");
    return { ...m, label: MESES[parseInt(mm)] ?? m.month };
  });

  // Segundos desde última actualización
  const secsAgo = lastUpdate ? Math.round((Date.now() - lastUpdate.getTime()) / 1000) : null;

  const sessionDot = (status: string) =>
    status === "done" ? "bg-emerald-500" : status === "failed" ? "bg-red-500" : "bg-amber-500";

  return (
    <div className="min-h-screen bg-[#0f172a] -m-6 p-6">
      {/* ── Header ── */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100">
            Bienvenido{user?.email ? `, ${user.email.split("@")[0]}` : ""}
          </h2>
          <p className="text-slate-500 text-xs mt-0.5">Panel de control · TaxOps</p>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2 bg-[#1e293b] border border-[#334155] rounded-lg px-3 py-1.5">
            <span className={`w-2 h-2 rounded-full ${loading ? "bg-amber-400 animate-pulse" : "bg-emerald-500"}`} />
            <span className="text-slate-400 text-[10px]">
              {loading ? "Cargando…" : secsAgo !== null ? `Actualizado hace ${secsAgo}s` : "En vivo"}
            </span>
          </div>
        )}
      </div>

      {/* ── KPIs ── */}
      {isAdmin && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard
            label="Facturas totales"
            value={loading ? "…" : (stats?.total_invoices ?? 0).toLocaleString("es-CO")}
            sub={`${stats?.invoices_this_month ?? 0} este mes`}
            icon="📄" accentColor="bg-[#431407]"
            trend={loading ? undefined : trendInv}
          />
          <KpiCard
            label="Exógenas"
            value={loading ? "…" : (stats?.total_exogenas ?? 0).toLocaleString("es-CO")}
            sub="certificados"
            icon="📋" accentColor="bg-[#1e3a5f]"
            trend={loading ? undefined : { pct: 0, up: true, neutral: true }}
          />
          <KpiCard
            label="Facturado total"
            value={loading ? "…" : formatCOP(totalFact)}
            sub="COP acumulado"
            icon="💰" accentColor="bg-[#3b0764]"
            trend={loading ? undefined : trendAmt}
          />
          <KpiCard
            label="Tasa de error"
            value={loading ? "…" : `${stats?.error_rate ?? 0}%`}
            sub="sesiones fallidas"
            icon={!stats || stats.error_rate <= 10 ? "✅" : "⚠️"}
            accentColor={!stats || stats.error_rate <= 10 ? "bg-[#052e16]" : "bg-[#450a0a]"}
            trend={loading ? undefined : {
              pct: 0, up: !stats || stats.error_rate <= 10, neutral: false,
            }}
          />
        </div>
      )}

      {/* ── Charts ── */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {/* Area chart */}
          <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-4 lg:col-span-2">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-slate-200 text-sm font-semibold">Facturas por mes</h3>
              <div className="flex gap-2 text-[10px]">
                <span className="flex items-center gap-1 text-orange-400"><span className="w-2 h-0.5 bg-orange-400 inline-block" /> Conteo</span>
                <span className="flex items-center gap-1 text-blue-400"><span className="w-2 h-0.5 bg-blue-400 inline-block border-dashed border-t border-blue-400" /> Monto</span>
              </div>
            </div>
            {loading ? (
              <div className="h-40 bg-[#0f172a] rounded animate-pulse" />
            ) : chartData.length ? (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f97316" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gAmount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="label" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<DarkTooltip />} />
                  <Area type="monotone" dataKey="total_amount" stroke="#3b82f6" strokeWidth={1} strokeDasharray="4 2" fill="url(#gAmount)" />
                  <Area type="monotone" dataKey="count" stroke="#f97316" strokeWidth={2} fill="url(#gCount)" dot={{ fill: "#f97316", r: 3 }} activeDot={{ r: 5 }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-600 text-sm text-center py-10">Sin datos aún</p>
            )}
          </div>

          {/* Donut + top providers */}
          <div className="flex flex-col gap-4">
            {/* Donut módulos */}
            <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-4 flex-1">
              <h3 className="text-slate-200 text-sm font-semibold mb-3">Módulos activos</h3>
              {loading ? (
                <div className="h-20 bg-[#0f172a] rounded animate-pulse" />
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
                        <span className="text-[10px] text-slate-400 truncate max-w-[80px]">
                          {MODULE_LABELS[m.module] ?? m.module}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-slate-600 text-xs">Sin datos</p>
              )}
            </div>

            {/* Top providers */}
            <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-4 flex-1">
              <h3 className="text-slate-200 text-sm font-semibold mb-3">Top proveedores</h3>
              {loading ? (
                <div className="h-20 bg-[#0f172a] rounded animate-pulse" />
              ) : stats?.top_providers?.length ? (
                <ResponsiveContainer width="100%" height={80}>
                  <BarChart data={stats.top_providers} layout="vertical"
                    margin={{ top: 0, right: 5, left: -20, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" tick={{ fill: "#475569", fontSize: 9 }}
                      axisLine={false} tickLine={false} width={55} />
                    <Tooltip
                      cursor={{ fill: "#0f172a" }}
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: "#94a3b8" }}
                      itemStyle={{ color: "#f8fafc" }}
                    />
                    <Bar dataKey="count" fill="#f97316" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-slate-600 text-xs">Sin datos</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Activity + Quick actions ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Activity feed */}
        {isAdmin && (
          <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-4">
            <h3 className="text-slate-200 text-sm font-semibold mb-4">Actividad reciente</h3>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-8 bg-[#0f172a] rounded animate-pulse" />
                ))}
              </div>
            ) : stats?.recent_sessions?.length ? (
              <div className="space-y-3">
                {stats.recent_sessions.slice(0, 6).map((s) => (
                  <div key={s.id} className="flex items-start gap-3">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${sessionDot(s.status)}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-slate-300 text-[11px] leading-tight">
                        {s.total_archivos} archivos — {s.nuevas} nuevas
                        {s.errores > 0 && <span className="text-red-400"> · {s.errores} err</span>}
                      </p>
                      <p className="text-slate-600 text-[10px]">{timeAgo(s.started_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-600 text-xs">Sin sesiones recientes</p>
            )}
          </div>
        )}

        {/* Quick actions */}
        <div className={`${isAdmin ? "lg:col-span-2" : "lg:col-span-3"} bg-[#1e293b] border border-[#334155] rounded-xl p-4`}>
          <h3 className="text-slate-200 text-sm font-semibold mb-4">Acceso rápido</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <QuickAction href="/facturas"  icon="🧾" title="Facturas DIAN"     sub="PDF / XML · OCR"        color="orange"  />
            <QuickAction href="/exogenas"  icon="📋" title="Exógenas"          sub="Cert. retención 1003"   color="blue"    />
            <QuickAction href="/renta"     icon="📊" title="Renta Personas"    sub="Art. 241 ET"            color="violet"  />
            <QuickAction href="/nomina"    icon="💼" title="Nómina"            sub="Liquidación CST"        color="amber"   />
            <QuickAction href="/calendario" icon="📅" title="Calendario DIAN" sub="Fechas tributarias 2026" color="cyan"   />
            <QuickAction href="/chatbot"   icon="🤖" title="Chatbot IA"        sub="Normativa DIAN"         color="emerald" />
          </div>
        </div>
      </div>
    </div>
  );
}
