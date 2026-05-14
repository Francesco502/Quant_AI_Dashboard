"use client"

import { useEffect } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import Link from "next/link"

export default function LoginError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Route /login error:", error)
  }, [error])

  return (
    <div className="glass-card mx-auto flex min-h-[320px] max-w-md flex-col items-center justify-center rounded-[30px] px-8 text-center" role="alert">
      <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-[rgba(var(--rgb-cinnabar),0.1)] text-[rgb(var(--rgb-cinnabar))]">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h2 className="mt-6 text-lg font-semibold text-foreground/92">页面加载失败</h2>
      <p className="mt-2 max-w-md text-sm leading-7 text-muted-foreground">
        {error.message || "登录页面渲染时遇到错误。"}
      </p>
      <div className="mt-6 flex items-center gap-3">
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 rounded-2xl border border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.08)] px-5 py-2.5 text-sm font-medium text-[rgb(var(--rgb-ochre))] transition-all hover:bg-[rgba(var(--rgb-ochre),0.14)]"
        >
          <RefreshCw className="h-4 w-4" />
          重新加载
        </button>
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
          返回首页
        </Link>
      </div>
    </div>
  )
}
