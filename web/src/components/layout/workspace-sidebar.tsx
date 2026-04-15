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
    indigo: "bg-[rgba(var(--rgb-indigo),0.14)] text-[rgb(var(--rgb-indigo))]",
    celadon: "bg-[rgba(var(--rgb-celadon),0.14)] text-[rgb(var(--rgb-celadon))]",
    plum: "bg-[rgba(var(--rgb-plum),0.14)] text-[rgb(var(--rgb-plum))]",
    ochre: "bg-[rgba(var(--rgb-ochre),0.16)] text-[rgb(var(--rgb-ochre))]",
    ink: "bg-[rgba(var(--rgb-ink),0.12)] text-[rgba(var(--rgb-ink),0.88)]",
  } as const

  return (
    <aside className="hidden w-[244px] shrink-0 xl:block">
      <div className="sticky top-[92px] rounded-[30px] border border-white/60 bg-[rgba(250,246,239,0.34)] px-5 py-6 shadow-[0_8px_26px_rgba(41,33,25,0.04)] backdrop-blur-xl">
        <div className="flex items-center gap-3 px-1 pb-4">
          <div className={cn("rounded-[18px] border border-black/[0.05] p-2.5", toneClasses[group.tone])}>
            <group.icon className="h-4.5 w-4.5" />
          </div>
          <div className="min-w-0">
            <div className="eyebrow text-foreground/66">当前分组</div>
            <h2 className="mt-1 truncate text-[1.26rem] font-semibold tracking-[-0.03em] text-foreground/94">
              {group.name}
            </h2>
          </div>
        </div>

        <div className="px-1 pb-3 text-[0.92rem] leading-7 text-foreground/74">{group.description}</div>

        <nav className="mt-2 space-y-1.5">
          {group.items.map((item) => {
            const isActive = isWorkspaceItemActive(pathname, item.href)

            return (
              <Link key={item.href} href={item.href} className="block">
                <motion.div
                  whileHover={{ y: -1 }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className={cn(
                    "group relative overflow-hidden rounded-[22px] border px-4 py-3 transition-[background-color,border-color,color,box-shadow,transform] duration-300",
                    isActive
                      ? "border-[rgba(var(--rgb-ochre),0.22)] bg-[linear-gradient(180deg,rgba(var(--rgb-ochre),0.12),rgba(var(--rgb-xuan),0.78))] text-foreground shadow-[0_10px_22px_rgba(142,115,77,0.08)]"
                      : "border-transparent text-foreground/70 hover:border-[rgba(var(--rgb-ochre),0.12)] hover:bg-[rgba(var(--rgb-ochre),0.05)] hover:text-foreground/92",
                  )}
                >
                  {isActive ? (
                    <div className="absolute inset-y-3 left-0 w-[3px] rounded-full bg-[rgb(var(--rgb-ochre))]" />
                  ) : null}

                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 rounded-2xl border p-2 transition-colors",
                        isActive
                          ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.12)] text-[rgb(var(--rgb-ochre))]"
                          : "border-[rgba(var(--rgb-ink),0.06)] bg-[rgba(var(--rgb-ink),0.04)] text-foreground/54 group-hover:border-[rgba(var(--rgb-ochre),0.1)] group-hover:bg-[rgba(var(--rgb-ochre),0.06)] group-hover:text-foreground/72",
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[0.94rem] font-medium leading-7 text-foreground/90">{item.name}</div>
                      <div
                        className={cn(
                          "mt-1 line-clamp-2 text-[0.86rem] leading-7",
                          isActive ? "text-foreground/74" : "text-foreground/64",
                        )}
                      >
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
