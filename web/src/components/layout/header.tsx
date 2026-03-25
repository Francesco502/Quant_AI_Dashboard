"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Bell, ChevronDown, LogOut, Menu, User, X } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { useMemo, useState } from "react"

import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  getActiveWorkspaceGroup,
  getWorkspaceGroups,
  isWorkspaceItemActive,
} from "@/lib/workspace-nav"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export function Header() {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isAdmin = user?.role === "admin"
  const groups = useMemo(() => getWorkspaceGroups(isAdmin), [isAdmin])
  const activeGroup = useMemo(() => getActiveWorkspaceGroup(pathname, groups), [groups, pathname])
  const toneClasses = {
    indigo: {
      active: "bg-[rgba(111,124,142,0.14)] text-[#5E6876]",
      idle: "bg-[rgba(111,124,142,0.08)] text-[#6F7C8E]",
    },
    celadon: {
      active: "bg-[rgba(77,115,88,0.14)] text-[#45674F]",
      idle: "bg-[rgba(77,115,88,0.08)] text-[#4D7358]",
    },
    plum: {
      active: "bg-[rgba(122,105,115,0.14)] text-[#6D5C66]",
      idle: "bg-[rgba(122,105,115,0.08)] text-[#7A6973]",
    },
    ochre: {
      active: "bg-[rgba(176,142,97,0.16)] text-[#8C724C]",
      idle: "bg-[rgba(176,142,97,0.09)] text-[#B08E61]",
    },
    ink: {
      active: "bg-[rgba(77,71,66,0.14)] text-[#4D4742]",
      idle: "bg-[rgba(77,71,66,0.08)] text-[#6B635D]",
    },
  } as const

  return (
    <header className="sticky top-0 z-50 border-b border-white/40 bg-white/30 backdrop-blur-2xl">
      <div className="mx-auto flex h-20 w-full max-w-[1480px] items-center gap-4 px-6 sm:px-8 lg:px-10">
        <button
          onClick={() => setMobileMenuOpen((open) => !open)}
          className="flex h-9 w-9 items-center justify-center rounded-2xl border border-black/[0.06] bg-[rgba(250,247,242,0.9)] text-foreground/72 transition-colors hover:bg-white hover:text-foreground xl:hidden"
          aria-label={mobileMenuOpen ? "关闭导航菜单" : "打开导航菜单"}
        >
          {mobileMenuOpen ? <X className="h-[18px] w-[18px]" /> : <Menu className="h-[18px] w-[18px]" />}
        </button>

        <Link href="/" className="group flex min-w-[160px] items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[18px] border border-[#8E734D]/18 bg-[linear-gradient(145deg,rgba(252,249,244,0.98),rgba(240,232,220,0.96))] shadow-[0_12px_28px_rgba(46,38,30,0.05)] transition-transform duration-300 group-hover:-translate-y-0.5">
            <span className="text-sm font-semibold tracking-[-0.08em] text-[#7C5B3C]">量</span>
          </div>
          <div className="min-w-0">
            <div className="text-[15px] font-semibold tracking-[-0.03em] text-foreground/90">
              Quant<span className="font-light text-foreground/52"> AI</span>
            </div>
            <div className="text-[11px] tracking-[0.16em] text-foreground/32">量化研习台</div>
          </div>
        </Link>

        <div className="hidden min-w-0 flex-1 items-center justify-center xl:flex">
          <nav className="flex items-center gap-2 rounded-full border border-white/60 bg-white/40 backdrop-blur-md px-2.5 py-2 shadow-[0_8px_24px_rgba(142,115,77,0.03)]">
            {groups.map((group) => {
              const isActive = group.id === activeGroup.id

              return (
                <Link key={group.id} href={group.defaultHref}>
                  <div
                    className={cn(
                      "flex items-center gap-2.5 rounded-full px-5 py-2.5 text-[14px] font-medium tracking-wide transition-all duration-300",
                      isActive
                        ? "bg-white/80 text-foreground shadow-[0_4px_16px_rgba(0,0,0,0.04)]"
                        : "text-foreground/60 hover:bg-white/60 hover:text-foreground/90",
                    )}
                  >
                    <span
                      className={cn(
                        "inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors",
                        isActive ? toneClasses[group.tone].active : toneClasses[group.tone].idle,
                      )}
                    >
                      <group.icon className="h-3.5 w-3.5" />
                    </span>
                    {group.name}
                  </div>
                </Link>
              )
            })}
          </nav>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
          <button
            className="flex h-9 w-9 items-center justify-center rounded-2xl border border-transparent text-foreground/42 transition-colors hover:border-black/[0.05] hover:bg-white/75 hover:text-foreground/74"
            aria-label="通知"
          >
            <Bell className="h-4 w-4" />
          </button>

          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex h-10 items-center gap-2.5 rounded-full border border-white/60 bg-white/40 backdrop-blur-md px-4 text-foreground/70 shadow-[0_4px_16px_rgba(142,115,77,0.03)] transition-all duration-300 hover:bg-white/80 hover:text-foreground/90"
                  aria-label={`当前账户 ${user.username}`}
                  title={`已登录：${user.username}`}
                >
                  <User className="h-4 w-4" />
                  <span className="hidden text-[12px] font-medium sm:inline">{user.username}</span>
                  <ChevronDown className="hidden h-3.5 w-3.5 text-foreground/34 sm:inline" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-56 rounded-[24px] border border-black/[0.08] bg-[rgba(247,243,237,0.98)] p-1.5 text-foreground shadow-[0_22px_52px_rgba(41,33,25,0.14)]"
              >
                <DropdownMenuLabel className="px-3 py-3">
                  <div className="text-[11px] font-medium tracking-[0.18em] text-foreground/35">当前账户</div>
                  <div className="mt-2 text-sm font-semibold text-foreground/90">{user.username}</div>
                  <div className="mt-1 text-xs text-foreground/48">{isAdmin ? "管理员账户" : "已登录用户"}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-black/[0.06]" />
                <DropdownMenuItem
                  onClick={logout}
                  className="cursor-pointer rounded-2xl px-3 py-2.5 text-market-up focus:bg-market-up-soft focus:text-market-up"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Link href="/login">
              <button
                className="flex h-9 w-9 items-center justify-center rounded-2xl border border-transparent text-foreground/42 transition-colors hover:border-black/[0.05] hover:bg-white/75 hover:text-foreground/74"
                aria-label="前往登录"
              >
                <User className="h-4 w-4" />
              </button>
            </Link>
          )}
        </div>
      </div>

      <AnimatePresence>
        {mobileMenuOpen ? (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="border-t border-black/[0.05] bg-[rgba(247,243,237,0.97)] px-4 pb-4 pt-3 shadow-[0_18px_40px_rgba(41,33,25,0.08)] xl:hidden"
          >
            <div className="mx-auto max-w-[1480px] space-y-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {groups.map((group) => {
                  const isActive = group.id === activeGroup.id

                  return (
                    <Link
                      key={group.id}
                      href={group.defaultHref}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "rounded-2xl border px-3 py-2.5 text-center text-[13px] font-medium transition-colors",
                        isActive
                          ? "border-[#8E734D]/14 bg-white text-foreground"
                          : "border-black/[0.05] bg-white/66 text-foreground/62",
                      )}
                    >
                      <div className="flex items-center justify-center gap-2">
                        <group.icon className="h-3.5 w-3.5" />
                        {group.name}
                      </div>
                    </Link>
                  )
                })}
              </div>

              <div className="rounded-[26px] border border-black/[0.06] bg-white/70 p-3">
                <div className="px-1 pb-3">
                  <div className="text-[11px] tracking-[0.18em] text-foreground/34">当前分组</div>
                  <div className="mt-2 text-[17px] font-semibold tracking-[-0.02em] text-foreground/92">
                    {activeGroup.name}
                  </div>
                  <div className="mt-1 text-[12px] leading-5 text-foreground/50">{activeGroup.description}</div>
                </div>

                <div className="space-y-1.5">
                  {activeGroup.items.map((item) => {
                    const isActive = isWorkspaceItemActive(pathname, item.href)

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={cn(
                          "block rounded-2xl px-3 py-2.5 transition-colors",
                          isActive
                            ? "bg-[rgba(255,255,255,0.94)] text-foreground"
                            : "text-foreground/62 hover:bg-black/[0.03] hover:text-foreground/88",
                        )}
                      >
                        <div className="font-medium">{item.name}</div>
                        <div className="mt-1 text-[12px] leading-5 text-foreground/46">{item.description}</div>
                      </Link>
                    )
                  })}
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  )
}
