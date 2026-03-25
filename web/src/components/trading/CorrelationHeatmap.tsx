"use client"

import { CardTitle, GlassCard } from "@/components/ui/card"

interface CorrelationHeatmapProps {
  tickers: string[]
  correlations?: number[][]
}

function getColor(value: number) {
  if (value < 0) {
    const intensity = Math.abs(value)
    return `rgba(77, 115, 88, ${Math.min(0.85, intensity * 0.7 + 0.18)})`
  }
  return `rgba(182, 69, 60, ${Math.min(0.85, value * 0.7 + 0.18)})`
}

export function CorrelationHeatmap({ tickers, correlations }: CorrelationHeatmapProps) {
  const hasEnoughAssets = tickers.length >= 2
  const hasRealCorrelations =
    Array.isArray(correlations) &&
    correlations.length === tickers.length &&
    correlations.every((row) => Array.isArray(row) && row.length === tickers.length)

  if (!hasEnoughAssets) {
    return (
      <GlassCard className="p-4">
        <CardTitle className="text-sm">相关性热力图</CardTitle>
        <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
          至少需要 2 个持仓，才能计算资产之间的相关性。
        </div>
      </GlassCard>
    )
  }

  if (!hasRealCorrelations || !correlations) {
    return (
      <GlassCard className="p-4">
        <CardTitle className="text-sm">相关性热力图</CardTitle>
        <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-center">
          <p className="text-sm font-medium text-foreground">暂无真实相关性分析结果</p>
          <p className="max-w-md text-xs leading-6 text-muted-foreground">
            当前后端尚未返回完整的收益序列相关性矩阵，因此这里不再使用占位图。待真实相关性数据可用后，系统会自动展示热力图。
          </p>
        </div>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="p-4">
      <CardTitle className="mb-4 text-sm">相关性热力图</CardTitle>
      <div className="overflow-x-auto">
        <div className="inline-block">
          <div className="flex">
            <div className="w-16" />
            {tickers.map((ticker) => (
              <div key={ticker} className="flex h-12 w-12 items-center justify-center text-xs font-medium">
                {ticker.slice(0, 4)}
              </div>
            ))}
          </div>

          {tickers.map((ticker, i) => (
            <div key={ticker} className="flex">
              <div className="flex h-12 w-16 items-center justify-center text-xs font-medium">
                {ticker.slice(0, 4)}
              </div>
              {tickers.map((peer, j) => {
                const value = correlations[i]?.[j] ?? 0
                return (
                  <div
                    key={`${ticker}-${peer}`}
                    className="flex h-12 w-12 items-center justify-center text-xs"
                    style={{ backgroundColor: getColor(value) }}
                    title={`${ticker} vs ${peer}: ${value.toFixed(2)}`}
                  >
                    <span className={Math.abs(value) > 0.45 ? "text-white" : "text-foreground"}>{value.toFixed(2)}</span>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-center gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded" style={{ backgroundColor: "rgba(77, 115, 88, 0.8)" }} />
          <span>负相关</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[rgba(175,165,150,0.55)]" />
          <span>低相关</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded" style={{ backgroundColor: "rgba(182, 69, 60, 0.8)" }} />
          <span>正相关</span>
        </div>
      </div>
    </GlassCard>
  )
}
