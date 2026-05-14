import { Suspense } from "react"

import { BacktestCenterWorkspace } from "@/components/backtest/backtest-center-workspace"

export default function BacktestPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">正在加载回测中心…</div>}>
      <BacktestCenterWorkspace />
    </Suspense>
  )
}
