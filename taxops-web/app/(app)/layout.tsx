"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/layout/sidebar";
import Header from "@/components/layout/header";
import { AuthProvider, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/api";

const API_URL = "/api-proxy";

const BASE_ROLES = ["contador", "auxiliar_contable"];

function AdminRequestBanner() {
  const { token, user } = useAuth();
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

  if (!user || !BASE_ROLES.includes(user.role)) return null;

  async function handleRequest() {
    setStatus("loading");
    try {
      const res = await fetch(`${API_URL}/auth/request-admin`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setStatus(res.ok ? "done" : "error");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 flex items-center justify-between text-sm">
      <span className="text-amber-800">
        Tu cuenta tiene rol <strong>{user.role}</strong>. ¿Necesitas acceso de administrador?
      </span>
      {status === "idle" && (
        <button
          onClick={handleRequest}
          className="ml-4 bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded-lg font-medium transition-colors"
        >
          Solicitar acceso Admin
        </button>
      )}
      {status === "loading" && <span className="ml-4 text-amber-600">Enviando...</span>}
      {status === "done" && <span className="ml-4 text-green-700 font-medium">✓ Solicitud enviada. Un admin la revisará.</span>}
      {status === "error" && <span className="ml-4 text-red-600">Error al enviar. Intenta de nuevo.</span>}
    </div>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  const { token, loadSession, loading, setSuperadmin } = useAuth();
  const { get } = useApi();
  const router = useRouter();

  useEffect(() => {
    loadSession()
      .then(() => {
        // Chequeo superadmin en tiempo real — independiente del JWT
        get<{ is_superadmin: boolean }>("/admin/superadmin/check")
          .then((data) => { if (data.is_superadmin) setSuperadmin(true); })
          .catch(() => {});
      })
      .catch(() => { router.push("/login"); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-2xl font-black mb-2">
            <span className="text-brand-orange">Tax</span>
            <span className="text-brand-navy dark:text-white">Ops</span>
          </div>
          <p className="text-gray-400 text-sm">Cargando...</p>
        </div>
      </div>
    );
  }

  if (!token) return null;

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-slate-900">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <AdminRequestBanner />
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
