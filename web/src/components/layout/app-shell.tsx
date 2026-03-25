"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSyncExternalStore } from "react"
import { AnimatePresence, motion } from "framer-motion"

import { Header } from "@/components/layout/header"
import { WorkspaceSidebar } from "@/components/layout/workspace-sidebar"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  getActiveWorkspaceGroup,
  getWorkspaceGroups,
  isWorkspaceItemActive,
} from "@/lib/workspace-nav"

const PUBLIC_ROUTES = new Set(["/login", "/register"])

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { isAuthenticated, user } = useAuth()
  const isPublicRoute = PUBLIC_ROUTES.has(pathname)
  const isClient = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  )
  const workspaceGroups = getWorkspaceGroups(user?.role === "admin")
  const activeGroup = getActiveWorkspaceGroup(pathname, workspaceGroups)

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

  if (!isClient || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div
          className={cn(
            "glass-card flex min-h-[220px] w-full max-w-md flex-col items-center justify-center rounded-3xl px-8 text-center",
          )}
        >
          <div className="h-10 w-10 rounded-2xl border border-black/[0.06] bg-white/60 shadow-[0_10px_30px_rgba(0,0,0,0.04)]" />
          <p className="mt-5 text-sm font-medium text-foreground/80">正在验证登录状态</p>
          <p className="mt-2 max-w-xs text-[13px] leading-6 text-muted-foreground">
            只有登录后才会显示系统内部页面与导航入口。
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <div className="border-b border-white/40 bg-white/20 backdrop-blur-lg xl:hidden">
        <div className="mx-auto flex w-full max-w-[1480px] gap-3 overflow-x-auto px-6 py-4 no-scrollbar md:px-10">
          {activeGroup.items.map((item) => {
            const isActive = isWorkspaceItemActive(pathname, item.href)

            return (
              <Link key={item.href} href={item.href} className="shrink-0">
                <div
                  className={cn(
                    "rounded-full border px-3.5 py-2 text-[12px] font-medium transition-colors",
                    isActive
                      ? "border-[#8E734D]/16 bg-white text-foreground"
                      : "border-black/[0.05] bg-white/58 text-foreground/58",
                  )}
                >
                  {item.name}
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-[1480px] flex-1 gap-8 px-6 py-8 md:px-10 md:py-10 xl:gap-12">
        <WorkspaceSidebar group={activeGroup} pathname={pathname} />

        <AnimatePresence mode="wait">
          <motion.main
            key={pathname}
            initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -12, filter: "blur(4px)" }}
            transition={{ type: "spring", bounce: 0, duration: 0.4 }}
            className="min-w-0 flex-1 overflow-y-auto"
          >
            {children}
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  )
}
