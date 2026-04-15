import { type ReactNode } from "react"

import { cn } from "@/lib/utils"

export function TableSurface({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cn("data-table-shell", className)}>{children}</div>
}
