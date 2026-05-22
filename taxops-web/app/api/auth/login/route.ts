import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const body = await request.json();

  // Support pre-generated tokens from register/OAuth flows
  if (body._tokens) {
    const { access_token, refresh_token } = body._tokens as { access_token: string; refresh_token: string };
    const response = NextResponse.json({ access_token });
    response.cookies.set("taxops_refresh", refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7,
      path: "/",
    });
    return response;
  }

  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error de autenticación" }));
    return NextResponse.json(err, { status: res.status });
  }

  const data: { access_token: string; refresh_token: string } = await res.json();

  const response = NextResponse.json({ access_token: data.access_token });

  response.cookies.set("taxops_refresh", data.refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7,
    path: "/",
  });

  return response;
}

