"use client"

import { useMemo } from "react"
import { GlassCard, CardTitle } from "@/components/ui/card"

interface CorrelationHeatmapProps {
  tickers: string[]
  correlations?: number[][]
}

export function CorrelationHeatmap({ tickers, correlations }: CorrelationHeatmapProps) {
  const hasRealCorrelations =
    Array.isArray(correlations) &&
    correlations.length === tickers.length &&
    correlations.every((row) => Array.isArray(row) && row.length === tickers.length)

  const data = useMemo(() => {
    if (hasRealCorrelations && correlations) {
      return correlations
    }
    // No fabricated data: use neutral matrix until real correlation is provided.
    const matrix: number[][] = []
    for (let i = 0; i < tickers.length; i++) {
      matrix[i] = []
      for (let j = 0; j < tickers.length; j++) {
        matrix[i][j] = i === j ? 1 : 0
      }
    }
    return matrix
  }, [tickers, correlations, hasRealCorrelations])

  const getColor = (value: number) => {
    // Blue for negative, white for 0, red for positive
    if (value < 0) {
      const intensity = Math.abs(value)
      return `rgba(59, 130, 246, ${intensity * 0.8 + 0.2})`
    } else {
      return `rgba(239, 68, 68, ${value * 0.8 + 0.2})`
    }
  }

  if (tickers.length < 2) {
    return (
      <GlassCard className="p-4">
        <CardTitle className="text-sm">相关性热力图</CardTitle>
        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
          需要至少2个持仓才能显示相关性
        </div>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="p-4">
      <CardTitle className="text-sm mb-4">相关性热力图</CardTitle>
      <div className="overflow-x-auto">
        <div className="inline-block">
          {/* Header row */}
          <div className="flex">
            <div className="w-16" /> {/* Corner cell */}
            {tickers.map((ticker) => (
              <div
                key={ticker}
                className="w-12 h-12 flex items-center justify-center text-xs font-medium"
              >
                {ticker.slice(0, 4)}
              </div>
            ))}
          </div>

          {/* Data rows */}
          {tickers.map((ticker, i) => (
            <div key={ticker} className="flex">
              <div className="w-16 h-12 flex items-center justify-center text-xs font-medium">
                {ticker.slice(0, 4)}
              </div>
              {tickers.map((_, j) => (
                <div
                  key={`${i}-${j}`}
                  className="w-12 h-12 flex items-center justify-center text-xs"
                  style={{ backgroundColor: getColor(data[i]?.[j] || 0) }}
                  title={`${ticker} vs ${tickers[j]}: ${(data[i]?.[j] || 0).toFixed(2)}`}
                >
                  <span className={Math.abs(data[i]?.[j] || 0) > 0.5 ? "text-white" : "text-foreground"}>
                    {(data[i]?.[j] || 0).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {!hasRealCorrelations && (
        <div className="mt-3 text-xs text-muted-foreground">
          当前为中性占位矩阵，需接入真实收益序列后才能展示相关性。
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: "rgba(59, 130, 246, 0.8)" }} />
          <span>负相关</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-gray-200" />
          <span>无相关</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: "rgba(239, 68, 68, 0.8)" }} />
          <span>正相关</span>
        </div>
      </div>
    </GlassCard>
  )
}
