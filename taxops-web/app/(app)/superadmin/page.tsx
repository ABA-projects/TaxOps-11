"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/api";
import { RefreshCw, Search, Building2, Users, Check, X, Shield } from "lucide-react";
import { useRouter } from "next/navigation";

type SAUser = {
  id: string; email: string; full_name: string | null; role: string;
  active: boolean; admin_requested_at: string | null;
  created_at: string; org_name: string; org_id: string;
};

type Org = { id: string; slug: string; name: string; plan: string; active: boolean; users_count: number; invoices_count: number };

const ALL_ROLES = ["auxiliar_contable", "contador", "admin", "owner"] as const;

const ROLE_COLORS: Record<string, string> = {
  owner:             "bg-violet-50 text-violet-700",
  admin:             "bg-blue-50 text-blue-700",
  contador:          "bg-teal-50 text-teal-700",
  auxiliar_contable: "bg-gray-100 text-gray-600",
};

function Flash({ ok, err }: { ok: string; err: string }) {
  if (ok)  return <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700"><Check size={14} />{ok}</div>;
  if (err) return <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"><X size={14} />{err}</div>;
  return null;
}

export default function SuperadminPage() {
  const { user } = useAuth();
  const { get, patch } = useApi();
  const router = useRouter();

  const [users, setUsers]     = useState<SAUser[]>([]);
  const [orgs, setOrgs]       = useState<Org[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch]   = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  const [tab, setTab]         = useState<"users" | "orgs">("users");
  const [ok, setOk]           = useState("");
  const [err, setErr]         = useState("");

  function flash(msg: string, type: "ok" | "err") {
    if (type === "ok") { setOk(msg); setErr(""); setTimeout(() => setOk(""), 3000); }
    else               { setErr(msg); setOk(""); setTimeout(() => setErr(""), 4000); }
  }

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([
      get<SAUser[]>("/admin/superadmin/users").then(setUsers).catch(() => {}),
      get<Org[]>("/admin/superadmin/orgs").then(setOrgs).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [get]);

  useEffect(() => {
    if (!user?.is_superadmin) { router.replace("/dashboard"); return; }
    loadData();
  }, [user, router, loadData]);

  async function changeRole(userId: string, newRole: string) {
    try {
      await patch(`/admin/superadmin/users/${userId}/role`, { role: newRole });
      setUsers((p) => p.map((u) => u.id === userId ? { ...u, role: newRole, admin_requested_at: null } : u));
      flash("Rol actualizado", "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  const filtered = users.filter((u) => {
    const matchSearch = !search || u.email.toLowerCase().includes(search.toLowerCase()) || (u.full_name ?? "").toLowerCase().includes(search.toLowerCase());
    const matchOrg = !orgFilter || u.org_id === orgFilter;
    return matchSearch && matchOrg;
  });

  const pendingRequests = users.filter((u) => u.admin_requested_at);

  if (!user?.is_superadmin) return null;

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2.5 bg-violet-50 rounded-xl"><Shield size={22} className="text-violet-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Superadmin</h1>
          <p className="text-sm text-gray-500">{users.length} usuarios · {orgs.length} organizaciones</p>
        </div>
        <button onClick={loadData} className="ml-auto text-gray-400 hover:text-gray-700"><RefreshCw size={16} /></button>
      </div>

      <Flash ok={ok} err={err} />

      {/* Solicitudes pendientes */}
      {pendingRequests.length > 0 && (
        <div className="card border border-amber-100 bg-amber-50/30">
          <h3 className="font-semibold text-amber-800 mb-3 text-sm">Solicitudes de cambio de perfil ({pendingRequests.length})</h3>
          <div className="space-y-2">
            {pendingRequests.map((u) => (
              <div key={u.id} className="flex items-center justify-between bg-white rounded-xl px-4 py-2.5 text-sm shadow-sm">
                <div>
                  <span className="font-medium text-gray-900">{u.email}</span>
                  <span className="text-gray-400 text-xs ml-2">— {u.org_name}</span>
                  <span className={`ml-2 badge ${ROLE_COLORS[u.role] ?? "bg-gray-100"}`}>{u.role}</span>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    id={`req-${u.id}`}
                    defaultValue="contador"
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1"
                  >
                    {ALL_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                  <button
                    onClick={() => {
                      const sel = document.getElementById(`req-${u.id}`) as HTMLSelectElement;
                      changeRole(u.id, sel.value);
                    }}
                    className="flex items-center gap-1 bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1 rounded-lg text-xs font-medium"
                  >
                    <Check size={11} /> Aprobar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {[{ key: "users", label: "Usuarios", icon: <Users size={14} /> }, { key: "orgs", label: "Organizaciones", icon: <Building2 size={14} /> }].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as "users" | "orgs")}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* ── USUARIOS ── */}
      {tab === "users" && (
        <div className="card p-0 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input className="input pl-8 text-sm" placeholder="Buscar usuario..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <select className="input text-sm max-w-xs" value={orgFilter} onChange={(e) => setOrgFilter(e.target.value)}>
              <option value="">Todas las organizaciones</option>
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
            <span className="text-sm text-gray-400 shrink-0">{filtered.length} usuarios</span>
          </div>

          {loading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 border-b border-gray-100">
                {["Email", "Nombre", "Organización", "Rol", "Estado", "Creado"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {filtered.map((u) => (
                  <tr key={u.id} className={`border-b border-gray-100 hover:bg-gray-50 ${!u.active ? "opacity-60" : ""}`}>
                    <td className="px-4 py-3 text-gray-900 text-xs">{u.email}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{u.full_name ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-600">{u.org_name}</td>
                    <td className="px-4 py-3">
                      <select
                        className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-brand-orange"
                        value={u.role}
                        onChange={(e) => changeRole(u.id, e.target.value)}
                      >
                        {ALL_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${u.active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                        {u.active ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{new Date(u.created_at).toLocaleDateString("es-CO")}</td>
                  </tr>
                ))}
                {filtered.length === 0 && <tr><td colSpan={6} className="px-6 py-4 text-center text-gray-400 text-sm">Sin usuarios</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── ORGANIZACIONES ── */}
      {tab === "orgs" && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-100">
              {["Nombre", "Slug", "Plan", "Usuarios", "Facturas", "Estado"].map((h) => (
                <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {orgs.map((o) => (
                <tr key={o.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium text-gray-900">{o.name}</td>
                  <td className="px-6 py-3 text-gray-400 font-mono text-xs">{o.slug}</td>
                  <td className="px-6 py-3"><span className="badge bg-gray-100 text-gray-600 capitalize">{o.plan}</span></td>
                  <td className="px-6 py-3 text-gray-700">{o.users_count}</td>
                  <td className="px-6 py-3 text-gray-700">{o.invoices_count}</td>
                  <td className="px-6 py-3"><span className={`badge ${o.active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{o.active ? "Activa" : "Inactiva"}</span></td>
                </tr>
              ))}
              {orgs.length === 0 && <tr><td colSpan={6} className="px-6 py-4 text-center text-gray-400 text-sm">Sin organizaciones</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
