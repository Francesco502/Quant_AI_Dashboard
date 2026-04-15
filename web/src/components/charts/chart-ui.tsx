"use client"

import { type CSSProperties } from "react"

import { EmptyState } from "@/components/data/empty-state"
import { cn } from "@/lib/utils"

export const SONG_CHART_TOOLTIP_STYLE: CSSProperties = {
  borderRadius: 16,
  border: "1px solid rgba(77,71,66,0.08)",
  background: "rgba(255,255,255,0.92)",
  boxShadow: "0 14px 30px rgba(41,33,25,0.08)",
  backdropFilter: "blur(18px)",
  fontSize: 12,
}

export function ChartEmptyState({
  title = "暂无图表数据",
  description,
  className,
}: {
  title?: string
  description: string
  className?: string
}) {
  return (
    <div className={cn("flex h-full min-h-[220px] items-center justify-center", className)}>
      <EmptyState
        compact
        className="w-full max-w-lg border border-black/[0.05] bg-white/56"
        title={title}
        description={description}
      />
    </div>
  )
}
