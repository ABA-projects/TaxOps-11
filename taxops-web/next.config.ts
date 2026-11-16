import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // No anunciar el framework (x-powered-by: Next.js).
  poweredByHeader: false,
  async headers() {
    // Content-Security-Policy queda fuera a propósito: el App Router inyecta scripts inline, así
    // que una CSP correcta necesita nonces por middleware (y permitir Google OAuth y fuentes).
    // Mal configurada deja la app en blanco; se hace aparte y se valida en navegador.
    return [
      {
        source: "/:path*",
        headers: [
          // includeSubDomains aplica a *.app.taxopsapp.com (no a los hermanos de taxopsapp.com).
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          // La app no se embebe a sí misma en iframes: se puede negar el framing por completo.
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
  async rewrites() {
    // NEXT_PUBLIC_API_URL → Render API URL (e.g. https://taxops-api.onrender.com)
    // Falls back to localhost for local dev
    const api = (
      process.env.NEXT_PUBLIC_API_URL ??
      "http://localhost:8000"
    ).trim();
    return [
      {
        source: "/api-proxy/:path*",
        destination: `${api}/:path*`,
      },
    ];
  },
};

export default nextConfig;
