import "./globals.css"
import { AppShell } from "@/components/layout/app-shell"
import { cn } from "@/lib/utils"
import { Providers } from "@/components/providers"

export const metadata = {
  title: "Quant AI 量化研习台",
  description: "面向个人研究、回测、模拟交易与资产管理的量化工作台",
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
