import "./globals.css"
import { Header } from "@/components/layout/header"
import { cn } from "@/lib/utils"
import { Providers } from "@/components/providers"

export const metadata = {
  title: "Quant AI Dashboard",
  description: "Advanced Quantitative Trading Dashboard",
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
          "min-h-screen noise-bg font-sans",
          "bg-[#F5F5F3] dark:bg-[#0A0A0A]"
        )}
      >
        <Providers>
          <div className="flex flex-col min-h-screen">
            <Header />
            <main className="flex-1 container mx-auto px-4 py-6 md:px-8 md:py-8 overflow-y-auto">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  )
}
