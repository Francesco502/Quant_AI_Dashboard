import { type ReactNode } from "react"

import { HelpTooltip } from "@/components/ui/tooltip"
import { SONG_COLORS } from "@/lib/chart-theme"
import { cn } from "@/lib/utils"

type MetricTone = "default" | "positive" | "negative" | "accent"
type MetricSurface = "default" | "muted"

function resolveToneColor(tone: MetricTone, accentColor?: string) {
  if (accentColor) return accentColor
  if (tone === "positive") return SONG_COLORS.positive
  if (tone === "negative") return SONG_COLORS.negative
  if (tone === "accent") return SONG_COLORS.indigo
  return undefined
}

export function MetricCard({
  label,
  value,
  secondary,
  detail,
  hint,
  help,
  icon,
  tone = "default",
  accentColor,
  accent,
  compact = false,
  surface = "default",
  className,
  valueClassName,
  secondaryClassName,
}: {
  label: ReactNode
  value: ReactNode
  secondary?: ReactNode
  detail?: ReactNode
  hint?: string
  help?: string
  icon?: ReactNode
  tone?: MetricTone
  accentColor?: string
  accent?: string
  compact?: boolean
  surface?: MetricSurface
  className?: string
  valueClassName?: string
  secondaryClassName?: string
}) {
  const resolvedSecondary = secondary ?? detail
  const resolvedColor = resolveToneColor(tone, accentColor ?? accent)

  return (
    <div
      className={cn(
        surface === "muted" ? "data-panel-muted" : "data-panel",
        compact ? "data-metric-card-compact" : "data-metric-card",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1 text-foreground/78">
          <span className="data-metric-label">{label}</span>
          {hint || help ? <HelpTooltip content={hint ?? help ?? ""} /> : null}
        </div>
        {icon ? <div className="shrink-0 text-foreground/55">{icon}</div> : null}
      </div>
      <div
        className={cn(compact ? "mt-2 text-[1rem] font-medium tracking-[-0.02em]" : "metric-value mt-2", valueClassName)}
        style={resolvedColor ? { color: resolvedColor } : undefined}
      >
        {value}
      </div>
      {resolvedSecondary ? (
        <div className={cn("data-metric-secondary mt-1", secondaryClassName)}>{resolvedSecondary}</div>
      ) : null}
    </div>
  )
}
