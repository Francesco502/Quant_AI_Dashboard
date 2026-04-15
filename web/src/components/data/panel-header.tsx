import { type ReactNode } from "react"

import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { HelpTooltip } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export function PanelHeader({
  title,
  description,
  hint,
  meta,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  hint?: string
  meta?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="space-y-1">
        <div className="flex items-center gap-1">
          {typeof title === "string" ? <CardTitle>{title}</CardTitle> : title}
          {hint ? <HelpTooltip content={hint} /> : null}
        </div>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </div>
      {meta ? <div className="flex shrink-0 items-center gap-2">{meta}</div> : null}
    </div>
  )
}

export function ChartPanel({
  title,
  description,
  hint,
  meta,
  className,
  bodyClassName,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  hint?: string
  meta?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
}) {
  return (
    <GlassCard className={cn("space-y-4 p-5", className)}>
      <PanelHeader title={title} description={description} hint={hint} meta={meta} />
      <div className={bodyClassName}>{children}</div>
    </GlassCard>
  )
}
