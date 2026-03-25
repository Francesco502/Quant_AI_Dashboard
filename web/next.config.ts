import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: { unoptimized: true },
  async rewrites() {
    // Local development convenience:
    // When frontend uses `NEXT_PUBLIC_API_URL=/api`, proxy `/api/*` to the backend dev server
    // so browsers won't hit CORS during local testing.
    //
    // IMPORTANT:
    // - Only enabled in development.
    // - Production must rely on a real reverse proxy (nginx/caddy/traefik), never localhost.
    const apiUrl = process.env.NEXT_PUBLIC_API_URL
    const enableDevProxy = process.env.NODE_ENV === "development" && apiUrl?.trim() === "/api"
    if (!enableDevProxy) return []

    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8685/api/:path*",
      },
    ]
  },
};

export default nextConfig;
