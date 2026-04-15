"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

export type FilterBarOption<T extends string = string> = {
  value: T
  label: React.ReactNode
  icon?: React.ReactNode
  accent?: string
  meta?: React.ReactNode
  disabled?: boolean
}

type FilterBarProps<T extends string = string> = {
  label?: React.ReactNode
  icon?: React.ReactNode
  value: T
  onValueChange: (value: T) => void
  options: Array<FilterBarOption<T>>
  className?: string
  trackClassName?: string
}

export function FilterBar<T extends string = string>({
  label,
  icon,
  value,
  onValueChange,
  options,
  className,
  trackClassName,
}: FilterBarProps<T>) {
  return (
    <div className={cn("filter-bar-shell", className)}>
      {label ? (
        <div className="filter-bar-label flex items-center gap-2">
          {icon}
          <span>{label}</span>
        </div>
      ) : null}
      <div className={cn("filter-bar-track", trackClassName)}>
        {options.map((option) => {
          const active = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              data-active={active}
              disabled={option.disabled}
              onClick={() => onValueChange(option.value)}
              className="filter-chip disabled:pointer-events-none disabled:opacity-40"
            >
              {option.accent ? <span className="filter-chip-dot" style={{ backgroundColor: option.accent }} /> : option.icon}
              <span>{option.label}</span>
              {option.meta ? <span className="chart-legend-meta">{option.meta}</span> : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}
