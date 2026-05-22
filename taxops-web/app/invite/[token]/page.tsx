"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";

type InviteInfo = { email: string; role: string; org_name: string };

export default function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();

  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [form, setForm] = useState({ full_name: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`/api-proxy/auth/invite/${token}`)
      .then((r) => {
        if (!r.ok) { setNotFound(true); return null; }
        return r.json();
      })
      .then((d) => d && setInfo(d))
      .catch(() => setNotFound(true));
  }, [token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (form.password !== form.confirm) { setError("Las contraseñas no coinciden"); return; }
    if (form.password.length < 8) { setError("La contraseña debe tener al menos 8 caracteres"); return; }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`/api-proxy/auth/invite/${token}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: form.full_name, password: form.password }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail ?? "Error al activar la cuenta");
        return;
      }
      const { access_token, refresh_token } = await res.json();
      await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ _tokens: { access_token, refresh_token } }),
      });
      sessionStorage.setItem("taxops_token", access_token);
      router.replace("/dashboard");
    } catch {
      setError("Error de conexión. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  if (notFound) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-brand-navy to-slate-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-sm w-full text-center">
          <p className="text-2xl mb-3">🔗</p>
          <h1 className="text-lg font-bold text-gray-900 mb-2">Invitación inválida</h1>
          <p className="text-sm text-gray-500 mb-5">Este enlace expiró o ya fue utilizado.</p>
          <Link href="/login" className="btn-primary text-sm">Ir al inicio de sesión</Link>
        </div>
      </div>
    );
  }

  if (!info) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-orange border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-brand-navy to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-4xl font-black tracking-tight">
            <span className="text-brand-orange">Tax</span>
            <span className="text-white">Ops</span>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="mb-6 p-4 bg-brand-orange/5 border border-brand-orange/20 rounded-xl">
            <p className="text-xs text-gray-500 mb-1">Te invitaron a unirte a</p>
            <p className="font-bold text-gray-900">{info.org_name}</p>
            <p className="text-sm text-gray-600 mt-1">
              <span className="font-medium">{info.email}</span>
              <span className="ml-2 px-2 py-0.5 bg-brand-orange/10 text-brand-orange rounded-full text-xs capitalize">{info.role}</span>
            </p>
          </div>

          <h1 className="text-lg font-bold text-gray-900 mb-1">Activa tu cuenta</h1>
          <p className="text-sm text-gray-500 mb-5">Completa tu perfil para empezar.</p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tu nombre</label>
              <input
                className="input"
                placeholder="Nombre completo"
                value={form.full_name}
                onChange={(e) => setForm((p) => ({ ...p, full_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <input
                type="password"
                className="input"
                placeholder="Mínimo 8 caracteres"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar contraseña</label>
              <input
                type="password"
                className="input"
                placeholder="Repite la contraseña"
                required
                value={form.confirm}
                onChange={(e) => setForm((p) => ({ ...p, confirm: e.target.value }))}
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? "Activando..." : "Activar cuenta →"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
