import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const refreshToken = request.cookies.get("taxops_refresh")?.value;

  if (!refreshToken) {
    return NextResponse.json({ error: "Sin sesión" }, { status: 401 });
  }

  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    // Cookie inválida/expirada — limpiar
    const response = NextResponse.json({ error: "Sesión expirada" }, { status: 401 });
    response.cookies.delete("taxops_refresh");
    return response;
  }

  const data: { access_token: string } = await res.json();
  return NextResponse.json({ access_token: data.access_token });
}
