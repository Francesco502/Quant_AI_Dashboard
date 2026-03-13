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
  default_params?: Record<string, unknown>
}

type SelectedStrategy = {
  id: string
  name: string
  weight: number
  params: Record<string, unknown>
}

type PortfolioResult = {
  portfolio?: {
    metrics?: Record<string, number>
    weights?: Record<string, number>
  }
  individual?: Record<string, { name?: string; weight?: number; metrics?: Record<string, number> }>
}

export default function PortfolioBacktestPage() {
  const [strategies, setStrategies] = useState<StrategyOption[]>([])
  const [selectedId, setSelectedId] = useState<string>("")
  const [portfolio, setPortfolio] = useState<SelectedStrategy[]>([])

  const [tickers, setTickers] = useState("000001.SZ,600519.SH")
  const [startDate, setStartDate] = useState("2024-01-01")
  const [endDate, setEndDate] = useState("")
  const [initialCapital, setInitialCapital] = useState("100000")
  const [benchmark, setBenchmark] = useState("000300.SH")

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PortfolioResult | null>(null)

  useEffect(() => {
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
                  default_params:
                    rec.default_params && typeof rec.default_params === "object"
                      ? (rec.default_params as Record<string, unknown>)
                      : {},
                }
              })
              .filter((item) => item.id)
          : []
        setStrategies(options)
        if (options.length > 0) {
          setSelectedId(options[0].id)
        }
      } catch (err) {
        console.error("Failed to load strategies", err)
      }
    }
    void load()
  }, [])

  const totalWeight = useMemo(() => portfolio.reduce((sum, item) => sum + item.weight, 0), [portfolio])

  const normalizeWeights = (items: SelectedStrategy[]): SelectedStrategy[] => {
    if (items.length === 0) return items
    const equalWeight = 1 / items.length
    return items.map((item) => ({ ...item, weight: equalWeight }))
  }

  const addStrategy = () => {
    const strategy = strategies.find((item) => item.id === selectedId)
    if (!strategy) return
    if (portfolio.some((item) => item.id === strategy.id)) return

    const next = [
      ...portfolio,
      {
        id: strategy.id,
        name: strategy.name,
        weight: 0,
        params: { ...(strategy.default_params ?? {}) },
      },
    ]
    setPortfolio(normalizeWeights(next))
  }

  const removeStrategy = (id: string) => {
    const next = portfolio.filter((item) => item.id !== id)
    setPortfolio(normalizeWeights(next))
  }

  const updateWeight = (id: string, value: number) => {
    setPortfolio((prev) => prev.map((item) => (item.id === id ? { ...item, weight: value } : item)))
  }

  const runBacktest = async () => {
    if (portfolio.length === 0) {
      setError("Please add at least one strategy.")
      return
    }

    const tickersList = tickers.split(",").map((ticker) => ticker.trim()).filter(Boolean)
    if (tickersList.length === 0) {
      setError("Please provide at least one ticker.")
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const strategiesPayload = Object.fromEntries(
        portfolio.map((item) => [
          item.id,
          {
            weight: item.weight,
            params: item.params,
          },
        ])
      )

      const response = await api.backtest.runMulti({
        strategies: strategiesPayload,
        tickers: tickersList,
        start_date: startDate,
        end_date: endDate || undefined,
        initial_capital: Number(initialCapital) || 100000,
        benchmark_ticker: benchmark,
      })

      setResult((response ?? null) as PortfolioResult | null)
    } catch (err) {
      console.error("Portfolio backtest failed", err)
      setError("Portfolio backtest request failed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold">Portfolio Backtest</h1>
        <p className="text-sm text-muted-foreground">Combine multiple strategies and evaluate blended performance.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        <GlassCard className="xl:col-span-1 p-5 space-y-4 h-fit">
          <div className="space-y-2">
            <Label>Strategy</Label>
            <Select value={selectedId} onValueChange={setSelectedId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {strategies.map((strategy) => (
                  <SelectItem key={strategy.id} value={strategy.id}>
                    {strategy.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" className="w-full" onClick={addStrategy}>Add Strategy</Button>
          </div>

          <div className="space-y-2">
            <Label>Tickers (comma separated)</Label>
            <Input value={tickers} onChange={(e) => setTickers(e.target.value)} />
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

          <div className="space-y-2">
            <Label>Initial Capital</Label>
            <Input type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>Benchmark</Label>
            <Input value={benchmark} onChange={(e) => setBenchmark(e.target.value)} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Total Weight</span>
              <span className={Math.abs(totalWeight - 1) < 0.01 ? "text-emerald-600" : "text-amber-600"}>
                {totalWeight.toFixed(2)}
              </span>
            </div>
            <Button className="w-full" onClick={runBacktest} disabled={loading}>
              {loading ? "Running..." : "Run Portfolio Backtest"}
            </Button>
            {error && <p className="text-sm text-red-500">{error}</p>}
          </div>
        </GlassCard>

        <div className="xl:col-span-3 space-y-4">
          <GlassCard className="p-5 space-y-3">
            <h2 className="text-lg font-semibold">Portfolio Composition</h2>
            {portfolio.length === 0 ? (
              <p className="text-sm text-muted-foreground">No strategies selected.</p>
            ) : (
              <div className="space-y-3">
                {portfolio.map((item) => (
                  <div key={item.id} className="border rounded-md p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="font-medium">{item.name}</div>
                      <Button variant="ghost" size="sm" onClick={() => removeStrategy(item.id)}>Remove</Button>
                    </div>
                    <div className="flex items-center gap-3">
                      <Label className="min-w-16">Weight</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        value={item.weight.toFixed(2)}
                        onChange={(e) => updateWeight(item.id, Number(e.target.value) || 0)}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          <GlassCard className="p-5 space-y-3">
            <h2 className="text-lg font-semibold">Backtest Result</h2>
            {!result ? (
              <p className="text-sm text-muted-foreground">No result yet.</p>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(result.portfolio?.metrics ?? {}).slice(0, 8).map(([key, value]) => (
                    <GlassCard key={key} className="p-3">
                      <div className="text-xs text-muted-foreground uppercase">{key}</div>
                      <div className="text-lg font-semibold">{typeof value === "number" ? value.toFixed(4) : String(value)}</div>
                    </GlassCard>
                  ))}
                </div>

                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Weights</h3>
                  <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">
{JSON.stringify(result.portfolio?.weights ?? {}, null, 2)}
                  </pre>
                </div>

                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Individual Strategy Metrics</h3>
                  <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">
{JSON.stringify(result.individual ?? {}, null, 2)}
                  </pre>
                </div>
              </>
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  )
}
