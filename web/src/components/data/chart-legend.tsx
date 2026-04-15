"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

export type ChartLegendItem = {
  key: string
  label: React.ReactNode
  color: string
  meta?: React.ReactNode
  active?: boolean
  onToggle?: () => void
}

type ChartLegendProps = {
  items: ChartLegendItem[]
  className?: string
}

export function ChartLegend({ items, className }: ChartLegendProps) {
  if (items.length === 0) return null

  return (
    <div className={cn("chart-legend-shell", className)}>
      {items.map((item) => {
        const active = item.active ?? true
        const interactive = Boolean(item.onToggle)
        const content = (
          <>
            <span className="chart-legend-dot" style={{ backgroundColor: item.color }} />
            <span>{item.label}</span>
            {item.meta ? <span className="chart-legend-meta">{item.meta}</span> : null}
          </>
        )

        if (interactive) {
          return (
            <button
              key={item.key}
              type="button"
              data-active={active}
              data-interactive="true"
              onClick={item.onToggle}
              className="chart-legend-item"
            >
              {content}
            </button>
          )
        }

        return (
          <div key={item.key} data-active={active} data-interactive="false" className="chart-legend-item">
            {content}
          </div>
        )
      })}
    </div>
  )
}
