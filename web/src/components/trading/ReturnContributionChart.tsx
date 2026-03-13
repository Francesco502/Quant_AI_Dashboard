"use client"

import { useMemo } from "react"
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
  const hasRealContributions = Boolean(contributions && contributions.length > 0)

  const data = useMemo(() => {
    if (hasRealContributions && contributions) {
      return contributions
    }

    const totalShares = holdings.reduce((sum, h) => sum + Math.max(0, h.shares), 0)
    const fallbackWeight = holdings.length > 0 ? 1 / holdings.length : 0

    return holdings.map((h) => ({
      ticker: h.ticker,
      return_pct: 0,
      contribution_pct: 0,
      weight: totalShares > 0 ? h.shares / totalShares : fallbackWeight,
    }))
  }, [contributions, hasRealContributions, holdings])

  const sortedData = useMemo(() => [...data].sort((a, b) => b.contribution_pct - a.contribution_pct), [data])

  const totalPositive = useMemo(
    () => data.filter((d) => d.contribution_pct > 0).reduce((sum, d) => sum + d.contribution_pct, 0),
    [data]
  )
  const totalNegative = useMemo(
    () => data.filter((d) => d.contribution_pct < 0).reduce((sum, d) => sum + d.contribution_pct, 0),
    [data]
  )

  return (
    <GlassCard className="p-4">
      <CardTitle className="mb-2 text-sm">Return Contribution</CardTitle>

      <div className="mb-4 flex gap-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-red-500" />
          <span className="text-xs text-muted-foreground">Positive</span>
          <span className="text-sm font-medium text-red-500">+{totalPositive.toFixed(2)}%</span>
        </div>
        <div className="flex items-center gap-2">
          <TrendingDown className="h-4 w-4 text-emerald-500" />
          <span className="text-xs text-muted-foreground">Negative</span>
          <span className="text-sm font-medium text-emerald-500">{totalNegative.toFixed(2)}%</span>
        </div>
      </div>

      {!hasRealContributions && holdings.length > 0 && (
        <div className="mb-3 text-xs text-muted-foreground">Using neutral placeholders until real return attribution data is provided.</div>
      )}

      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tickFormatter={(v: number) => `${v.toFixed(1)}%`} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="ticker" tick={{ fontSize: 11 }} width={50} />
            <Tooltip
              formatter={(value) => {
                const numericValue = typeof value === "number" ? value : Number(value ?? 0)
                const safeValue = Number.isFinite(numericValue) ? numericValue : 0
                return [`${safeValue.toFixed(2)}%`, "Contribution"]
              }}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]}>
              {sortedData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.contribution_pct >= 0 ? "#EF4444" : "#10B981"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex items-center justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-red-500" />
          <span>Positive</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-emerald-500" />
          <span>Negative</span>
        </div>
      </div>
    </GlassCard>
  )
}
