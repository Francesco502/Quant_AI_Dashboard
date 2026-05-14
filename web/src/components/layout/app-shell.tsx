"use client"

import { usePathname } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"

import { Header } from "@/components/layout/header"
import { AppToaster } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"

const PUBLIC_ROUTES = new Set(["/login", "/register"])

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { isAuthenticated, isReady } = useAuth()
  const isPublicRoute = PUBLIC_ROUTES.has(pathname)

  if (isPublicRoute) {
    return (
      <AnimatePresence mode="wait">
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -12, filter: "blur(4px)" }}
          transition={{ type: "spring", bounce: 0, duration: 0.4 }}
          className="mx-auto flex-1 w-full max-w-[1480px] px-4 py-6 md:px-8 md:py-8"
        >
          {children}
        </motion.main>
      </AnimatePresence>
    )
  }

  if (!isReady || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="glass-card flex min-h-[220px] w-full max-w-md flex-col items-center justify-center rounded-3xl px-8 text-center">
          <div className="h-10 w-10 rounded-2xl border border-black/[0.06] bg-[rgba(250,246,239,0.60)] shadow-[0_10px_30px_rgba(0,0,0,0.04)]" />
          <p className="mt-5 text-sm font-medium text-foreground/80">
            {!isReady ? "正在验证登录状态" : "正在跳转到登录页"}
          </p>
          <p className="mt-2 max-w-xs text-[13px] leading-6 text-muted-foreground">
            {!isReady
              ? "只有登录后才会显示系统内部页面与导航入口。"
              : "当前会话未激活，即将回到登录页面。"}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen min-w-0 flex-col overflow-x-hidden">
      <Header />

      <AnimatePresence mode="wait">
        <motion.main
          key={pathname}
          id="main-content"
          initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -12, filter: "blur(4px)" }}
          transition={{ type: "spring", bounce: 0, duration: 0.4 }}
          className="mx-auto w-full min-w-0 max-w-[1480px] flex-1 overflow-x-hidden px-3 py-5 sm:px-6 md:px-10 md:py-10"
        >
          {children}
        </motion.main>
      </AnimatePresence>
      <AppToaster />
    </div>
  )
}
