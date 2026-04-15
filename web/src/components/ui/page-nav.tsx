"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

export type PageNavItem = {
  name: string
  href: string
}

export function PageNav({ items, className }: { items: PageNavItem[], className?: string }) {
  const pathname = usePathname()

  return (
    <nav
      className={cn(
        "ui-nav-shell inline-flex h-auto items-center justify-start gap-1.5 rounded-[24px] p-1.5",
        "w-full overflow-x-auto no-scrollbar sm:w-auto",
        className
      )}
    >
      {items.map((item) => {
        const isActive = pathname === item.href
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "ui-nav-item inline-flex items-center justify-center whitespace-nowrap rounded-[18px] border px-4.5 py-2.5 text-[13px] font-medium tracking-[0.03em] transition-[background-color,border-color,color,box-shadow,transform] duration-300",
              isActive
                ? "ui-nav-item-active border-[rgba(var(--rgb-ochre),0.18)] bg-[linear-gradient(180deg,rgba(var(--rgb-ochre),0.11),rgba(var(--rgb-xuan),0.78))] text-foreground shadow-[0_10px_22px_rgba(41,33,25,0.05),inset_0_-2px_0_rgba(var(--rgb-celadon),0.6)]"
                : "text-foreground/64 hover:bg-[rgba(var(--rgb-ochre),0.05)] hover:text-foreground/90"
            )}
          >
            {item.name}
          </Link>
        )
      })}
    </nav>
  )
}
