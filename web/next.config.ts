import type { NextConfig } from "next";

const isStaticExport = process.env.NEXT_STATIC_EXPORT === "1";

const rewriteConfig = !isStaticExport
  ? {
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
    }
  : {}

const nextConfig: NextConfig = {
  ...(isStaticExport ? { output: "export" as const } : {}),
  ...rewriteConfig,
  images: { unoptimized: true },
  poweredByHeader: false,
};

export default nextConfig;
