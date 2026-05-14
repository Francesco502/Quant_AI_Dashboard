import type { Metadata, Viewport } from "next"
import "./globals.css"
import { AppShell } from "@/components/layout/app-shell"
import { BRAND_DESCRIPTION, BRAND_NAME } from "@/lib/brand"
import { cn } from "@/lib/utils"
import { Providers } from "@/components/providers"
import { ErrorBoundary } from "@/components/error-boundary"

const THEME_SCRIPT = `
(function(){
  try {
    var t = localStorage.getItem("theme");
    if (t === "dark" || (!t && window.matchMedia("(prefers-color-scheme:dark)").matches)) {
      document.documentElement.classList.add("dark");
    }
  } catch(e) {}
})()
`.replace(/\s+/g, " ").trim()

const BRAND_ICON_URL = "/brand-icon.svg?v=20260415"

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: BRAND_DESCRIPTION,
  applicationName: BRAND_NAME,
  icons: {
    icon: [{ url: BRAND_ICON_URL, type: "image/svg+xml" }],
    shortcut: [{ url: BRAND_ICON_URL, type: "image/svg+xml" }],
    apple: [{ url: BRAND_ICON_URL, type: "image/svg+xml" }],
  },
}

export const viewport: Viewport = {
  themeColor: "#f6efe4",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body
        className={cn(
          "min-h-screen noise-bg font-sans leading-relaxed tracking-wide",
          "bg-background text-foreground"
        )}
      >
        <Providers>
          <ErrorBoundary>
            <AppShell>{children}</AppShell>
          </ErrorBoundary>
        </Providers>
      </body>
    </html>
  )
}
