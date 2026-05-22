"use client";

import { useState, useEffect, useCallback } from "react";
import {
  LayoutDashboard, Users, Building2, Activity, Shield,
  TrendingUp, Settings, Plus, Trash2, X, Check,
  FileText, ClipboardList, RefreshCw, UserX, UserCheck,
  Layers, AlertTriangle, Filter, Search,
} from "lucide-react";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// ── Types ─────────────────────────────────────────────────────────────────────
type User         = { id: string; email: string; full_name: string | null; role: string; active: boolean; created_at: string };
type AdminRequest = { id: string; email: string; full_name: string | null; role: string; admin_requested_at: string; created_at: string };
type Client       = { id: string; nit: string; razon_social: string; active: boolean; created_at?: string };
type Session      = { id: string; total_archivos: number; procesados: number; errores: number; nuevas: number; duplicadas: number; status: string; started_at: string; finished_at: string | null; user_email: string | null };
type Autorreten   = { id: number; nit: string; razon_social: string | null; vigente: boolean; updated_at: string };
type Ingreso      = { id: number; periodo: string; ingresos_gravados: number; ingresos_excluidos: number; updated_at: string };
type Org          = { id: string; slug: string; name: string; nit: string | null; plan: string; active: boolean; created_at: string };
type Stats        = {
  total_invoices: number; total_exogenas: number; total_users: number;
  total_clients: number; invoices_this_month: number; recent_sessions: Session[];
  invoices_by_month: { month: string; count: number; total_amount: number }[];
  top_providers: { name: string; count: number; total_amount: number }[];
  active_users_today: number; modules_usage: { module: string; actions: number }[];
  error_rate: number; total_nomina: number;
};
type Group        = { id: string; name: string; description: string | null; modules: string[]; created_at: string; members_count: number };
type Invite       = { id: string; email: string; role: string; invite_url: string; expires_at: string; created_at: string };
type AuditLog     = { id: string; user_email: string | null; action: string; module: string; resource_type: string | null; resource_id: string | null; details: Record<string,unknown> | null; created_at: string };

const ALL_MODULES = ["facturas", "nomina", "exogenas", "calendario", "chatbot", "admin"] as const;

// ── Tabs ──────────────────────────────────────────────────────────────────────
const TABS_ALL = [
  { key: "dashboard",        label: "Dashboard",         icon: <LayoutDashboard size={14} />, ownerOnly: false },
  { key: "usuarios",         label: "Usuarios",          icon: <Users size={14} />,           ownerOnly: false },
  { key: "grupos",           label: "Grupos",            icon: <Layers size={14} />,           ownerOnly: true  },
  { key: "solicitudes",      label: "Solicitudes Admin", icon: <Shield size={14} />,           ownerOnly: false },
  { key: "clientes",         label: "Clientes",          icon: <Building2 size={14} />,        ownerOnly: false },
  { key: "actividad",        label: "Actividad",         icon: <Activity size={14} />,         ownerOnly: false },
  { key: "autorretenedores", label: "Autorretenedores",  icon: <Shield size={14} />,           ownerOnly: false },
  { key: "ingresos",         label: "Ingresos",          icon: <TrendingUp size={14} />,       ownerOnly: false },
  { key: "organizacion",     label: "Organización",      icon: <Settings size={14} />,         ownerOnly: false },
] as const;
type TabKey = (typeof TABS_ALL)[number]["key"];

// ── Helpers ────────────────────────────────────────────────────────────────────
function Flash({ success, error }: { success: string; error: string }) {
  if (success) return <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700"><Check size={14} /> {success}</div>;
  if (error)   return <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"><X size={14} /> {error}</div>;
  return null;
}

function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = { done: "bg-emerald-50 text-emerald-700", running: "bg-blue-50 text-blue-700", failed: "bg-red-50 text-red-700" };
  return <span className={`badge ${cls[status] ?? "bg-gray-100 text-gray-600"}`}>{status}</span>;
}

function COP(v: number) { return v.toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }); }

