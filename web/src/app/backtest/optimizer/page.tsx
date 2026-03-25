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
      setError("请先选择策略。")
      return
    }
    if (tickerList.length === 0) {
      setError("请至少填写一个标的代码。")
      return
    }

    let paramGrid: Record<string, unknown[]>
    try {
      const parsed = JSON.parse(paramGridText) as unknown
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("参数网格必须是 JSON 对象")
      }
      paramGrid = parsed as Record<string, unknown[]>
    } catch (err) {
      console.error(err)
      setError("参数网格必须是合法的 JSON。")
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
      setError("参数优化请求失败。")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold">参数优化</h1>
        <p className="text-sm text-muted-foreground">针对选中的策略执行参数网格搜索，找到更合适的参数组合。</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard className="p-5 space-y-4 h-fit">
          <div className="space-y-2">
            <Label>策略</Label>
            <Select value={strategyId} onValueChange={setStrategyId}>
              <SelectTrigger>
                <SelectValue placeholder="请选择策略" />
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
            <Label>标的代码（逗号分隔）</Label>
            <Input value={tickersText} onChange={(e) => setTickersText(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>开始日期</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>结束日期</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>初始资金</Label>
              <Input type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>交叉验证天数</Label>
              <Input type="number" value={cvDays} onChange={(e) => setCvDays(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label>优化目标</Label>
            <Select value={objective} onValueChange={setObjective}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sharpe_ratio">夏普比率</SelectItem>
                <SelectItem value="total_return">总收益率</SelectItem>
                <SelectItem value="sortino_ratio">索提诺比率</SelectItem>
                <SelectItem value="calmar_ratio">卡玛比率</SelectItem>
                <SelectItem value="max_drawdown">最小化最大回撤</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>参数网格（JSON）</Label>
            <textarea
              className="w-full min-h-40 rounded-md border bg-background p-3 text-xs font-mono"
              value={paramGridText}
              onChange={(e) => setParamGridText(e.target.value)}
            />
          </div>

          <Button className="w-full" onClick={runOptimization} disabled={loading}>
            {loading ? "优化中..." : "开始优化"}
          </Button>

          {error && <p className="text-sm text-red-500">{error}</p>}
        </GlassCard>

        <GlassCard className="lg:col-span-2 p-5 space-y-4">
          {!result ? (
            <p className="text-sm text-muted-foreground">暂无优化结果，先在左侧设置策略与参数范围。</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground">优化目标</div>
                  <div className="text-lg font-semibold">{result.objective ?? objective}</div>
                </GlassCard>
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground">最优得分</div>
                  <div className="text-lg font-semibold">{(result.best_score ?? 0).toFixed(4)}</div>
                </GlassCard>
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground">候选组合数</div>
                  <div className="text-lg font-semibold">{result.all_results?.length ?? 0}</div>
                </GlassCard>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">最优参数</h3>
                <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">
{JSON.stringify(result.best_params ?? {}, null, 2)}
                </pre>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">全部结果</h3>
                <div className="max-h-72 overflow-auto rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="text-left p-2">得分</th>
                        <th className="text-left p-2">参数</th>
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
