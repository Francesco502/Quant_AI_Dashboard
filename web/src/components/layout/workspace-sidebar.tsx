"use client"

import Link from "next/link"
import { motion } from "framer-motion"

import { cn } from "@/lib/utils"
import type { WorkspaceGroup } from "@/lib/workspace-nav"
import { isWorkspaceItemActive } from "@/lib/workspace-nav"

type WorkspaceSidebarProps = {
  group: WorkspaceGroup
  pathname: string
}

export function WorkspaceSidebar({ group, pathname }: WorkspaceSidebarProps) {
  const toneClasses = {
    indigo: "bg-[rgba(111,124,142,0.12)] text-[#5E6876]",
    celadon: "bg-[rgba(77,115,88,0.12)] text-[#45674F]",
    plum: "bg-[rgba(122,105,115,0.12)] text-[#6D5C66]",
    ochre: "bg-[rgba(176,142,97,0.14)] text-[#8C724C]",
    ink: "bg-[rgba(77,71,66,0.12)] text-[#4D4742]",
  } as const

  return (
    <aside className="hidden w-[272px] shrink-0 xl:block">
      <div className="sticky top-[88px] rounded-[32px] bg-white/30 backdrop-blur-xl border border-white/60 shadow-[0_4px_24px_rgba(0,0,0,0.02)] px-6 py-8">
        <div className="border-b border-black/[0.04] px-2 pb-6">
          <div className="text-[11px] tracking-[0.22em] text-foreground/34">当前分组</div>
          <div className="mt-3 flex items-center gap-3">
            <div className={cn("rounded-[18px] border border-black/[0.05] p-2.5", toneClasses[group.tone])}>
              <group.icon className="h-4.5 w-4.5" />
            </div>
            <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-foreground/92">{group.name}</h2>
          </div>
          <p className="mt-2 text-[12px] leading-6 text-foreground/54">{group.description}</p>
        </div>

        <nav className="mt-4 space-y-1.5">
          {group.items.map((item) => {
            const isActive = isWorkspaceItemActive(pathname, item.href)

            return (
              <Link key={item.href} href={item.href} className="block">
                <motion.div
                  whileHover={{ y: -1 }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className={cn(
                    "group relative overflow-hidden rounded-[24px] border px-5 py-4 transition-all duration-300",
                    isActive
                      ? "border-white/60 bg-white/70 backdrop-blur-md text-foreground shadow-[0_8px_24px_rgba(142,115,77,0.04)]"
                      : "border-transparent text-foreground/60 hover:border-white/40 hover:bg-white/40 hover:text-foreground/90",
                  )}
                >
                  {isActive ? (
                    <div className="absolute inset-y-3 left-0 w-[3px] rounded-full bg-[#8E734D]" />
                  ) : null}

                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 rounded-2xl border p-2 transition-colors",
                        isActive
                          ? "border-[#8E734D]/14 bg-[#8E734D]/10 text-[#8E734D]"
                          : "border-black/[0.05] bg-black/[0.03] text-foreground/42 group-hover:text-foreground/64",
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium">{item.name}</div>
                      <div className="mt-1 text-[12px] leading-5 text-foreground/46">
                        {item.description}
                      </div>
                    </div>
                  </div>
                </motion.div>
              </Link>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