function BarChart({ data, labelKey, valueKey, color = "bg-brand-orange" }: { data: Record<string,unknown>[]; labelKey: string; valueKey: string; color?: string }) {
  if (!data.length) return <p className="text-xs text-gray-400 py-4 text-center">Sin datos</p>;
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-3 text-xs">
          <span className="w-20 shrink-0 truncate text-gray-500" title={String(d[labelKey])}>{String(d[labelKey])}</span>
          <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
            <div className={`h-2 rounded-full ${color} transition-all`} style={{ width: `${(Number(d[valueKey]) / max) * 100}%` }} />
          </div>
          <span className="w-16 text-right font-medium text-gray-700 shrink-0">{Number(d[valueKey]).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

function ConfirmDialog({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onCancel}>
      <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-red-50 rounded-xl"><AlertTriangle size={20} className="text-red-500" /></div>
          <p className="font-semibold text-gray-900">Confirmar acción</p>
        </div>
        <p className="text-sm text-gray-600 mb-5">{message}</p>
        <div className="flex gap-3">
          <button onClick={onCancel} className="btn-secondary flex-1">Cancelar</button>
          <button onClick={onConfirm} className="flex-1 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-xl text-sm font-medium transition-colors">Eliminar</button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AdminPage() {
  const { get, post, patch, del } = useApi();
  const { user } = useAuth();
  const isOwner = user?.role === "owner";

  const TABS = TABS_ALL.filter((t) => !t.ownerOnly || isOwner);

  const [tab, setTab]         = useState<TabKey>("dashboard");
  const [success, setSuccess] = useState("");
  const [error, setError]     = useState("");
  const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);

  function flash(msg: string, type: "ok" | "err") {
    if (type === "ok") { setSuccess(msg); setError("");   setTimeout(() => setSuccess(""), 3500); }
    else               { setError(msg);   setSuccess(""); setTimeout(() => setError(""),   4500); }
  }

  function withConfirm(message: string, onConfirm: () => void) {
    setConfirm({ message, onConfirm });
  }

  // ── Dashboard ──────────────────────────────────────────────────────────────
  const [stats, setStats]         = useState<Stats | null>(null);
  const [statsLoading, setStatsL] = useState(false);
  const loadStats = useCallback(() => {
    setStatsL(true);
    get<Stats>("/admin/stats").then(setStats).catch(() => setStats(null)).finally(() => setStatsL(false));
  }, [get]);

  // ── Usuarios ───────────────────────────────────────────────────────────────
  const [users, setUsers]         = useState<User[]>([]);
  const [usersLoading, setUsersL] = useState(false);
  const [newUser, setNewUser]     = useState({ email: "", password: "", full_name: "", role: "contador" });
  const [userSearch, setUserSearch] = useState("");
  const loadUsers = useCallback(() => {
    setUsersL(true);
    get<User[]>("/admin/users")
      .then(setUsers)
      .catch(() => flash("Error al cargar usuarios", "err"))
      .finally(() => setUsersL(false));
  }, [get]);

  // ── Grupos ─────────────────────────────────────────────────────────────────
  const [groups, setGroups]             = useState<Group[]>([]);
  const [groupsLoading, setGroupsL]     = useState(false);
  const [newGroup, setNewGroup]         = useState({ name: "", description: "", modules: [] as string[] });
  const [editGroup, setEditGroup]       = useState<Group | null>(null);
  const [groupMembers, setGroupMembers] = useState<{ [gid: string]: User[] }>({});
  const loadGroups = useCallback(() => {
    setGroupsL(true);
    get<Group[]>("/admin/groups")
      .then((gs) => {
        setGroups(gs);
        // Auto-load members for all groups
        gs.forEach((g) => get<User[]>(`/admin/groups/${g.id}/members`)
          .then((m) => setGroupMembers((p) => ({ ...p, [g.id]: m }))).catch(() => {}));
      })
      .finally(() => setGroupsL(false));
  }, [get]);

  // ── Invitaciones ───────────────────────────────────────────────────────────
  const [invites, setInvites]           = useState<Invite[]>([]);
  const [inviteForm, setInviteForm]     = useState({ email: "", role: "contador" });
  const [inviteLink, setInviteLink]     = useState("");
  const [inviteLoading, setInviteL]     = useState(false);
  const loadInvites = useCallback(() => {
    get<Invite[]>("/admin/invitations").then(setInvites).catch(() => setInvites([]));
  }, [get]);

  // ── Clientes ───────────────────────────────────────────────────────────────
  const [clients, setClients]         = useState<Client[]>([]);
  const [clientsLoading, setClientsL] = useState(false);
  const [newClient, setNewClient]     = useState({ nit: "", razon_social: "" });
  const loadClients = useCallback(() => { setClientsL(true); get<Client[]>("/admin/clients").then(setClients).finally(() => setClientsL(false)); }, [get]);

  // ── Actividad ──────────────────────────────────────────────────────────────
  const [auditLogs, setAuditLogs]       = useState<AuditLog[]>([]);
  const [auditLoading, setAuditL]       = useState(false);
  const [auditFilter, setAuditFilter]   = useState({ module: "", action: "", user_email: "" });
  const loadAudit = useCallback(() => {
    setAuditL(true);
    const params = new URLSearchParams();
    if (auditFilter.module)     params.set("module",     auditFilter.module);
    if (auditFilter.action)     params.set("action",     auditFilter.action);
    if (auditFilter.user_email) params.set("user_email", auditFilter.user_email);
    params.set("limit", "200");
    get<AuditLog[]>(`/admin/audit-logs?${params.toString()}`)
      .then(setAuditLogs).catch(() => setAuditLogs([])).finally(() => setAuditL(false));
  }, [get, auditFilter]);

  // ── Autorretenedores ───────────────────────────────────────────────────────
  const [autos, setAutos]           = useState<Autorreten[]>([]);
  const [autosLoading, setAutosL]   = useState(false);
  const [newAuto, setNewAuto]       = useState({ nit: "", razon_social: "" });
  const [autoFilter, setAutoFilter] = useState("");
  const loadAutos = useCallback(() => { setAutosL(true); get<Autorreten[]>("/admin/autorretenedores").then(setAutos).finally(() => setAutosL(false)); }, [get]);

  // ── Ingresos ───────────────────────────────────────────────────────────────
  const [ingresos, setIngresos]         = useState<Ingreso[]>([]);
  const [ingresosLoading, setIngresosL] = useState(false);
  const [newIng, setNewIng]             = useState({ periodo: "", ingresos_gravados: "", ingresos_excluidos: "" });
  const loadIngresos = useCallback(() => { setIngresosL(true); get<Ingreso[]>("/admin/ingresos").then(setIngresos).finally(() => setIngresosL(false)); }, [get]);

  // ── Solicitudes Admin ─────────────────────────────────────────────────────
  const [requests, setRequests]     = useState<AdminRequest[]>([]);
  const [requestsLoading, setReqL]  = useState(false);
  const loadRequests = useCallback(() => {
    setReqL(true);
    get<AdminRequest[]>("/admin/users/admin-requests").then(setRequests).finally(() => setReqL(false));
  }, [get]);

  // ── Organización ───────────────────────────────────────────────────────────
  const [org, setOrg]           = useState<Org | null>(null);
  const [orgLoading, setOrgL]   = useState(false);
  const [orgForm, setOrgForm]   = useState({ name: "", nit: "" });
  const loadOrg = useCallback(() => {
    setOrgL(true);
    get<Org>("/admin/org")
      .then((o) => { setOrg(o); setOrgForm({ name: o.name, nit: o.nit ?? "" }); })
      .finally(() => setOrgL(false));
  }, [get]);

  useEffect(() => {
    if (tab === "dashboard")        loadStats();
    if (tab === "usuarios")         { loadUsers(); loadInvites(); }
    if (tab === "grupos")           { loadGroups(); loadUsers(); }
    if (tab === "solicitudes")      loadRequests();
    if (tab === "clientes")         loadClients();
    if (tab === "actividad")        loadAudit();
    if (tab === "autorretenedores") loadAutos();
    if (tab === "ingresos")         loadIngresos();
    if (tab === "organizacion")     loadOrg();
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Invite actions ────────────────────────────────────────────────────────
  async function sendInvite() {
    if (!inviteForm.email) { flash("Email requerido", "err"); return; }
    setInviteL(true);
    try {
      const inv = await post<Invite>("/admin/invitations", inviteForm);
      setInviteLink(inv.invite_url);
      setInvites((p) => [inv, ...p]);
      setInviteForm({ email: "", role: "contador" });
      flash("Invitación generada", "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error al generar invitación", "err"); }
    finally { setInviteL(false); }
  }

  async function revokeInvite(id: string) {
    try {
      await del(`/admin/invitations/${id}`);
      setInvites((p) => p.filter((i) => i.id !== id));
      flash("Invitación revocada", "ok");
    } catch { flash("Error al revocar", "err"); }
  }

  // ── User actions ───────────────────────────────────────────────────────────
  async function createUser() {
    if (!newUser.email || !newUser.password) { flash("Email y contraseña son requeridos", "err"); return; }
    try {
      const created = await post<User>("/admin/users", newUser);
      setUsers((p) => [created, ...p]);
      setNewUser({ email: "", password: "", full_name: "", role: "contador" });
      flash("Usuario creado", "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function deactivateUser(id: string) {
    try { await del(`/admin/users/${id}`); setUsers((p) => p.map((u) => u.id === id ? { ...u, active: false } : u)); flash("Usuario desactivado", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function reactivateUser(id: string) {
    try { await post(`/admin/users/${id}/reactivate`, {}); setUsers((p) => p.map((u) => u.id === id ? { ...u, active: true } : u)); flash("Usuario reactivado", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function changeUserRole(userId: string, newRole: string) {
    try {
      await patch(`/admin/users/${userId}/role`, { role: newRole });
      setUsers((p) => p.map((u) => u.id === userId ? { ...u, role: newRole } : u));
      flash(`Rol actualizado a ${newRole}`, "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error al cambiar rol", "err"); }
  }

  async function hardDeleteUser(u: User) {
    withConfirm(
      `¿Eliminar permanentemente a ${u.email}? Esta acción no se puede deshacer. Se anonimizará el email y se perderá el acceso.`,
      async () => {
        setConfirm(null);
        try {
          await del(`/admin/users/${u.id}/permanent`);
          setUsers((p) => p.filter((x) => x.id !== u.id));
          flash("Usuario eliminado permanentemente", "ok");
        } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
      }
    );
  }

  // ── Group actions ──────────────────────────────────────────────────────────
  async function createGroup() {
    if (!newGroup.name) { flash("Nombre del grupo requerido", "err"); return; }
    try {
      const g = await post<Group>("/admin/groups", newGroup);
      setGroups((p) => [g, ...p]);
      setNewGroup({ name: "", description: "", modules: [] });
      flash("Grupo creado", "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function saveGroup() {
    if (!editGroup) return;
    try {
      await patch(`/admin/groups/${editGroup.id}`, { name: editGroup.name, description: editGroup.description, modules: editGroup.modules });
      setGroups((p) => p.map((g) => g.id === editGroup.id ? { ...g, ...editGroup } : g));
      setEditGroup(null);
      flash("Grupo actualizado", "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function deleteGroup(id: string, name: string) {
    withConfirm(`¿Eliminar el grupo "${name}"? Los usuarios no serán eliminados.`, async () => {
      setConfirm(null);
      try {
        await del(`/admin/groups/${id}`);
        setGroups((p) => p.filter((g) => g.id !== id));
        flash("Grupo eliminado", "ok");
      } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
    });
  }

  async function loadGroupMembers(gid: string) {
    const members = await get<User[]>(`/admin/groups/${gid}/members`);
    setGroupMembers((p) => ({ ...p, [gid]: members }));
  }

  async function addToGroup(gid: string, uid: string) {
    try { await post(`/admin/groups/${gid}/members/${uid}`, {}); loadGroupMembers(gid); loadGroups(); flash("Usuario agregado al grupo", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function removeFromGroup(gid: string, uid: string) {
    try { await del(`/admin/groups/${gid}/members/${uid}`); loadGroupMembers(gid); loadGroups(); flash("Usuario removido del grupo", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  // ── Other actions ─────────────────────────────────────────────────────────
  async function createClient() {
    if (!newClient.nit || !newClient.razon_social) { flash("NIT y razón social requeridos", "err"); return; }
    try { const c = await post<Client>("/admin/clients", newClient); setClients((p) => [...p, c]); setNewClient({ nit: "", razon_social: "" }); flash("Cliente creado", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function addAutorretenedor() {
    if (!newAuto.nit) { flash("NIT requerido", "err"); return; }
    try { await post("/admin/autorretenedores", newAuto); setNewAuto({ nit: "", razon_social: "" }); loadAutos(); flash("NIT agregado", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function removeAutorretenedor(nit: string) {
    try { await del(`/admin/autorretenedores/${encodeURIComponent(nit)}`); setAutos((p) => p.map((a) => a.nit === nit ? { ...a, vigente: false } : a)); flash("NIT desactivado", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function saveIngreso() {
    if (!newIng.periodo) { flash("Periodo requerido (YYYY-MM)", "err"); return; }
    try {
      await post("/admin/ingresos", { periodo: newIng.periodo, ingresos_gravados: parseFloat(newIng.ingresos_gravados) || 0, ingresos_excluidos: parseFloat(newIng.ingresos_excluidos) || 0 });
      setNewIng({ periodo: "", ingresos_gravados: "", ingresos_excluidos: "" });
      loadIngresos();
      flash("Ingreso guardado", "ok");
    } catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function deleteIngreso(periodo: string) {
    try { await del(`/admin/ingresos/${encodeURIComponent(periodo)}`); setIngresos((p) => p.filter((i) => i.periodo !== periodo)); flash("Ingreso eliminado", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  async function saveOrg() {
    try { await patch("/admin/org", { name: orgForm.name || undefined, nit: orgForm.nit || null }); loadOrg(); flash("Organización actualizada", "ok"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Error", "err"); }
  }

  const filteredAutos = autoFilter
    ? autos.filter((a) => a.nit.includes(autoFilter) || (a.razon_social ?? "").toLowerCase().includes(autoFilter.toLowerCase()))
    : autos;

  const filteredUsers = userSearch
    ? users.filter((u) => u.email.toLowerCase().includes(userSearch.toLowerCase()) || (u.full_name ?? "").toLowerCase().includes(userSearch.toLowerCase()))
    : users;

  function toggleModule(modules: string[], mod: string) {
    return modules.includes(mod) ? modules.filter((m) => m !== mod) : [...modules, mod];
  }

  const ACTION_LABELS: Record<string, string> = {
    create_user: "Crear usuario", deactivate_user: "Desactivar usuario", hard_delete_user: "Eliminar usuario",
    reactivate_user: "Reactivar usuario", update_user: "Editar usuario", promote_to_admin: "Promover a admin",
    create_group: "Crear grupo", update_group: "Editar grupo", delete_group: "Eliminar grupo",
    add_to_group: "Agregar a grupo", remove_from_group: "Quitar de grupo",
    create_client: "Crear cliente", update_org: "Editar org",
    add_autorretenedor: "Agregar autorretenedor", remove_autorretenedor: "Desactivar autorretenedor",
    process_invoices: "Procesar facturas", process_nomina: "Calcular nómina",
    process_exogenas: "Procesar exógenas",
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6 max-w-6xl">
      {confirm && (
        <ConfirmDialog
          message={confirm.message}
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}

      <div>
        <h2 className="text-2xl font-bold text-gray-900">Administración</h2>
        <p className="text-gray-500 mt-1 text-sm">Panel de control · {isOwner ? "Owner" : "Admin"}</p>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 bg-gray-100 rounded-xl p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <Flash success={success} error={error} />

      {/* ══ DASHBOARD ══════════════════════════════════════════════════════════ */}
      {tab === "dashboard" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Resumen general</h3>
            <button onClick={loadStats} className="text-gray-400 hover:text-gray-700 transition-colors" title="Actualizar"><RefreshCw size={15} /></button>
          </div>

          {/* KPI grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Facturas totales",   value: stats?.total_invoices,      sub: `${stats?.invoices_this_month ?? 0} este mes`, icon: <FileText size={20} className="text-brand-orange" /> },
              { label: "Registros exógenas", value: stats?.total_exogenas,      icon: <ClipboardList size={20} className="text-blue-500" /> },
              { label: "Usuarios activos",   value: stats?.total_users,         sub: `${stats?.active_users_today ?? 0} hoy`, icon: <Users size={20} className="text-emerald-500" /> },
              { label: "Clientes",           value: stats?.total_clients,       icon: <Building2 size={20} className="text-violet-500" /> },
              { label: "Nóminas calculadas", value: stats?.total_nomina,        icon: <TrendingUp size={20} className="text-amber-500" /> },
              { label: "Tasa de errores",    value: `${stats?.error_rate ?? 0}%`, icon: <AlertTriangle size={20} className="text-red-400" /> },
            ].map((card) => (
              <div key={card.label} className="card flex items-start gap-3">
                <div className="p-2 bg-gray-50 rounded-lg shrink-0">{card.icon}</div>
                <div>
                  <p className="text-xs text-gray-500">{card.label}</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {statsLoading ? <span className="animate-pulse text-gray-300">—</span> : (typeof card.value === "number" ? card.value.toLocaleString() : (card.value ?? "—"))}
                  </p>
                  {card.sub && <p className="text-xs text-gray-400 mt-0.5">{card.sub}</p>}
                </div>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <h4 className="text-sm font-semibold text-gray-700 mb-4">Facturas por mes (últimos 6 meses)</h4>
              {statsLoading ? <div className="animate-pulse h-20 bg-gray-100 rounded" /> : (
                <BarChart data={(stats?.invoices_by_month ?? []).map(r => ({ month: r.month, count: r.count }))} labelKey="month" valueKey="count" />
              )}
            </div>
            <div className="card">
              <h4 className="text-sm font-semibold text-gray-700 mb-4">Top proveedores (por facturas)</h4>
              {statsLoading ? <div className="animate-pulse h-20 bg-gray-100 rounded" /> : (
                <BarChart data={(stats?.top_providers ?? []).map(r => ({ name: (r.name ?? "").substring(0, 20), count: r.count }))} labelKey="name" valueKey="count" color="bg-blue-500" />
              )}
            </div>
            <div className="card">
              <h4 className="text-sm font-semibold text-gray-700 mb-4">Módulos más usados (30 días)</h4>
              {statsLoading ? <div className="animate-pulse h-20 bg-gray-100 rounded" /> : (
                <BarChart data={(stats?.modules_usage ?? [])} labelKey="module" valueKey="actions" color="bg-emerald-500" />
              )}
            </div>
            <div className="card p-0 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100"><h4 className="text-sm font-semibold text-gray-700">Sesiones recientes</h4></div>
              {statsLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
                <table className="w-full text-sm">
                  <thead><tr className="bg-gray-50 border-b border-gray-100">
                    {["Archivos","Nuevas","Errores","Estado","Fecha"].map((h) => <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {(stats?.recent_sessions ?? []).slice(0, 5).map((s) => (
                      <tr key={s.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-900">{s.total_archivos}</td>
                        <td className="px-4 py-2 text-emerald-600 font-medium">{s.nuevas}</td>
                        <td className="px-4 py-2 text-red-500">{s.errores}</td>
                        <td className="px-4 py-2"><StatusBadge status={s.status} /></td>
                        <td className="px-4 py-2 text-gray-400 text-xs">{new Date(s.started_at).toLocaleString("es-CO")}</td>
                      </tr>
                    ))}
                    {!stats?.recent_sessions?.length && <tr><td colSpan={5} className="px-4 py-4 text-center text-gray-400 text-sm">Sin sesiones aún</td></tr>}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══ USUARIOS ═══════════════════════════════════════════════════════════ */}
      {tab === "usuarios" && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-4">Nuevo usuario</h3>
            <div className="grid grid-cols-2 gap-3">
              <input className="input" placeholder="Email" type="email" value={newUser.email} onChange={(e) => setNewUser((p) => ({ ...p, email: e.target.value }))} />
              <input className="input" placeholder="Contraseña temporal" type="password" value={newUser.password} onChange={(e) => setNewUser((p) => ({ ...p, password: e.target.value }))} />
              <input className="input" placeholder="Nombre completo (opcional)" value={newUser.full_name} onChange={(e) => setNewUser((p) => ({ ...p, full_name: e.target.value }))} />
              <select className="input" value={newUser.role} onChange={(e) => setNewUser((p) => ({ ...p, role: e.target.value }))}>
                <option value="auxiliar_contable">Auxiliar Contable</option>
                <option value="contador">Contador</option>
                {isOwner && <option value="admin">Admin</option>}
                {isOwner && <option value="owner">Owner</option>}
              </select>
            </div>
            <button onClick={createUser} className="btn-primary mt-3 flex items-center gap-2"><Plus size={14} /> Crear usuario</button>
          </div>

          <div className="card p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-3">
              <h3 className="font-semibold text-gray-900 shrink-0">Usuarios ({filteredUsers.length})</h3>
              <div className="relative flex-1 max-w-xs">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input className="input pl-8 text-sm" placeholder="Buscar..." value={userSearch} onChange={(e) => setUserSearch(e.target.value)} />
              </div>
              <button onClick={loadUsers} className="text-gray-400 hover:text-gray-700 shrink-0"><RefreshCw size={14} /></button>
            </div>
            {usersLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
              <table className="w-full text-sm">
                <thead><tr className="bg-gray-50 border-b border-gray-100">
                  {["Email","Nombre","Rol","Estado","Creado","Acciones"].map((h) => <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>)}
                </tr></thead>
                <tbody>
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className={`border-b border-gray-100 hover:bg-gray-50 ${!u.active ? "opacity-60" : ""}`}>
                      <td className="px-4 py-3 text-gray-900 text-xs">{u.email}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{u.full_name ?? "—"}</td>
                      <td className="px-4 py-3">
                        {(u.id === user?.user_id) || (u.role === "owner" && !isOwner) ? (
                          <span className={`badge ${
                            u.role === "owner" ? "bg-violet-50 text-violet-700" :
                            u.role === "admin" ? "bg-blue-50 text-blue-700" :
                            u.role === "contador" ? "bg-teal-50 text-teal-700" :
                            "bg-gray-100 text-gray-600"
                          }`}>{u.role === "auxiliar_contable" ? "Auxiliar" : u.role}</span>
                        ) : (
                          <select
                            className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-brand-orange"
                            value={u.role}
                            disabled={u.id === user?.user_id}
                            onChange={(e) => changeUserRole(u.id, e.target.value)}
                          >
                            <option value="auxiliar_contable">Auxiliar Contable</option>
                            <option value="contador">Contador</option>
                            {isOwner && <option value="admin">Admin</option>}
                            {isOwner && <option value="owner">Owner</option>}
                          </select>
                        )}
                      </td>
                      <td className="px-4 py-3"><span className={`badge ${u.active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{u.active ? "Activo" : "Inactivo"}</span></td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{new Date(u.created_at).toLocaleDateString("es-CO")}</td>
                      <td className="px-4 py-3">
                        {u.id !== user?.user_id && u.role !== "owner" && (
                          <div className="flex items-center gap-2">
                            {u.active ? (
                              <button onClick={() => deactivateUser(u.id)} title="Desactivar" className="text-gray-400 hover:text-orange-500 transition-colors">
                                <UserX size={14} />
                              </button>
                            ) : (
                              <button onClick={() => reactivateUser(u.id)} title="Reactivar" className="text-gray-400 hover:text-emerald-500 transition-colors">
                                <UserCheck size={14} />
                              </button>
                            )}
                            {isOwner && (
                              <button onClick={() => hardDeleteUser(u)} title="Eliminar permanentemente" className="text-gray-400 hover:text-red-600 transition-colors">
                                <Trash2 size={14} />
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filteredUsers.length === 0 && <tr><td colSpan={6} className="px-6 py-4 text-center text-gray-400 text-sm">Sin usuarios</td></tr>}
                </tbody>
              </table>
            )}
          </div>

          {/* Invitar por enlace */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-1">Invitar por enlace</h3>
            <p className="text-xs text-gray-500 mb-4">Genera un enlace de invitación (válido 7 días) y envíalo por email o WhatsApp.</p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <input
                className="input"
                type="email"
                placeholder="correo@empresa.com"
                value={inviteForm.email}
                onChange={(e) => setInviteForm((p) => ({ ...p, email: e.target.value }))}
              />
              <select className="input" value={inviteForm.role} onChange={(e) => setInviteForm((p) => ({ ...p, role: e.target.value }))}>
                <option value="auxiliar_contable">Auxiliar Contable</option>
                <option value="contador">Contador</option>
                {isOwner && <option value="admin">Admin</option>}
              </select>
            </div>
            <button onClick={sendInvite} disabled={inviteLoading} className="btn-primary flex items-center gap-2">
              <Plus size={14} /> {inviteLoading ? "Generando..." : "Generar enlace"}
            </button>

            {/* Enlace generado */}
            {inviteLink && (
              <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
                <p className="text-xs font-medium text-emerald-700 mb-2">Enlace listo — cópialo y envíalo:</p>
                <div className="flex items-center gap-2">
                  <input readOnly className="input text-xs flex-1 bg-white" value={inviteLink} />
                  <button
                    onClick={() => { navigator.clipboard.writeText(inviteLink); flash("Enlace copiado", "ok"); }}
                    className="btn-secondary text-xs shrink-0"
                  >Copiar</button>
                </div>
              </div>
            )}

            {/* Invitaciones pendientes */}
            {invites.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-gray-600 mb-2">Invitaciones pendientes ({invites.length})</p>
                <div className="space-y-1">
                  {invites.map((inv) => (
                    <div key={inv.id} className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded-lg text-xs">
                      <div>
                        <span className="font-medium text-gray-800">{inv.email}</span>
                        <span className={`ml-2 px-1.5 py-0.5 rounded-full ${inv.role === "admin" ? "bg-blue-50 text-blue-600" : "bg-gray-100 text-gray-500"}`}>{inv.role}</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-400">
                        <span>Expira {new Date(inv.expires_at).toLocaleDateString("es-CO")}</span>
                        <button
                          onClick={() => { navigator.clipboard.writeText(inv.invite_url); flash("Enlace copiado", "ok"); }}
                          title="Copiar enlace"
                          className="hover:text-brand-orange"
                        ><RefreshCw size={11} /></button>
                        <button onClick={() => revokeInvite(inv.id)} title="Revocar" className="hover:text-red-500"><X size={11} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ GRUPOS ═════════════════════════════════════════════════════════════ */}
      {tab === "grupos" && isOwner && (
        <div className="space-y-4">
          {/* Crear grupo */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-4">Nuevo grupo</h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <input className="input" placeholder="Nombre del grupo" value={newGroup.name} onChange={(e) => setNewGroup((p) => ({ ...p, name: e.target.value }))} />
              <input className="input" placeholder="Descripción (opcional)" value={newGroup.description} onChange={(e) => setNewGroup((p) => ({ ...p, description: e.target.value }))} />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-2">Módulos del grupo:</p>
              <div className="flex flex-wrap gap-2">
                {ALL_MODULES.map((mod) => (
                  <button
                    key={mod}
                    type="button"
                    onClick={() => setNewGroup((p) => ({ ...p, modules: toggleModule(p.modules, mod) }))}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                      newGroup.modules.includes(mod)
                        ? "bg-brand-orange text-white border-brand-orange"
                        : "bg-white text-gray-500 border-gray-300 hover:border-brand-orange"
                    }`}
                  >
                    {mod}
                  </button>
                ))}
              </div>
            </div>
            <button onClick={createGroup} className="btn-primary mt-3 flex items-center gap-2"><Plus size={14} /> Crear grupo</button>
          </div>

          {/* Lista grupos */}
          {groupsLoading ? <div className="text-sm text-gray-400">Cargando...</div> : (
            <div className="space-y-3">
              {groups.map((g) => (
                <div key={g.id} className="card">
                  {editGroup?.id === g.id ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <input className="input" value={editGroup.name} onChange={(e) => setEditGroup({ ...editGroup, name: e.target.value })} />
                        <input className="input" value={editGroup.description ?? ""} onChange={(e) => setEditGroup({ ...editGroup, description: e.target.value })} />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {ALL_MODULES.map((mod) => (
                          <button key={mod} type="button"
                            onClick={() => setEditGroup({ ...editGroup, modules: toggleModule(editGroup.modules, mod) })}
                            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                              editGroup.modules.includes(mod) ? "bg-brand-orange text-white border-brand-orange" : "bg-white text-gray-500 border-gray-300"
                            }`}
                          >{mod}</button>
                        ))}
                      </div>
                      <div className="flex gap-2">
                        <button onClick={saveGroup} className="btn-primary flex items-center gap-1"><Check size={13} /> Guardar</button>
                        <button onClick={() => setEditGroup(null)} className="btn-secondary">Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-semibold text-gray-900">{g.name}</h4>
                          {g.description && <p className="text-xs text-gray-500 mt-0.5">{g.description}</p>}
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {g.modules.map((m) => (
                              <span key={m} className="px-2 py-0.5 bg-brand-orange/10 text-brand-orange rounded-full text-xs">{m}</span>
                            ))}
                            {g.modules.length === 0 && <span className="text-xs text-gray-400">Sin módulos asignados</span>}
                          </div>
                          <p className="text-xs text-gray-400 mt-2">{g.members_count} miembro{g.members_count !== 1 ? "s" : ""}</p>
                        </div>
                        <div className="flex gap-2">
                          <button onClick={() => { setEditGroup(g); loadGroupMembers(g.id); }} className="btn-secondary text-xs py-1">Editar</button>
                          <button onClick={() => deleteGroup(g.id, g.name)} className="text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={14} /></button>
                        </div>
                      </div>

                      {/* Miembros del grupo — siempre visible */}
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-xs font-medium text-gray-600">
                            Miembros ({(groupMembers[g.id] ?? []).length})
                          </p>
                          <button onClick={() => loadGroupMembers(g.id)} className="text-gray-400 hover:text-gray-600" title="Recargar">
                            <RefreshCw size={11} />
                          </button>
                        </div>
                        <div className="space-y-1">
                          {(groupMembers[g.id] ?? []).length === 0 && (
                            <p className="text-xs text-gray-400 py-1">Sin miembros aún</p>
                          )}
                          {(groupMembers[g.id] ?? []).map((m) => (
                            <div key={m.id} className="flex items-center justify-between py-1 px-2 bg-gray-50 rounded-lg text-xs">
                              <div>
                                <span className="font-medium text-gray-700">{m.email}</span>
                                <span className={`ml-1.5 px-1.5 py-0.5 rounded-full ${m.role === "admin" ? "bg-blue-50 text-blue-600" : m.role === "owner" ? "bg-violet-50 text-violet-600" : "bg-gray-100 text-gray-500"}`}>{m.role}</span>
                              </div>
                              <button onClick={() => removeFromGroup(g.id, m.id)} title="Quitar del grupo" className="text-gray-400 hover:text-red-500"><X size={12} /></button>
                            </div>
                          ))}
                          {/* Agregar usuario */}
                          <select
                            className="input text-xs mt-2"
                            onChange={(e) => { if (e.target.value) { addToGroup(g.id, e.target.value); e.target.value = ""; } }}
                            defaultValue=""
                          >
                            <option value="">+ Agregar usuario...</option>
                            {users.filter((u) => !(groupMembers[g.id] ?? []).find((m) => m.id === u.id)).map((u) => (
                              <option key={u.id} value={u.id}>{u.email} — {u.role}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {groups.length === 0 && <div className="card text-center text-sm text-gray-400 py-8">Sin grupos. Crea uno para organizar usuarios por módulo.</div>}
            </div>
          )}
        </div>
      )}

      {/* ══ SOLICITUDES ════════════════════════════════════════════════════════ */}
      {tab === "solicitudes" && (
        <div className="card p-0 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Solicitudes de cambio de perfil ({requests.length})</h3>
            <button onClick={loadRequests} className="text-gray-400 hover:text-gray-700"><RefreshCw size={14} /></button>
          </div>
          {requestsLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : requests.length === 0 ? (
            <div className="p-6 text-sm text-gray-400">No hay solicitudes pendientes.</div>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 border-b border-gray-100">
                {["Email","Nombre","Rol actual","Solicitado","Asignar rol"].map((h) => <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>)}
              </tr></thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-6 py-3 text-gray-900">{r.email}</td>
                    <td className="px-6 py-3 text-gray-500">{r.full_name ?? "—"}</td>
                    <td className="px-6 py-3"><span className="badge bg-gray-100 text-gray-600">{r.role}</span></td>
                    <td className="px-6 py-3 text-gray-400 text-xs">{new Date(r.admin_requested_at).toLocaleString("es-CO")}</td>
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-2">
                        <select
                          id={`role-select-${r.id}`}
                          defaultValue="contador"
                          className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white focus:outline-none"
                        >
                          <option value="auxiliar_contable">Auxiliar Contable</option>
                          <option value="contador">Contador</option>
                          {isOwner && <option value="admin">Admin</option>}
                        </select>
                        <button
                          onClick={async () => {
                            const sel = document.getElementById(`role-select-${r.id}`) as HTMLSelectElement;
                            try {
                              await patch(`/admin/users/${r.id}/role`, { role: sel.value });
                              flash(`${r.email} → ${sel.value}`, "ok");
                              loadRequests();
                              setUsers((p) => p.map((u) => u.id === r.id ? { ...u, role: sel.value } : u));
                            } catch { flash("Error al cambiar rol", "err"); }
                          }}
                          className="flex items-center gap-1 bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1 rounded-lg text-xs font-medium transition-colors"
                        >
                          <Check size={12} /> Aprobar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ══ CLIENTES ═══════════════════════════════════════════════════════════ */}
      {tab === "clientes" && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-4">Nuevo cliente</h3>
            <div className="grid grid-cols-2 gap-3">
              <input className="input" placeholder="NIT (sin dígito de verificación)" value={newClient.nit} onChange={(e) => setNewClient((p) => ({ ...p, nit: e.target.value }))} />
              <input className="input" placeholder="Razón social" value={newClient.razon_social} onChange={(e) => setNewClient((p) => ({ ...p, razon_social: e.target.value }))} />
            </div>
            <button onClick={createClient} className="btn-primary mt-3 flex items-center gap-2"><Plus size={14} /> Agregar cliente</button>
          </div>
          <div className="card p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Clientes ({clients.length})</h3>
              <button onClick={loadClients} className="text-gray-400 hover:text-gray-700"><RefreshCw size={14} /></button>
            </div>
            {clientsLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
              <table className="w-full text-sm">
                <thead><tr className="bg-gray-50 border-b border-gray-100">
                  {["NIT","Razón Social","Estado","Creado"].map((h) => <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>)}
                </tr></thead>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-6 py-3 font-mono text-gray-700">{c.nit}</td>
                      <td className="px-6 py-3 text-gray-900">{c.razon_social}</td>
                      <td className="px-6 py-3"><span className={`badge ${c.active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{c.active ? "Activo" : "Inactivo"}</span></td>
                      <td className="px-6 py-3 text-gray-400 text-xs">{c.created_at ? new Date(c.created_at).toLocaleDateString("es-CO") : "—"}</td>
                    </tr>
                  ))}
                  {clients.length === 0 && <tr><td colSpan={4} className="px-6 py-4 text-center text-gray-400 text-sm">Sin clientes aún</td></tr>}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ══ ACTIVIDAD ══════════════════════════════════════════════════════════ */}
      {tab === "actividad" && (
        <div className="space-y-4">
          {/* Filtros */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <Filter size={14} className="text-gray-400" />
              <span className="text-sm font-medium text-gray-700">Filtros</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Módulo</label>
                <select className="input text-sm" value={auditFilter.module} onChange={(e) => setAuditFilter((p) => ({ ...p, module: e.target.value }))}>
                  <option value="">Todos</option>
                  {ALL_MODULES.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Tipo de acción</label>
                <input className="input text-sm" placeholder="ej. create, delete..." value={auditFilter.action} onChange={(e) => setAuditFilter((p) => ({ ...p, action: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Usuario</label>
                <input className="input text-sm" placeholder="Email..." value={auditFilter.user_email} onChange={(e) => setAuditFilter((p) => ({ ...p, user_email: e.target.value }))} />
              </div>
            </div>
            <button onClick={loadAudit} className="btn-primary mt-3 flex items-center gap-2 text-sm"><Search size={14} /> Buscar</button>
          </div>

          {/* Audit log table */}
          <div className="card p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">Registro de actividad</h3>
                <p className="text-xs text-gray-500 mt-0.5">{auditLogs.length} eventos</p>
              </div>
              <button onClick={loadAudit} className="text-gray-400 hover:text-gray-700"><RefreshCw size={14} /></button>
            </div>
            {auditLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
              <div className="overflow-x-auto max-h-[32rem] overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-gray-50 z-10">
                    <tr className="border-b border-gray-100">
                      {["Fecha","Usuario","Módulo","Acción","Recurso","Detalle"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-400 whitespace-nowrap">{new Date(log.created_at).toLocaleString("es-CO")}</td>
                        <td className="px-4 py-2 text-gray-600 max-w-[140px] truncate">{log.user_email ?? "—"}</td>
                        <td className="px-4 py-2">
                          <span className={`badge text-xs ${
                            log.module === "admin" ? "bg-violet-50 text-violet-700" :
                            log.module === "facturas" ? "bg-orange-50 text-orange-700" :
                            log.module === "nomina" ? "bg-blue-50 text-blue-700" :
                            "bg-gray-100 text-gray-600"
                          }`}>{log.module}</span>
                        </td>
                        <td className="px-4 py-2 text-gray-700 whitespace-nowrap">{ACTION_LABELS[log.action] ?? log.action}</td>
                        <td className="px-4 py-2 text-gray-500">{log.resource_type ?? "—"} {log.resource_id ? `#${log.resource_id.substring(0,8)}` : ""}</td>
                        <td className="px-4 py-2 text-gray-400 max-w-[180px] truncate" title={JSON.stringify(log.details)}>
                          {log.details ? JSON.stringify(log.details).substring(0, 40) : "—"}
                        </td>
                      </tr>
                    ))}
                    {auditLogs.length === 0 && <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-400">Sin actividad registrada. Las acciones se registran automáticamente.</td></tr>}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ AUTORRETENEDORES ═══════════════════════════════════════════════════ */}
      {tab === "autorretenedores" && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-1">Agregar autorretenedor</h3>
            <p className="text-sm text-gray-500 mb-4">NITs marcados como autorretenedores al procesar facturas.</p>
            <div className="grid grid-cols-2 gap-3">
              <input className="input" placeholder="NIT (sin dígito de verificación)" value={newAuto.nit} onChange={(e) => setNewAuto((p) => ({ ...p, nit: e.target.value }))} />
              <input className="input" placeholder="Razón social (opcional)" value={newAuto.razon_social} onChange={(e) => setNewAuto((p) => ({ ...p, razon_social: e.target.value }))} />
            </div>
            <button onClick={addAutorretenedor} className="btn-primary mt-3 flex items-center gap-2"><Plus size={14} /> Agregar NIT</button>
          </div>
          <div className="card p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
              <h3 className="font-semibold text-gray-900 flex-1">Autorretenedores — {autos.filter((a) => a.vigente).length} vigentes / {autos.length} total</h3>
              <input className="input w-56 text-sm" placeholder="Buscar NIT o razón social..." value={autoFilter} onChange={(e) => setAutoFilter(e.target.value)} />
              <button onClick={loadAutos} className="text-gray-400 hover:text-gray-700 shrink-0"><RefreshCw size={14} /></button>
            </div>
            {autosLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
              <div className="max-h-[28rem] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50 z-10">
                    <tr className="border-b border-gray-100">
                      {["NIT","Razón Social","Estado","Actualizado",""].map((h) => <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAutos.map((a) => (
                      <tr key={a.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-6 py-2.5 font-mono text-gray-700">{a.nit}</td>
                        <td className="px-6 py-2.5 text-gray-500">{a.razon_social ?? "—"}</td>
                        <td className="px-6 py-2.5"><span className={`badge ${a.vigente ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-400"}`}>{a.vigente ? "Vigente" : "Inactivo"}</span></td>
                        <td className="px-6 py-2.5 text-gray-400 text-xs">{new Date(a.updated_at).toLocaleDateString("es-CO")}</td>
                        <td className="px-6 py-2.5 text-right">
                          {a.vigente && <button onClick={() => removeAutorretenedor(a.nit)} className="text-gray-400 hover:text-red-500 transition-colors" title="Desactivar"><Trash2 size={14} /></button>}
                        </td>
                      </tr>
                    ))}
                    {filteredAutos.length === 0 && <tr><td colSpan={5} className="px-6 py-4 text-center text-gray-400 text-sm">Sin resultados</td></tr>}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ INGRESOS PRORRATEO ═════════════════════════════════════════════════ */}
      {tab === "ingresos" && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-1">Registrar ingresos por periodo</h3>
            <p className="text-sm text-gray-500 mb-4">Usados para calcular el % de IVA deducible (Art. 490 E.T.).</p>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs text-gray-500 mb-1 block">Periodo</label><input className="input" placeholder="2026-03" value={newIng.periodo} onChange={(e) => setNewIng((p) => ({ ...p, periodo: e.target.value }))} /></div>
              <div><label className="text-xs text-gray-500 mb-1 block">Gravados $</label><input className="input" type="number" min="0" placeholder="0" value={newIng.ingresos_gravados} onChange={(e) => setNewIng((p) => ({ ...p, ingresos_gravados: e.target.value }))} /></div>
              <div><label className="text-xs text-gray-500 mb-1 block">Excluidos $</label><input className="input" type="number" min="0" placeholder="0" value={newIng.ingresos_excluidos} onChange={(e) => setNewIng((p) => ({ ...p, ingresos_excluidos: e.target.value }))} /></div>
            </div>
            <button onClick={saveIngreso} className="btn-primary mt-3 flex items-center gap-2"><Plus size={14} /> Guardar periodo</button>
          </div>
          <div className="card p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Ingresos ({ingresos.length} periodos)</h3>
              <button onClick={loadIngresos} className="text-gray-400 hover:text-gray-700"><RefreshCw size={14} /></button>
            </div>
            {ingresosLoading ? <div className="p-6 text-sm text-gray-400">Cargando...</div> : (
              <table className="w-full text-sm">
                <thead><tr className="bg-gray-50 border-b border-gray-100">
                  {["Periodo","Gravados","Excluidos","Total","% Deducible",""].map((h, i) => <th key={h} className={`px-6 py-3 text-xs font-medium text-gray-500 uppercase ${i > 0 ? "text-right" : "text-left"}`}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {ingresos.map((i) => {
                    const total = i.ingresos_gravados + i.ingresos_excluidos;
                    const pct   = total > 0 ? ((i.ingresos_gravados / total) * 100).toFixed(1) + "%" : "—";
                    return (
                      <tr key={i.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-6 py-3 font-mono font-medium text-gray-900">{i.periodo}</td>
                        <td className="px-6 py-3 text-right text-gray-700">{COP(i.ingresos_gravados)}</td>
                        <td className="px-6 py-3 text-right text-gray-700">{COP(i.ingresos_excluidos)}</td>
                        <td className="px-6 py-3 text-right text-gray-500">{COP(total)}</td>
                        <td className="px-6 py-3 text-right font-semibold text-emerald-600">{pct}</td>
                        <td className="px-6 py-3 text-right"><button onClick={() => deleteIngreso(i.periodo)} className="text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={14} /></button></td>
                      </tr>
                    );
                  })}
                  {ingresos.length === 0 && <tr><td colSpan={6} className="px-6 py-6 text-center text-gray-400 text-sm">Sin ingresos registrados</td></tr>}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ══ ORGANIZACIÓN ═══════════════════════════════════════════════════════ */}
      {tab === "organizacion" && (
        <div className="max-w-lg space-y-4">
          {orgLoading ? <div className="text-sm text-gray-400">Cargando...</div> : org && (
            <div className="card space-y-5">
              <h3 className="font-semibold text-gray-900">Información de la organización</h3>
              <div><label className="text-xs text-gray-500 mb-1 block">Nombre de la firma</label><input className="input" value={orgForm.name} onChange={(e) => setOrgForm((p) => ({ ...p, name: e.target.value }))} /></div>
              <div><label className="text-xs text-gray-500 mb-1 block">NIT de la organización</label><input className="input" placeholder="Ej. 900123456" value={orgForm.nit} onChange={(e) => setOrgForm((p) => ({ ...p, nit: e.target.value }))} /></div>
              <div className="grid grid-cols-2 gap-y-3 text-sm border-t border-gray-100 pt-4">
                <div className="text-gray-500">Slug</div><div className="font-mono text-gray-700">{org.slug}</div>
                <div className="text-gray-500">Plan</div><div><span className="badge bg-brand-orange/10 text-brand-orange capitalize">{org.plan}</span></div>
                <div className="text-gray-500">Estado</div><div><span className={`badge ${org.active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{org.active ? "Activo" : "Inactivo"}</span></div>
                <div className="text-gray-500">Creado</div><div className="text-gray-700">{new Date(org.created_at).toLocaleDateString("es-CO")}</div>
              </div>
              <button onClick={saveOrg} className="btn-primary flex items-center gap-2"><Check size={14} /> Guardar cambios</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
