/**
 * api.ts — Cliente HTTP tipado para el backend FastAPI.
 *
 * Auto-renueva el access token al recibir 401 usando la cookie de refresh.
 * Para rutas que devuelven Blob (descarga de archivos), pasar blob=true.
 */
"use client";

const API_URL = "/api-proxy";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("taxops_token");
}

function authHeaders(token?: string | null): HeadersInit {
  const t = token ?? getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

/** Intenta renovar el access token con la cookie de refresh. Devuelve el nuevo token o null. */
async function tryRefresh(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/session");
    if (!res.ok) return null;
    const { access_token } = await res.json();
    sessionStorage.setItem("taxops_token", access_token);
    return access_token;
  } catch {
    return null;
  }
}

async function handleResponse<T>(res: Response, blob = false): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText || "Error de conexión" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  if (blob) return (await res.blob()) as unknown as T;
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

/** Ejecuta fetch y reintenta una vez si recibe 401 (token expirado). */
async function fetchWithRefresh(url: string, init: RequestInit): Promise<Response> {
  let res = await fetch(url, init);
  if (res.status !== 401) return res;

  // Intentar renovar el token
  const newToken = await tryRefresh();
  if (!newToken) return res; // devolver el 401 original

  // Reintentar con el nuevo token
  const newHeaders = new Headers(init.headers);
  newHeaders.set("Authorization", `Bearer ${newToken}`);
  res = await fetch(url, { ...init, headers: newHeaders });
  return res;
}

/** GET genérico */
async function get<T>(path: string): Promise<T> {
  const res = await fetchWithRefresh(`${API_URL}${path}`, {
    headers: { ...authHeaders() },
    cache: "no-store",
  });
  return handleResponse<T>(res);
}

/** POST con JSON body */
async function post<T>(path: string, body: unknown, blob = false): Promise<T> {
  const res = await fetchWithRefresh(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res, blob);
}

/** POST con FormData (multipart — upload de archivos) */
async function postForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetchWithRefresh(`${API_URL}${path}`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });
  return handleResponse<T>(res);
}

/** PATCH con JSON body */
async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithRefresh(`${API_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

/** PUT con JSON body */
async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithRefresh(`${API_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

/** DELETE */
async function del<T>(path: string): Promise<T> {
  const res = await fetchWithRefresh(`${API_URL}${path}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  return handleResponse<T>(res);
}

/** Hook de conveniencia para usarlo en componentes */
export function useApi() {
  return { get, post, postForm, patch, put, del };
}
