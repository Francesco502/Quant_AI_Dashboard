import type { Metadata, Viewport } from "next"
import "./globals.css"
import { AppShell } from "@/components/layout/app-shell"
import { BRAND_DESCRIPTION, BRAND_NAME } from "@/lib/brand"
import { cn } from "@/lib/utils"
import { Providers } from "@/components/providers"

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
    <html lang="zh-CN">
      <body
        className={cn(
          "min-h-screen noise-bg font-sans leading-relaxed tracking-wide",
          "bg-background text-foreground"
        )}
      >
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
