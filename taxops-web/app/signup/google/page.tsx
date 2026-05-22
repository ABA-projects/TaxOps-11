"use client";

import { useState, useEffect, FormEvent, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

const API_URL = "/api-proxy";

function GoogleSignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const email = searchParams.get("email") ?? "";
  const name = searchParams.get("name") ?? "";

  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!email) router.replace("/signup");
  }, [email, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          full_name: name,
          org_name: orgName,
          password: crypto.randomUUID() + crypto.randomUUID(),
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail ?? "Error al crear la cuenta");
        return;
      }

      const { access_token, refresh_token } = await res.json();

      await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ _tokens: { access_token, refresh_token } }),
      });

      sessionStorage.setItem("taxops_token", access_token);
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Error de conexión. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-brand-navy to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-block">
            <div className="text-4xl font-black tracking-tight">
              <span className="text-brand-orange">Tax</span>
              <span className="text-white">Ops</span>
            </div>
          </Link>
          <p className="text-slate-400 text-sm mt-2">Automatización Contable Colombia</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center text-green-600 text-lg">✓</div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">¡Cuenta de Google verificada!</h1>
              <p className="text-sm text-gray-500">{email}</p>
            </div>
          </div>

          <p className="text-sm text-gray-600 mb-6">Solo falta un dato para crear tu espacio de trabajo.</p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                ¿Cómo se llama tu empresa o firma?
              </label>
              <input
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="ABA Contable S.A.S."
                required
                autoFocus
                className="input"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-2"
            >
              {loading ? "Creando cuenta..." : "Crear mi cuenta →"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function GoogleSignupPage() {
  return (
    <Suspense>
      <GoogleSignupForm />
    </Suspense>
  );
}
