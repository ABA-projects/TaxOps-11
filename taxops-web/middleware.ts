import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Rutas que no requieren autenticación
const PUBLIC_PATHS = ["/login", "/signup", "/api/auth", "/auth/callback", "/api-proxy", "/invite"];

// La raíz "/" es pública (landing page)
const PUBLIC_EXACT = ["/"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Permitir raíz exacta (landing page pública)
  if (PUBLIC_EXACT.includes(pathname)) {
    return NextResponse.next();
  }

  // Permitir rutas públicas por prefijo
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Verificar cookie de sesión (set en httpOnly por /api/auth/login)
  const hasSession = request.cookies.has("taxops_refresh");

  if (!hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Excluir assets estáticos y rutas de Next.js internos
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
