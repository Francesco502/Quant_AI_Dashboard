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

function getApiConnectSources() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim()
  const sources = new Set([
    "'self'",
    "http://127.0.0.1:8685",
    "http://localhost:8685",
    "ws://127.0.0.1:8685",
    "ws://localhost:8685",
  ])

  if (apiUrl && /^https?:\/\//i.test(apiUrl)) {
    try {
      const url = new URL(apiUrl)
      sources.add(url.origin)
      sources.add(`${url.protocol === "https:" ? "wss:" : "ws:"}//${url.host}`)
    } catch {
      // Keep the conservative default sources when NEXT_PUBLIC_API_URL is malformed.
    }
  }

  return Array.from(sources).join(" ")
}

const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      `connect-src ${getApiConnectSources()}`,
    ].join("; "),
  },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
]

const nextConfig: NextConfig = {
  ...(isStaticExport ? { output: "export" as const } : {}),
  ...rewriteConfig,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ]
  },
  images: { unoptimized: true },
  poweredByHeader: false,
};

export default nextConfig;
