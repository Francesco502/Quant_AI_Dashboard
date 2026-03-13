"use client"

import { useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

type StrategyOption = {
  id: string
  name: string
}

type OptimizationResult = {
  objective?: string
  best_score?: number
  best_params?: Record<string, unknown>
  all_results?: Array<{ params?: string; params_dict?: Record<string, unknown>; score?: number }>
  best_result?: {
    metrics?: Record<string, number>
  }
}

const DEFAULT_PARAM_GRID: Record<string, unknown[]> = {
  fast: [8, 12, 20],
  slow: [21, 26, 34],
}

export default function BacktestOptimizerPage() {
  const [strategies, setStrategies] = useState<StrategyOption[]>([])
  const [strategyId, setStrategyId] = useState<string>("")
  const [tickersText, setTickersText] = useState("000001.SZ,600519.SH")
  const [startDate, setStartDate] = useState("2024-01-01")
  const [endDate, setEndDate] = useState("")
  const [initialCapital, setInitialCapital] = useState("100000")
  const [objective, setObjective] = useState("sharpe_ratio")
  const [cvDays, setCvDays] = useState("60")
  const [paramGridText, setParamGridText] = useState(JSON.stringify(DEFAULT_PARAM_GRID, null, 2))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<OptimizationResult | null>(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const items = await api.backtest.listStrategies()
        const options = Array.isArray(items)
          ? items
              .filter((item) => item && typeof item === "object")
              .map((item) => {
                const rec = item as Record<string, unknown>
                return {
                  id: String(rec.id ?? ""),
                  name: String(rec.name ?? rec.id ?? "unknown"),
                }
              })
              .filter((item) => item.id)
          : []

        if (mounted) {
          setStrategies(options)
          if (options.length > 0 && !strategyId) {
            setStrategyId(options[0].id)
          }
        }
      } catch (err) {
        console.error("Failed to load strategies", err)
      }
    }
    void load()
    return () => {
      mounted = false
    }
  }, [strategyId])

  const tickerList = useMemo(
    () => tickersText.split(",").map((ticker) => ticker.trim()).filter(Boolean),
    [tickersText]
  )

  const runOptimization = async () => {
    if (!strategyId) {
      setError("Please select a strategy.")
      return
    }
    if (tickerList.length === 0) {
      setError("Please provide at least one ticker.")
      return
    }

    let paramGrid: Record<string, unknown[]>
    try {
      const parsed = JSON.parse(paramGridText) as unknown
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Parameter grid must be a JSON object")
      }
      paramGrid = parsed as Record<string, unknown[]>
    } catch (err) {
      console.error(err)
      setError("Parameter grid must be valid JSON.")
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await api.backtest.optimize({
        strategy_id: strategyId,
        tickers: tickerList,
        param_grid: paramGrid,
        start_date: startDate,
        end_date: endDate || undefined,
        initial_capital: Number(initialCapital) || 100000,
        objective,
        cv_days: Number(cvDays) || 60,
      })
      setResult((res ?? null) as OptimizationResult | null)
    } catch (err) {
      console.error("Optimization failed", err)
      setError("Optimization request failed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold">Parameter Optimization</h1>
        <p className="text-sm text-muted-foreground">Run a parameter grid search for a selected strategy.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard className="p-5 space-y-4 h-fit">
          <div className="space-y-2">
            <Label>Strategy</Label>
            <Select value={strategyId} onValueChange={setStrategyId}>
              <SelectTrigger>
                <SelectValue placeholder="Select strategy" />
              </SelectTrigger>
              <SelectContent>
                {strategies.map((strategy) => (
                  <SelectItem key={strategy.id} value={strategy.id}>
                    {strategy.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Tickers (comma separated)</Label>
            <Input value={tickersText} onChange={(e) => setTickersText(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Initial Capital</Label>
              <Input type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>CV Days</Label>
              <Input type="number" value={cvDays} onChange={(e) => setCvDays(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Objective</Label>
            <Select value={objective} onValueChange={setObjective}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sharpe_ratio">Sharpe Ratio</SelectItem>
                <SelectItem value="total_return">Total Return</SelectItem>
                <SelectItem value="sortino_ratio">Sortino Ratio</SelectItem>
                <SelectItem value="calmar_ratio">Calmar Ratio</SelectItem>
                <SelectItem value="max_drawdown">Minimize Max Drawdown</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Parameter Grid (JSON)</Label>
            <textarea
              className="w-full min-h-40 rounded-md border bg-background p-3 text-xs font-mono"
              value={paramGridText}
              onChange={(e) => setParamGridText(e.target.value)}
            />
          </div>

          <Button className="w-full" onClick={runOptimization} disabled={loading}>
            {loading ? "Optimizing..." : "Run Optimization"}
          </Button>

          {error && <p className="text-sm text-red-500">{error}</p>}
        </GlassCard>

        <GlassCard className="lg:col-span-2 p-5 space-y-4">
          {!result ? (
            <p className="text-sm text-muted-foreground">No optimization result yet.</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground uppercase">Objective</div>
                  <div className="text-lg font-semibold">{result.objective ?? objective}</div>
                </GlassCard>
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground uppercase">Best Score</div>
                  <div className="text-lg font-semibold">{(result.best_score ?? 0).toFixed(4)}</div>
                </GlassCard>
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground uppercase">Candidates</div>
                  <div className="text-lg font-semibold">{result.all_results?.length ?? 0}</div>
                </GlassCard>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">Best Params</h3>
                <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">
{JSON.stringify(result.best_params ?? {}, null, 2)}
                </pre>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">All Results</h3>
                <div className="max-h-72 overflow-auto rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="text-left p-2">Score</th>
                        <th className="text-left p-2">Params</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(result.all_results ?? []).map((item, index) => (
                        <tr key={`${index}-${item.score ?? 0}`} className="border-t">
                          <td className="p-2">{(item.score ?? 0).toFixed(4)}</td>
                          <td className="p-2 font-mono text-xs">
                            {item.params ?? JSON.stringify(item.params_dict ?? {})}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
