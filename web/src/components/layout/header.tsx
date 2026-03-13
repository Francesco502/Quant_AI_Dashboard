"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Activity,
  BarChart3,
  Bell,
  History,
  Layers,
  LayoutDashboard,
  LineChart,
  Menu,
  PieChart,
  Settings,
  Target,
  User,
  X,
} from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { useState } from "react"

import { cn } from "@/lib/utils"

const navigation = [
  { name: "市场概览", href: "/", icon: LayoutDashboard },
  { name: "AI分析", href: "/market", icon: LineChart },
  { name: "决策仪表盘", href: "/dashboard-llm", icon: Target },
  { name: "大盘复盘", href: "/market-review", icon: BarChart3 },
  { name: "交易中心", href: "/trading", icon: Activity },
  { name: "资产池", href: "/portfolio", icon: PieChart },
  { name: "策略回测", href: "/backtest", icon: History },
  { name: "量化策略", href: "/strategies", icon: Layers },
  { name: "系统设置", href: "/settings", icon: Settings },
]

export function Header() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full",
        "h-14 flex items-center px-5 md:px-6",
        "glass",
        "border-b border-black/[0.04] dark:border-white/[0.06]",
        "transition-all duration-300"
      )}
    >
      <div className="lg:hidden mr-3">
        <button
          onClick={() => setMobileMenuOpen((open) => !open)}
          className={cn(
            "flex items-center justify-center w-8 h-8 rounded-lg",
            "text-foreground/60 hover:text-foreground",
            "hover:bg-black/[0.04] dark:hover:bg-white/[0.06]",
            "transition-colors duration-150"
          )}
        >
          {mobileMenuOpen ? <X className="h-[18px] w-[18px]" /> : <Menu className="h-[18px] w-[18px]" />}
        </button>
      </div>

      <Link href="/" className="flex items-center gap-1.5 min-w-[120px] md:min-w-[160px] group">
        <div className="w-6 h-6 rounded-md bg-foreground/90 dark:bg-foreground/80 flex items-center justify-center group-hover:bg-foreground transition-colors duration-200">
          <span className="text-background text-[10px] font-bold tracking-tighter">Q</span>
        </div>
        <span className="text-[15px] font-semibold tracking-[-0.02em] text-foreground/90">
          Quant<span className="font-light text-foreground/50 ml-0.5">AI</span>
        </span>
      </Link>

      <nav className="hidden lg:flex items-center gap-0.5 absolute left-1/2 -translate-x-1/2">
        {navigation.map((item) => {
          const isActive = pathname === item.href

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "relative flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium",
                "transition-colors duration-200",
                isActive ? "text-foreground" : "text-foreground/45 hover:text-foreground/70"
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="nav-pill"
                  className={cn(
                    "absolute inset-0 rounded-lg",
                    "bg-black/[0.05] dark:bg-white/[0.08]",
                    "border border-black/[0.04] dark:border-white/[0.06]"
                  )}
                  transition={{ type: "spring", bounce: 0.15, duration: 0.5 }}
                />
              )}
              <item.icon className="h-3.5 w-3.5 relative z-10" />
              <span className="relative z-10 text-[13px] font-medium tracking-tight">{item.name}</span>
            </Link>
          )
        })}
      </nav>

      <div className="flex-1 flex items-center justify-end gap-1">
        <button
          className={cn(
            "flex items-center justify-center w-8 h-8 rounded-lg",
            "text-foreground/40 hover:text-foreground/70",
            "hover:bg-black/[0.04] dark:hover:bg-white/[0.06]",
            "transition-colors duration-150"
          )}
        >
          <Bell className="h-[15px] w-[15px]" />
          <span className="sr-only">通知</span>
        </button>
        <Link href="/login">
          <button
            className={cn(
              "flex items-center justify-center w-8 h-8 rounded-lg",
              "text-foreground/40 hover:text-foreground/70",
              "hover:bg-black/[0.04] dark:hover:bg-white/[0.06]",
              "transition-colors duration-150"
            )}
          >
            <User className="h-[15px] w-[15px]" />
            <span className="sr-only">用户菜单</span>
          </button>
        </Link>
      </div>

      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={cn("absolute top-14 left-0 right-0", "glass-dropdown", "border-t-0 rounded-b-2xl", "p-3 lg:hidden")}
          >
            <nav className="flex flex-col gap-0.5">
              {navigation.map((item) => {
                const isActive = pathname === item.href

                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium",
                      "transition-all duration-150",
                      isActive
                        ? "bg-black/[0.05] dark:bg-white/[0.08] text-foreground"
                        : "text-foreground/50 hover:text-foreground/80 hover:bg-black/[0.03] dark:hover:bg-white/[0.04]"
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    <span className="text-[15px] font-medium tracking-tight">{item.name}</span>
                  </Link>
                )
              })}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
