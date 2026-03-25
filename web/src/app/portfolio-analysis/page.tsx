"use client"

import { useState } from "react"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import type { PortfolioAnalyzeResponse } from "@/lib/api"
import { DecisionDashboard } from "@/components/trading/DecisionDashboard"
import { CorrelationHeatmap } from "@/components/trading/CorrelationHeatmap"
import { ReturnContributionChart } from "@/components/trading/ReturnContributionChart"

type Holding = {
  ticker: string
  shares: number
  costPrice?: number
}

export default function PortfolioAnalysisPage() {
  const [holdings, setHoldings] = useState<Holding[]>([{ ticker: "600519", shares: 100 }])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PortfolioAnalyzeResponse | null>(null)

  const updateHolding = (index: number, field: keyof Holding, value: string) => {
    setHoldings((prev) =>
      prev.map((item, i) => {
        if (i !== index) return item
        if (field === "shares" || field === "costPrice") {
          return { ...item, [field]: Number(value) || 0 }
        }
        return { ...item, [field]: value }
      })
    )
  }

  const addHolding = () => setHoldings((prev) => [...prev, { ticker: "", shares: 0 }])
  const removeHolding = (index: number) => setHoldings((prev) => prev.filter((_, i) => i !== index))

  const analyze = async () => {
    const payload = holdings
      .filter((item) => item.ticker.trim() && item.shares > 0)
      .map((item) => ({
        ticker: item.ticker.trim().toUpperCase(),
        shares: item.shares,
        cost_price: item.costPrice,
      }))

    if (payload.length === 0) {
      setError("请至少填写一条有效持仓。")
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await api.portfolio.analyze({ holdings: payload })
      setResult(response)
    } catch (err) {
      console.error("Portfolio analysis failed", err)
      setError("组合分析请求失败。")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8 md:space-y-12 max-w-7xl mx-auto p-6 md:p-10">
      <div className="space-y-3">
        <h1 className="text-3xl font-medium tracking-wide text-foreground/90">组合分析</h1>
        <p className="text-base font-light tracking-wide text-foreground/60">录入持仓后，查看组合风险、收益拆解与辅助决策结果。</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 md:gap-12">
        <GlassCard className="xl:col-span-1 p-6 md:p-8 space-y-8 h-fit border-white/40 bg-white/30 backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
          <h2 className="text-xl font-medium tracking-wide text-foreground/80">持仓录入</h2>
          <div className="space-y-5">
            {holdings.map((holding, index) => (
              <div key={index} className="rounded-md border p-3 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>资产代码</Label>
                    <Input value={holding.ticker} onChange={(e) => updateHolding(index, "ticker", e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>持有数量</Label>
                    <Input type="number" value={holding.shares} onChange={(e) => updateHolding(index, "shares", e.target.value)} />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>成本价（可选）</Label>
                  <Input
                    type="number"
                    value={holding.costPrice ?? ""}
                    onChange={(e) => updateHolding(index, "costPrice", e.target.value)}
                  />
                </div>
                <Button variant="ghost" size="sm" onClick={() => removeHolding(index)}>删除</Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={addHolding}>新增持仓</Button>
            <Button onClick={() => void analyze()} disabled={loading}>{loading ? "分析中..." : "开始分析"}</Button>
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
        </GlassCard>

        <div className="xl:col-span-2 space-y-8 md:space-y-12">
          <GlassCard className="p-6 md:p-10 space-y-8 border-white/40 bg-white/30 backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
            {!result ? (
              <p className="text-sm text-muted-foreground">尚未生成分析结果。</p>
            ) : (
              <>
                <DecisionDashboard ticker={holdings[0]?.ticker || "000001.SZ"} />
                <CorrelationHeatmap tickers={holdings.map((h) => h.ticker).filter(Boolean)} correlations={result?.correlations} />
                <ReturnContributionChart holdings={holdings} contributions={result?.contributions} />
                <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">
{JSON.stringify(result, null, 2)}
                </pre>
              </>
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  )
}

