"use client";

import { useEffect, useState, FormEvent } from "react";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/api";
import { User, Lock, Building2, Layers, Check, X, Shield } from "lucide-react";

type OrgInfo  = { id: string; slug: string; name: string; plan: string; nit: string | null };
type GroupInfo = { id: string; name: string; description: string | null; modules: string[] };

function Flash({ ok, err }: { ok: string; err: string }) {
  if (ok)  return <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700"><Check size={14} />{ok}</div>;
  if (err) return <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700"><X size={14} />{err}</div>;
  return null;
}

export default function PerfilPage() {
  const { user, setToken } = useAuth();
  const { get, patch } = useApi();

  const [org, setOrg]       = useState<OrgInfo | null>(null);
  const [groups, setGroups] = useState<GroupInfo[]>([]);

  const [nameForm, setNameForm] = useState({ full_name: "" });
  const [pwForm, setPwForm]     = useState({ current_password: "", new_password: "", confirm: "" });

  const [nameOk, setNameOk]   = useState("");
  const [nameErr, setNameErr] = useState("");
  const [pwOk, setPwOk]       = useState("");
  const [pwErr, setPwErr]     = useState("");
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    get<OrgInfo>("/admin/org").then(setOrg).catch(() => {});
    get<GroupInfo[]>("/auth/me/groups").then(setGroups).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Pre-fill name from JWT
  useEffect(() => {
    if (user) setNameForm({ full_name: "" });
  }, [user]);

  async function saveName(e: FormEvent) {
    e.preventDefault();
    setNameOk(""); setNameErr("");
    setSaving(true);
    try {
      await patch("/auth/me", { full_name: nameForm.full_name });
      setNameOk("Nombre actualizado");
      setNameForm({ full_name: "" });
      // Refresh token so JWT reflects new name
      const res = await fetch("/api/auth/session");
      if (res.ok) { const { access_token } = await res.json(); setToken(access_token); }
    } catch (e: unknown) { setNameErr(e instanceof Error ? e.message : "Error al guardar"); }
    finally { setSaving(false); setTimeout(() => setNameOk(""), 3000); }
  }

  async function savePassword(e: FormEvent) {
    e.preventDefault();
    setPwOk(""); setPwErr("");
    if (pwForm.new_password !== pwForm.confirm) { setPwErr("Las contraseñas no coinciden"); return; }
    if (pwForm.new_password.length < 8) { setPwErr("Mínimo 8 caracteres"); return; }
    setSaving(true);
    try {
      await patch("/auth/me", { current_password: pwForm.current_password, new_password: pwForm.new_password });
      setPwOk("Contraseña actualizada");
      setPwForm({ current_password: "", new_password: "", confirm: "" });
    } catch (e: unknown) { setPwErr(e instanceof Error ? e.message : "Error al guardar"); }
    finally { setSaving(false); setTimeout(() => setPwOk(""), 3000); }
  }

  const BASE_ROLES = ["contador", "auxiliar_contable"];

  const [upgradeOk, setUpgradeOk]   = useState("");
  const [upgradeErr, setUpgradeErr] = useState("");
  const [upgradeLoading, setUpgrL]  = useState(false);
  const [alreadyRequested, setAlreadyRequested] = useState(false);

  async function requestUpgrade() {
    setUpgradeOk(""); setUpgradeErr("");
    setUpgrL(true);
    try {
      const res = await fetch("/api-proxy/auth/request-admin", { method: "POST", headers: { Authorization: `Bearer ${sessionStorage.getItem("taxops_token")}` } });
      if (!res.ok) { const d = await res.json().catch(() => ({})); setUpgradeErr(d.detail ?? "Error"); return; }
      setUpgradeOk("Solicitud enviada. Un administrador revisará tu solicitud."); setAlreadyRequested(true);
    } catch { setUpgradeErr("Error de conexión"); }
    finally { setUpgrL(false); }
  }

  const roleBadge: Record<string, string> = {
    owner:             "bg-violet-50 text-violet-700",
    admin:             "bg-blue-50 text-blue-700",
    contador:          "bg-teal-50 text-teal-700",
    auxiliar_contable: "bg-gray-100 text-gray-600",
  };

  const planBadge: Record<string, string> = {
    pro:     "bg-brand-orange/10 text-brand-orange",
    starter: "bg-blue-50 text-blue-600",
    free:    "bg-gray-100 text-gray-500",
  };

  return (
    <div className="max-w-2xl space-y-6">

      {/* Info de cuenta */}
      <div className="card">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-gray-100 rounded-xl"><User size={20} className="text-gray-600" /></div>
          <div>
            <h2 className="font-semibold text-gray-900">Información de cuenta</h2>
            <p className="text-xs text-gray-500">Tu email, rol y organización</p>
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt className="text-xs text-gray-400 mb-0.5">Email</dt>
            <dd className="font-medium text-gray-900">{user?.email ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-400 mb-0.5">Rol</dt>
            <dd><span className={`badge capitalize ${roleBadge[user?.role ?? ""] ?? "bg-gray-100 text-gray-600"}`}>{user?.role ?? "—"}</span></dd>
          </div>
          {org && (
            <>
              <div>
                <dt className="text-xs text-gray-400 mb-0.5">Organización</dt>
                <dd className="font-medium text-gray-900">{org.name}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-400 mb-0.5">Plan</dt>
                <dd><span className={`badge capitalize ${planBadge[org.plan] ?? "bg-gray-100 text-gray-500"}`}>{org.plan}</span></dd>
              </div>
              {org.nit && (
                <div>
                  <dt className="text-xs text-gray-400 mb-0.5">NIT</dt>
                  <dd className="font-medium text-gray-900">{org.nit}</dd>
                </div>
              )}
            </>
          )}
        </dl>
      </div>

      {/* Editar nombre */}
      <div className="card">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-gray-100 rounded-xl"><User size={20} className="text-gray-600" /></div>
          <div>
            <h2 className="font-semibold text-gray-900">Nombre</h2>
            <p className="text-xs text-gray-500">Actualiza tu nombre visible</p>
          </div>
        </div>
        <Flash ok={nameOk} err={nameErr} />
        <form onSubmit={saveName} className="mt-3 space-y-3">
          <input
            className="input"
            placeholder="Tu nombre completo"
            value={nameForm.full_name}
            onChange={(e) => setNameForm({ full_name: e.target.value })}
            required
          />
          <button type="submit" disabled={saving} className="btn-primary">Guardar nombre</button>
        </form>
      </div>

      {/* Cambiar contraseña */}
      <div className="card">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 bg-gray-100 rounded-xl"><Lock size={20} className="text-gray-600" /></div>
          <div>
            <h2 className="font-semibold text-gray-900">Cambiar contraseña</h2>
            <p className="text-xs text-gray-500">Mínimo 8 caracteres</p>
          </div>
        </div>
        <Flash ok={pwOk} err={pwErr} />
        <form onSubmit={savePassword} className="mt-3 space-y-3">
          <input
            type="password"
            className="input"
            placeholder="Contraseña actual"
            required
            value={pwForm.current_password}
            onChange={(e) => setPwForm((p) => ({ ...p, current_password: e.target.value }))}
          />
          <input
            type="password"
            className="input"
            placeholder="Nueva contraseña"
            required
            minLength={8}
            value={pwForm.new_password}
            onChange={(e) => setPwForm((p) => ({ ...p, new_password: e.target.value }))}
          />
          <input
            type="password"
            className="input"
            placeholder="Confirmar nueva contraseña"
            required
            value={pwForm.confirm}
            onChange={(e) => setPwForm((p) => ({ ...p, confirm: e.target.value }))}
          />
          <button type="submit" disabled={saving} className="btn-primary">Cambiar contraseña</button>
        </form>
      </div>

      {/* Organización */}
      {org && (
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 bg-gray-100 rounded-xl"><Building2 size={20} className="text-gray-600" /></div>
            <h2 className="font-semibold text-gray-900">Organización</h2>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-xs text-gray-400 mb-0.5">Nombre</dt><dd className="font-medium text-gray-900">{org.name}</dd></div>
            <div><dt className="text-xs text-gray-400 mb-0.5">Slug</dt><dd className="text-gray-600">{org.slug}</dd></div>
            {org.nit && <div><dt className="text-xs text-gray-400 mb-0.5">NIT</dt><dd className="font-medium text-gray-900">{org.nit}</dd></div>}
            <div><dt className="text-xs text-gray-400 mb-0.5">Plan</dt><dd><span className={`badge capitalize ${planBadge[org.plan] ?? "bg-gray-100"}`}>{org.plan}</span></dd></div>
          </dl>
        </div>
      )}

      {/* Solicitar cambio de perfil — solo para roles base */}
      {user && BASE_ROLES.includes(user.role) && (
        <div className="card border border-amber-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 bg-amber-50 rounded-xl"><Shield size={20} className="text-amber-600" /></div>
            <div>
              <h2 className="font-semibold text-gray-900">Solicitar cambio de perfil</h2>
              <p className="text-xs text-gray-500">Pide a un administrador que te asigne un perfil diferente</p>
            </div>
          </div>
          <Flash ok={upgradeOk} err={upgradeErr} />
          {!alreadyRequested ? (
            <button
              onClick={requestUpgrade}
              disabled={upgradeLoading}
              className="btn-primary mt-2"
            >
              {upgradeLoading ? "Enviando..." : "Solicitar cambio de perfil"}
            </button>
          ) : (
            <p className="text-sm text-amber-700 bg-amber-50 rounded-xl p-3 mt-2">Solicitud enviada — un administrador la revisará pronto.</p>
          )}
        </div>
      )}

      {/* Grupos */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 bg-gray-100 rounded-xl"><Layers size={20} className="text-gray-600" /></div>
          <div>
            <h2 className="font-semibold text-gray-900">Mis grupos</h2>
            <p className="text-xs text-gray-500">Grupos a los que perteneces y sus módulos</p>
          </div>
        </div>
        {groups.length === 0 ? (
          <p className="text-sm text-gray-400">No perteneces a ningún grupo todavía.</p>
        ) : (
          <div className="space-y-2">
            {groups.map((g) => (
              <div key={g.id} className="p-3 bg-gray-50 rounded-xl">
                <p className="font-medium text-gray-900 text-sm">{g.name}</p>
                {g.description && <p className="text-xs text-gray-500 mt-0.5">{g.description}</p>}
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {g.modules.map((m) => (
                    <span key={m} className="px-2 py-0.5 bg-brand-orange/10 text-brand-orange rounded-full text-xs">{m}</span>
                  ))}
                  {g.modules.length === 0 && <span className="text-xs text-gray-400">Sin módulos</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
