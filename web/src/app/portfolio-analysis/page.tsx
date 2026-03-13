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
      setError("Please provide at least one valid holding.")
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
      setError("Portfolio analysis request failed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold">Portfolio Analysis</h1>
        <p className="text-sm text-muted-foreground">Analyze holdings and review risk/return breakdown.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <GlassCard className="xl:col-span-1 p-5 space-y-4 h-fit">
          <h2 className="text-lg font-semibold">Holdings</h2>
          <div className="space-y-3">
            {holdings.map((holding, index) => (
              <div key={index} className="rounded-md border p-3 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Ticker</Label>
                    <Input value={holding.ticker} onChange={(e) => updateHolding(index, "ticker", e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Shares</Label>
                    <Input type="number" value={holding.shares} onChange={(e) => updateHolding(index, "shares", e.target.value)} />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Cost Price (optional)</Label>
                  <Input
                    type="number"
                    value={holding.costPrice ?? ""}
                    onChange={(e) => updateHolding(index, "costPrice", e.target.value)}
                  />
                </div>
                <Button variant="ghost" size="sm" onClick={() => removeHolding(index)}>Remove</Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={addHolding}>Add Holding</Button>
            <Button onClick={() => void analyze()} disabled={loading}>{loading ? "Analyzing..." : "Analyze"}</Button>
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
        </GlassCard>

        <div className="xl:col-span-2 space-y-4">
          <GlassCard className="p-5 space-y-4">
            {!result ? (
              <p className="text-sm text-muted-foreground">No analysis result yet.</p>
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

