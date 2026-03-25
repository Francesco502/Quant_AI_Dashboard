"use client"

import { TrendingDown, TrendingUp } from "lucide-react"
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { CardTitle, GlassCard } from "@/components/ui/card"

interface ReturnContribution {
  ticker: string
  return_pct: number
  contribution_pct: number
  weight: number
}

interface ReturnContributionChartProps {
  holdings: { ticker: string; shares: number; costPrice?: number }[]
  contributions?: ReturnContribution[]
}

export function ReturnContributionChart({ holdings, contributions }: ReturnContributionChartProps) {
  const hasHoldings = holdings.some((item) => item.ticker.trim() && item.shares > 0)
  const hasRealContributions = Boolean(contributions && contributions.length > 0)
  const chartData = hasRealContributions ? [...(contributions ?? [])].sort((a, b) => b.contribution_pct - a.contribution_pct) : []

  const totalPositive = chartData.filter((item) => item.contribution_pct > 0).reduce((sum, item) => sum + item.contribution_pct, 0)
  const totalNegative = chartData.filter((item) => item.contribution_pct < 0).reduce((sum, item) => sum + item.contribution_pct, 0)

  if (!hasHoldings) {
    return (
      <GlassCard className="p-4">
        <CardTitle className="mb-2 text-sm">收益贡献</CardTitle>
        <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
          先录入有效持仓，再查看各资产对组合收益的贡献。
        </div>
      </GlassCard>
    )
  }

  if (!hasRealContributions) {
    return (
      <GlassCard className="p-4">
        <CardTitle className="mb-2 text-sm">收益贡献</CardTitle>
        <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
          <p className="text-sm font-medium text-foreground">暂无真实收益贡献数据</p>
          <p className="max-w-md text-xs leading-6 text-muted-foreground">
            当前分析结果没有返回可用的收益归因明细，因此这里不再使用占位图。待收益归因链路补齐后，会展示各资产的贡献比例与方向。
          </p>
        </div>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="p-4">
      <CardTitle className="mb-2 text-sm">收益贡献</CardTitle>

      <div className="mb-4 flex gap-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-[#B6453C]" />
          <span className="text-xs text-muted-foreground">正贡献</span>
          <span className="text-sm font-medium text-[#B6453C]">+{totalPositive.toFixed(2)}%</span>
        </div>
        <div className="flex items-center gap-2">
          <TrendingDown className="h-4 w-4 text-[#4D7358]" />
          <span className="text-xs text-muted-foreground">负贡献</span>
          <span className="text-sm font-medium text-[#4D7358]">{totalNegative.toFixed(2)}%</span>
        </div>
      </div>

      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tickFormatter={(value: number) => `${value.toFixed(1)}%`} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="ticker" tick={{ fontSize: 11 }} width={58} />
            <Tooltip
              formatter={(value) => {
                const numeric = typeof value === "number" ? value : Number(value ?? 0)
                const safeValue = Number.isFinite(numeric) ? numeric : 0
                return [`${safeValue.toFixed(2)}%`, "贡献度"]
              }}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.contribution_pct >= 0 ? "#B6453C" : "#4D7358"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex items-center justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#B6453C]" />
          <span>正贡献</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#4D7358]" />
          <span>负贡献</span>
        </div>
      </div>
    </GlassCard>
  )
}
