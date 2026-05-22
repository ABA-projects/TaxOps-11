/**
 * auth.ts — Gestión del estado de autenticación.
 *
 * Flujo:
 * 1. Login → Next.js API route → cookie httpOnly (refresh) + access_token en sessionStorage
 * 2. loadSession() → llama /api/auth/session con la cookie → retorna nuevo access_token
 * 3. Logout → borra cookie + sessionStorage
 */
"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from "react";

const API_URL = "/api-proxy";

export type AuthUser = {
  user_id: string;
  org_id: string;
  email: string;
  role: string;
  is_superadmin?: boolean;
};

type AuthCtx = {
  token: string | null;
  user: AuthUser | null;
  loading: boolean;
  loadSession: () => Promise<void>;
  setToken: (t: string) => void;
  clearSession: () => void;
  setSuperadmin: (v: boolean) => void;
};

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem("taxops_token");
  });
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  function parseJwt(t: string): AuthUser | null {
    try {
      const payload = JSON.parse(atob(t.split(".")[1]));
      return {
        user_id: payload.sub,
        org_id: payload.org_id,
        email: payload.email,
        role: payload.role,
        is_superadmin: payload.is_superadmin ?? false,
      };
    } catch {
      return null;
    }
  }

  const setToken = useCallback((t: string) => {
    sessionStorage.setItem("taxops_token", t);
    setTokenState(t);
    setUser(parseJwt(t));
  }, []);

  const clearSession = useCallback(() => {
    sessionStorage.removeItem("taxops_token");
    setTokenState(null);
    setUser(null);
  }, []);

  const setSuperadmin = useCallback((v: boolean) => {
    setUser((prev) => prev ? { ...prev, is_superadmin: v } : prev);
  }, []);

  /**
   * Intenta renovar el access token usando la cookie httpOnly de refresh.
   * Llamado al montar el AppShell.
   */
  const loadSession = useCallback(async () => {
    // Si ya tenemos token válido en sessionStorage, úsalo
    const stored = sessionStorage.getItem("taxops_token");
    if (stored) {
      const parsed = parseJwt(stored);
      if (parsed) {
        setTokenState(stored);
        setUser(parsed);
        setLoading(false);
        return;
      }
    }

    // Sin token en memoria — intentar refresh con cookie
    try {
      const res = await fetch("/api/auth/session");
      if (!res.ok) throw new Error("Sin sesión");
      const { access_token } = await res.json();
      setToken(access_token);
    } catch {
      clearSession();
      throw new Error("Sesión expirada");
    } finally {
      setLoading(false);
    }
  }, [setToken, clearSession]);

  return (
    <AuthContext.Provider
      value={{ token, user, loading, loadSession, setToken, clearSession, setSuperadmin }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}

export { API_URL };
