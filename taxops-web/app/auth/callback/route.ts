import { NextRequest, NextResponse } from "next/server";

function getBaseUrl(request: NextRequest): string {
  // Railway (and most proxies) set x-forwarded-host with the public hostname
  const fwdHost = request.headers.get("x-forwarded-host");
  const fwdProto = request.headers.get("x-forwarded-proto") ?? "https";
  if (fwdHost) return `${fwdProto}://${fwdHost}`;
  // Fallback: use env var baked at build time
  if (process.env.NEXT_PUBLIC_API_URL) {
    // derive frontend origin from the request URL as last resort
  }
  return new URL(request.url).origin;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const access_token = searchParams.get("access_token");
  const refresh_token = searchParams.get("refresh_token");

  const base = getBaseUrl(request);

  if (!access_token || !refresh_token) {
    return NextResponse.redirect(`${base}/login?error=oauth_failed`);
  }

  // Store access token in a readable cookie so the client can pick it up
  const response = NextResponse.redirect(`${base}/dashboard`);

  response.cookies.set("taxops_access_pending", access_token, {
    httpOnly: false, // must be readable by JS to move to sessionStorage
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60, // only needed for 1 redirect
    path: "/",
  });

  response.cookies.set("taxops_refresh", refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7,
    path: "/",
  });

  return response;
}
