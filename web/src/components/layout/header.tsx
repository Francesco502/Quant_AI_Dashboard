"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Bell, ChevronDown, LogOut, Menu, User, X } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { useMemo, useState } from "react"

import { useAuth } from "@/lib/auth-context"
import { BRAND_NAME, BRAND_SUBTITLE } from "@/lib/brand"
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
import { BrandMark } from "@/components/layout/brand-mark"

export function Header() {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isAdmin = user?.role === "admin"
  const groups = useMemo(() => getWorkspaceGroups(isAdmin), [isAdmin])
  const activeGroup = useMemo(() => getActiveWorkspaceGroup(pathname, groups), [groups, pathname])

  const toneClasses = {
    indigo: {
      idle: "bg-[rgba(var(--rgb-indigo),0.10)] text-[rgb(var(--rgb-indigo))]",
    },
    celadon: {
      idle: "bg-[rgba(var(--rgb-celadon),0.10)] text-[rgb(var(--rgb-celadon))]",
    },
    plum: {
      idle: "bg-[rgba(var(--rgb-plum),0.10)] text-[rgb(var(--rgb-plum))]",
    },
    ochre: {
      idle: "bg-[rgba(var(--rgb-ochre),0.11)] text-[rgb(var(--rgb-ochre))]",
    },
    ink: {
      idle: "bg-[rgba(var(--rgb-ink),0.08)] text-[rgba(var(--rgb-ink),0.78)]",
    },
  } as const

  return (
    <header className="sticky top-0 z-50 border-b border-[rgba(77,71,66,0.08)] bg-[rgba(250,246,239,0.58)] backdrop-blur-2xl">
      <div className="mx-auto flex h-21 w-full max-w-[1480px] items-center gap-4 px-6 sm:px-8 lg:px-10">
        <button
          onClick={() => setMobileMenuOpen((open) => !open)}
          className="flex h-10 w-10 items-center justify-center rounded-2xl border border-black/[0.06] bg-[rgba(250,247,242,0.92)] text-foreground/72 transition-[background-color,border-color,color] duration-300 hover:bg-[rgba(250,246,239,0.98)] hover:text-foreground xl:hidden"
          aria-label={mobileMenuOpen ? "关闭导航菜单" : "打开导航菜单"}
        >
          {mobileMenuOpen ? <X className="h-[18px] w-[18px]" /> : <Menu className="h-[18px] w-[18px]" />}
        </button>

        <Link href="/" className="group flex min-w-[228px] items-center gap-3.5">
          <BrandMark className="transition-transform duration-300 group-hover:-translate-y-0.5" />
          <div className="min-w-0">
            <div className="text-[1.04rem] font-semibold tracking-[0.02em] text-foreground/94">
              {BRAND_NAME}
            </div>
            <div className="mt-1 text-[0.8rem] font-medium tracking-[0.12em] text-foreground/68">
              {BRAND_SUBTITLE}
            </div>
          </div>
        </Link>

        <div className="hidden min-w-0 flex-1 items-center justify-center xl:flex">
          <nav className="ui-nav-shell flex items-center gap-2 rounded-full px-2.5 py-2">
            {groups.map((group) => {
              const isActive = group.id === activeGroup.id

              return (
                <Link key={group.id} href={group.defaultHref}>
                  <div
                    className={cn(
                      "ui-nav-item flex items-center gap-2.5 rounded-full px-5 py-2.5 text-[0.94rem] font-medium tracking-[0.02em]",
                      isActive && "ui-nav-item-active",
                    )}
                  >
                    <span
                      className={cn(
                        "inline-flex h-6.5 w-6.5 items-center justify-center rounded-full transition-colors",
                        isActive
                          ? "bg-[rgba(var(--rgb-ochre),0.14)] text-[rgb(var(--rgb-ochre))]"
                          : toneClasses[group.tone].idle,
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
            className="flex h-10 w-10 items-center justify-center rounded-2xl border border-transparent text-foreground/48 transition-[background-color,border-color,color] duration-300 hover:border-black/[0.05] hover:bg-[rgba(250,246,239,0.75)] hover:text-foreground/78"
            aria-label="通知"
          >
            <Bell className="h-4 w-4" />
          </button>

          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="ui-nav-shell flex h-10 items-center gap-2.5 rounded-full px-4 text-foreground/78 transition-[background-color,border-color,color,box-shadow] duration-300 hover:bg-[rgba(250,246,239,0.92)] hover:text-foreground/92"
                  aria-label={`当前账户 ${user.username}`}
                  title={`已登录：${user.username}`}
                >
                  <User className="h-4 w-4" />
                  <span className="hidden text-[0.84rem] font-medium sm:inline">{user.username}</span>
                  <ChevronDown className="hidden h-3.5 w-3.5 text-foreground/42 sm:inline" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-56 rounded-[24px] border border-black/[0.08] bg-[rgba(247,243,237,0.98)] p-1.5 text-foreground shadow-[0_22px_52px_rgba(41,33,25,0.14)]"
              >
                <DropdownMenuLabel className="px-3 py-3">
                  <div className="eyebrow text-foreground/64">当前账户</div>
                  <div className="mt-2 text-sm font-semibold text-foreground/92">{user.username}</div>
                  <div className="mt-1 text-[0.86rem] text-foreground/68">
                    {isAdmin ? "管理员账户" : "已登录用户"}
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-black/[0.06]" />
                <DropdownMenuItem
                  onClick={logout}
                  className="cursor-pointer rounded-2xl px-3 py-2.5 text-tone-cinnabar focus:bg-[rgba(var(--rgb-cinnabar),0.10)] focus:text-tone-cinnabar"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Link href="/login">
              <button
                className="flex h-10 w-10 items-center justify-center rounded-2xl border border-transparent text-foreground/48 transition-[background-color,border-color,color] duration-300 hover:border-black/[0.05] hover:bg-[rgba(250,246,239,0.75)] hover:text-foreground/78"
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
                        "rounded-2xl border px-3 py-2.5 text-center text-[0.85rem] font-medium transition-[background-color,border-color,color,box-shadow] duration-300",
                        isActive
                          ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[linear-gradient(180deg,rgba(var(--rgb-ochre),0.11),rgba(var(--rgb-xuan),0.8))] text-foreground shadow-[0_8px_18px_rgba(142,115,77,0.05)]"
                          : "border-black/[0.05] bg-[rgba(250,246,239,0.66)] text-foreground/70 hover:bg-[rgba(var(--rgb-ochre),0.05)]",
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

              <div className="rounded-[26px] border border-black/[0.06] bg-[rgba(250,246,239,0.70)] p-3">
                <div className="px-1 pb-3">
                  <div className="eyebrow text-foreground/68">当前分组</div>
                  <div className="mt-2 text-[1.06rem] font-semibold tracking-[-0.02em] text-foreground/92">
                    {activeGroup.name}
                  </div>
                  <div className="mt-1 text-[0.9rem] leading-7 text-foreground/74">
                    {activeGroup.description}
                  </div>
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
                          "block rounded-2xl px-3 py-2.5 transition-[background-color,border-color,color,box-shadow] duration-300",
                          isActive
                            ? "border border-[rgba(var(--rgb-ochre),0.16)] bg-[linear-gradient(180deg,rgba(var(--rgb-ochre),0.10),rgba(var(--rgb-xuan),0.76))] text-foreground shadow-[0_8px_18px_rgba(142,115,77,0.04)]"
                            : "text-foreground/68 hover:bg-[rgba(var(--rgb-ochre),0.05)] hover:text-foreground/88",
                        )}
                      >
                        <div className="font-medium">{item.name}</div>
                        <div className={cn("mt-1 text-[0.88rem] leading-7", isActive ? "text-foreground/72" : "text-foreground/64")}>
                          {item.description}
                        </div>
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
