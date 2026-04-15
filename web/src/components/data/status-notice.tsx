import { type ReactNode } from "react"
import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react"

import { cn } from "@/lib/utils"

type NoticeTone = "success" | "error" | "info" | "warning"

const NOTICE_ICONS = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
  warning: TriangleAlert,
} as const

export function StatusNotice({
  tone = "info",
  title,
  children,
  compact = false,
  className,
}: {
  tone?: NoticeTone
  title?: ReactNode
  children: ReactNode
  compact?: boolean
  className?: string
}) {
  const Icon = NOTICE_ICONS[tone]

  return (
    <div className={cn("status-notice", compact && "status-notice-compact", className)} data-tone={tone}>
      <Icon className="status-notice-icon h-4.5 w-4.5" />
      <div className="min-w-0 space-y-1">
        {title ? <div className="status-notice-title">{title}</div> : null}
        <div className="status-notice-body">{children}</div>
      </div>
    </div>
  )
}
