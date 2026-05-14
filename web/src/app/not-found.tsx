import Link from "next/link"
import { Compass } from "lucide-react"

export default function NotFound() {
  return (
    <div className="glass-card mx-auto flex min-h-[420px] max-w-lg flex-col items-center justify-center rounded-[30px] px-8 text-center">
      <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgba(var(--rgb-ochre),0.1)] text-[rgb(var(--rgb-ochre))]">
        <Compass className="h-7 w-7" />
      </div>
      <h1 className="mt-6 font-serif text-[clamp(2rem,1.8rem+0.8vw,2.5rem)] font-semibold tracking-[-0.03em] text-foreground/92">
        404
      </h1>
      <p className="mt-3 text-lg font-medium text-foreground/80">页面未找到</p>
      <p className="mt-2 max-w-sm text-sm leading-7 text-muted-foreground">
        你访问的页面可能已被移动、删除，或地址输入有误。
      </p>
      <Link
        href="/"
        className="mt-8 inline-flex items-center gap-2 rounded-2xl border border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.08)] px-5 py-2.5 text-sm font-medium text-[rgb(var(--rgb-ochre))] transition-all hover:bg-[rgba(var(--rgb-ochre),0.14)]"
      >
        <Compass className="h-4 w-4" />
        返回首页
      </Link>
    </div>
  )
}
