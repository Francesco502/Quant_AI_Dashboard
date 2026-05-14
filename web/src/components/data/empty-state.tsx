import { type ReactNode } from "react"

import { cn } from "@/lib/utils"

export function EmptyState({
  title,
  description,
  action,
  compact = false,
  className,
}: {
  title?: ReactNode
  description: ReactNode
  action?: ReactNode
  compact?: boolean
  className?: string
}) {
  return (
    <div role="status" className={cn("data-empty text-muted-foreground", compact && "data-empty-compact", className)}>
      {title ? <div className="mb-2 text-sm font-medium text-foreground/84">{title}</div> : null}
      <div className="text-sm leading-7">{description}</div>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  )
}
