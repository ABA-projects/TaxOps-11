"use client";

import { useState, useEffect, FormEvent, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

const API_URL = "/api-proxy";

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [googleAvailable, setGoogleAvailable] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/auth/google/status`)
      .then((r) => r.json())
      .then((d) => setGoogleAvailable(d.available === true))
      .catch(() => setGoogleAvailable(false));
  }, []);

  const [form, setForm] = useState({
    email: searchParams.get("email") ?? "",
    password: "",
    full_name: "",
    org_name: "",
  });
  const [error, setError] = useState(
    searchParams.get("error") === "no_account"
      ? "Tu cuenta de Google no está registrada. Completa el formulario para crear tu cuenta."
      : ""
  );
  const [loading, setLoading] = useState(false);

  function update(field: string, value: string) {
    setForm((p) => ({ ...p, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // 1. Register on backend
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail ?? "Error al crear la cuenta");
        return;
      }

      const { access_token, refresh_token } = await res.json();

      // 2. Store refresh token as httpOnly cookie via Next.js route
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

  function handleGoogle() {
    window.location.href = `${API_URL}/auth/google`;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-brand-navy to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
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
          <h1 className="text-xl font-bold text-gray-900 mb-2">Crear cuenta gratis</h1>
          <p className="text-sm text-gray-500 mb-6">Sin tarjeta de crédito · 14 días gratis</p>

          {/* Google — solo visible si está configurado */}
          {googleAvailable && <button
            type="button"
            onClick={handleGoogle}
            className="w-full flex items-center justify-center gap-3 border border-gray-300 rounded-xl px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors mb-4"
          >
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
              <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/>
            </svg>
            Continuar con Google
          </button>}

          {googleAvailable && <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
            <div className="relative flex justify-center text-xs text-gray-400 bg-white px-2 w-fit mx-auto">o regístrate con email</div>
          </div>}

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nombre de la empresa / firma
              </label>
              <input
                type="text"
                value={form.org_name}
                onChange={(e) => update("org_name", e.target.value)}
                placeholder="ABA Contable S.A.S."
                required
                className="input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tu nombre
              </label>
              <input
                type="text"
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                placeholder="Jaime Henao"
                className="input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Correo electrónico
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                placeholder="contador@firma.com"
                required
                autoComplete="email"
                className="input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contraseña
              </label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                placeholder="Mínimo 8 caracteres"
                required
                minLength={8}
                autoComplete="new-password"
                className="input"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-2"
            >
              {loading ? "Creando cuenta..." : "Crear cuenta gratis →"}
            </button>
          </form>

          <p className="text-center text-xs text-gray-400 mt-5">
            ¿Ya tienes cuenta?{" "}
            <Link href="/login" className="text-brand-orange hover:underline font-medium">
              Inicia sesión
            </Link>
          </p>
        </div>

        <p className="text-center text-slate-500 text-xs mt-6">
          Al registrarte aceptas nuestros Términos de Servicio · Política de Privacidad
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}
