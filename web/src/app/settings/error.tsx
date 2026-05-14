"use client"

import { useEffect } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"

export default function SettingsError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Route /settings error:", error)
  }, [error])

  return (
    <div className="glass-card flex min-h-[320px] w-full flex-col items-center justify-center rounded-[30px] px-8 text-center" role="alert">
      <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-[rgba(var(--rgb-cinnabar),0.1)] text-[rgb(var(--rgb-cinnabar))]">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h2 className="mt-6 text-lg font-semibold text-foreground/92">页面加载失败</h2>
      <p className="mt-2 max-w-md text-sm leading-7 text-muted-foreground">
        {error.message || "系统设置页面渲染时遇到错误。"}
      </p>
      <button onClick={reset} className="mt-6 inline-flex items-center gap-2 rounded-2xl border border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.08)] px-5 py-2.5 text-sm font-medium text-[rgb(var(--rgb-ochre))] transition-all hover:bg-[rgba(var(--rgb-ochre),0.14)]">
        <RefreshCw className="h-4 w-4" />
        重新加载
      </button>
    </div>
  )
}
