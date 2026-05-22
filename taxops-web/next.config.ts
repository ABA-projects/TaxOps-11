import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
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
