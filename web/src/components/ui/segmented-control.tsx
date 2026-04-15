"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

export type SegmentedControlOption<T extends string = string> = {
  value: T
  label: React.ReactNode
  description?: React.ReactNode
  icon?: React.ReactNode
  badge?: React.ReactNode
  disabled?: boolean
  className?: string
}

type SegmentedControlProps<T extends string = string> = {
  value: T
  onValueChange: (value: T) => void
  options: Array<SegmentedControlOption<T>>
  className?: string
  itemClassName?: string
  fullWidth?: boolean
  orientation?: "horizontal" | "vertical"
  ariaLabel?: string
}

export function SegmentedControl<T extends string = string>({
  value,
  onValueChange,
  options,
  className,
  itemClassName,
  fullWidth = false,
  orientation = "horizontal",
  ariaLabel,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        "segmented-shell",
        fullWidth && "flex w-full",
        orientation === "vertical" && "flex-col items-stretch",
        className,
      )}
    >
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={option.disabled}
            data-active={active}
            data-orientation={option.description ? "vertical" : "horizontal"}
            onClick={() => onValueChange(option.value)}
            className={cn(
              "segmented-item text-left disabled:pointer-events-none disabled:opacity-40",
              fullWidth && "flex-1",
              option.description && "min-h-[3.25rem] flex-col items-start",
              itemClassName,
              option.className,
            )}
          >
            <div className="flex items-center gap-2">
              {option.icon}
              <span className="segmented-item-title">{option.label}</span>
              {option.badge}
            </div>
            {option.description ? <div className="segmented-item-description">{option.description}</div> : null}
          </button>
        )
      })}
    </div>
  )
}
