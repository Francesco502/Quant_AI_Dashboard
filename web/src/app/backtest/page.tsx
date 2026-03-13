"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import { usePathname, useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { GlassCard, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { api, type BacktestRunResponse, type UnknownRecord } from "@/lib/api"
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  Area,
  AreaChart
} from "recharts"
import { Play, RotateCcw, Settings2, TrendingUp, AlertTriangle, Layers, ZoomIn, ZoomOut, Download } from "lucide-react"
import { cn, formatPercent, formatCurrency } from "@/lib/utils"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"
import ComparativeAnalysisPanel from "./ComparativeAnalysisPanel"
import { StrategyTemplateSelector } from "@/components/trading/StrategyTemplateSelector"

// Design System Constants
const COLORS = {
  equity: "#3B82F6",
  equityGradientStart: "#3B82F6",
  equityGradientEnd: "#60A5FA",
  drawdown: "#DC2626",
  grid: "rgba(0, 0, 0, 0.04)",
  tooltipBg: "rgba(255, 255, 255, 0.94)"
}

const tooltipStyle = {
  backgroundColor: COLORS.tooltipBg,
  border: '1px solid rgba(0, 0, 0, 0.06)',
  borderRadius: '10px',
  backdropFilter: 'blur(20px)',
  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
  color: '#1A1A1A',
  fontSize: '12px',
}

// 缁熶竴绛栫暐绫诲瀷
type StrategyParams = Record<string, string | number | boolean | null>

interface UnifiedStrategy {
  id: string
  name: string
  description: string
  category: "classic" | "stz"
  default_params: StrategyParams
  class_name: string
  alias: string
  activate: boolean
}

interface EquityPoint {
  date: string
  equity: number
}

interface TradeRecord {
  timestamp: string
  symbol: string
  side: "BUY" | "SELL"
  price: number
  quantity: number
  commission: number
}

interface StzSignalRow {
  ticker: string
  name?: string
  selector_alias?: string
  last_close?: number
}

interface StzResultShape {
  count?: number
  data?: StzSignalRow[]
  message?: string
}

interface ComparisonRow {
  id: string
  name: string
  weight: number
  metrics: Record<string, number>
  equity_curve: EquityPoint[]
  trades: TradeRecord[]
}

interface ComparativePanelRow {
  id: string
  name: string
  weight?: number
  metrics: {
    total_return: number
    sharpe_ratio: number
    max_drawdown: number
    volatility: number
    annual_return?: number
    information_ratio?: number
    beta?: number
    alpha?: number
  }
  equity_curve: EquityPoint[]
  trades: TradeRecord[]
}

interface BacktestPageResult extends BacktestRunResponse {
  comparisonData?: ComparisonRow[]
}

const DEFAULT_METRICS: Record<string, number> = {
  total_return: 0,
  sharpe_ratio: 0,
  max_drawdown: 0,
  volatility: 0,
}

const getErrorMessage = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback

const normalizeStrategy = (row: UnknownRecord): UnifiedStrategy | null => {
  const id = typeof row.id === "string" ? row.id : ""
  if (!id) return null

  const category = row.category === "stz" ? "stz" : "classic"
  const defaultParamsRaw = (row.default_params && typeof row.default_params === "object")
    ? row.default_params as Record<string, unknown>
    : {}
  const defaultParams = Object.fromEntries(
    Object.entries(defaultParamsRaw).map(([key, value]) => [key, typeof value === "object" ? null : (value as string | number | boolean | null)])
  ) as StrategyParams

  return {
    id,
    name: typeof row.name === "string" ? row.name : id,
    description: typeof row.description === "string" ? row.description : "",
    category,
    default_params: defaultParams,
    class_name: typeof row.class_name === "string" ? row.class_name : id,
    alias: typeof row.alias === "string" ? row.alias : (typeof row.name === "string" ? row.name : id),
    activate: Boolean(row.activate ?? true),
  }
}

// Enhanced Chart Component with Zoom/Pan simulation
const EnhancedChart = ({ data }: { data: EquityPoint[] }) => {
  const [viewRange, setViewRange] = useState<{ start: number; end: number }>({ start: 0, end: 100 })
  const autoScale = true

  const paginatedData = data.slice(viewRange.start, viewRange.end)

  const handleZoomIn = useCallback(() => {
    const range = viewRange.end - viewRange.start
    if (range > 10) {
      const newRange = Math.floor(range * 0.8)
      const center = Math.floor((viewRange.start + viewRange.end) / 2)
      setViewRange({
        start: Math.max(0, center - Math.floor(newRange / 2)),
        end: Math.min(data.length, center + Math.floor(newRange / 2))
      })
    }
  }, [viewRange, data.length])

  const handleZoomOut = useCallback(() => {
    const range = viewRange.end - viewRange.start
    const newRange = Math.min(data.length, Math.floor(range * 1.2))
    const center = Math.floor((viewRange.start + viewRange.end) / 2)
    setViewRange({
      start: Math.max(0, center - Math.floor(newRange / 2)),
      end: Math.min(data.length, center + Math.floor(newRange / 2))
    })
  }, [viewRange, data.length])

  const handleResetZoom = useCallback(() => {
    setViewRange({ start: 0, end: data.length })
  }, [data.length])

  if (!data || data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground opacity-50">
        No data yet. Run a backtest first.
      </div>
    )
  }

  return (
    <div className="relative w-full h-full">
      {/* Chart Header with Controls */}
      <div className="absolute top-0 right-0 flex gap-2 z-10">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleZoomIn}
          className="h-8 w-8 p-0 bg-background/80 backdrop-blur rounded-md"
          title="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleZoomOut}
          className="h-8 w-8 p-0 bg-background/80 backdrop-blur rounded-md"
          title="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleResetZoom}
          className="h-8 w-8 p-0 bg-background/80 backdrop-blur rounded-md"
          title="Reset"
        >
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Responsive Chart */}
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={paginatedData}>
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={COLORS.equityGradientStart} stopOpacity={0.3}/>
              <stop offset="95%" stopColor={COLORS.equityGradientStart} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
          <XAxis
            dataKey="date"
            stroke="#888"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
            tickMargin={10}
          />
          <YAxis
            domain={autoScale ? ['auto', 'auto'] : undefined}
            stroke="#888"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tickFormatter={(val) => `楼${(val/1000).toFixed(0)}k`}
            tickMargin={10}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(val?: number | string) => [formatCurrency(Number(val ?? 0)), "Equity"]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Legend />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={COLORS.equityGradientStart}
            strokeWidth={2}
            fill="url(#equityGradient)"
            animationDuration={300}
          />
          <ReferenceLine y={data[0]?.equity} stroke="#888" strokeDasharray="3 3" label={{ position: "left", value: "Start" }} />
        </AreaChart>
      </ResponsiveContainer>

      {/* View Statistics */}
      <div className="flex justify-between text-xs text-muted-foreground mt-2 px-1">
        <span>Points: {paginatedData.length}</span>
        <span>
          Range: {paginatedData[0]?.date || "-"} ~ {paginatedData[paginatedData.length - 1]?.date || "-"}
        </span>
      </div>
    </div>
  )
}

export default function BacktestPage() {
  const pathname = usePathname()
  const router = useRouter()
  const [strategies, setStrategies] = useState<UnifiedStrategy[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState<string>("")
  const [tickers, setTickers] = useState<string>("013281,002611,160615")
  const [startDate, setStartDate] = useState<string>("2024-01-01")
  const [endDate, setEndDate] = useState<string>("")
  const [initialCapital, setInitialCapital] = useState<string>("100000")
  const [params, setParams] = useState<StrategyParams>({})
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestPageResult | null>(null)
  const [showComparison, setShowComparison] = useState(false)

  // Load strategy list from unified endpoint.
  useEffect(() => {
    api.backtest.listStrategies().then((res) => {
      const parsed = (res || [])
        .map((row) => normalizeStrategy(row as UnknownRecord))
        .filter((row): row is UnifiedStrategy => row !== null)
      setStrategies(parsed)
      if (parsed.length > 0) {
        setSelectedStrategy(parsed[0].id)
        setParams((parsed[0].default_params || {}) as StrategyParams)
      }
    }).catch((error) => console.error("Failed to load strategies:", error))
  }, [])

  const handleStrategyChange = (id: string) => {
    setSelectedStrategy(id)
    const strat = strategies.find(s => s.id === id)
    if (strat) {
      setParams((strat.default_params || {}) as StrategyParams)
    }
  }

  const handleParamChange = (key: string, value: string) => {
    setParams((prev) => ({ ...prev, [key]: value }))
  }

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    setShowComparison(false)
    try {
      const strat = strategies.find(s => s.id === selectedStrategy)

      if (strat && strat.category === "stz") {
        // STZ 绛栫暐 鈫?浣跨敤 /stz/run 鎺ュ彛
        const tickerList = tickers.split(",").map(t => t.trim()).filter(Boolean)
        const res = await api.stz.run({
          trade_date: endDate || new Date().toISOString().split('T')[0],
          mode: "universe",
          selector_names: [strat.class_name],
          selector_params: { [strat.class_name]: params },
          tickers: tickerList.length > 0 ? tickerList : undefined
        })
        // Adapt STZ response into backtest result shape.
        setResult({
          metrics: DEFAULT_METRICS,
          equity_curve: [],
          trades: [],
          stz_result: res as unknown as UnknownRecord,
        })
      } else {
        // 缁忓吀绛栫暐 鈫?浣跨敤 /backtest/run 鎺ュ彛
        const tickerList = tickers.split(",").map(t => t.trim()).filter(Boolean)
        const res = await api.backtest.run({
          strategy_id: selectedStrategy,
          tickers: tickerList,
          start_date: startDate,
          end_date: endDate || undefined,
          initial_capital: parseFloat(initialCapital),
          params
        })
        setResult(res as BacktestPageResult)
      }
    } catch (error) {
      console.error("Backtest failed", error)
      alert(`Backtest failed: ${getErrorMessage(error, "Please check parameters or data.")}`)
    } finally {
      setLoading(false)
    }
  }

  // Run comparison for all classic strategies
  const handleCompareStrategies = async () => {
    if (classicStrategies.length < 2) {
      alert("Please select at least 2 classic strategies for comparison.")
      return
    }

    setLoading(true)
    setResult(null)
    setShowComparison(true)
    try {
      const tickerList = tickers.split(",").map(t => t.trim()).filter(Boolean)

      // Prepare strategies object
      const strategiesObj: Record<string, { weight: number; params: UnknownRecord }> = {}
      classicStrategies.forEach(s => {
        strategiesObj[s.id] = {
          weight: 1.0 / classicStrategies.length,
          params: (s.default_params || {}) as UnknownRecord
        }
      })

      const res = await api.backtest.runMulti({
        strategies: strategiesObj,
        tickers: tickerList,
        start_date: startDate,
        end_date: endDate || undefined,
        initial_capital: parseFloat(initialCapital),
        benchmark_ticker: "000300.SH"
      })

      // Store comparison result
      const comparisonResult: BacktestPageResult = {
        portfolio: res.portfolio,
        individual: res.individual || {},
        comparisonData: classicStrategies.map(s => ({
          id: s.id,
          name: s.name,
          weight: res.portfolio?.weights?.[s.id] || 1.0 / classicStrategies.length,
          metrics: res.individual?.[s.id]?.metrics || DEFAULT_METRICS,
          equity_curve: (res.individual?.[s.id]?.equity_curve || []) as EquityPoint[],
          trades: (res.individual?.[s.id]?.trades || []) as TradeRecord[],
        }))
      }
      setResult(comparisonResult)
    } catch (error) {
      console.error("Comparison failed", error)
      alert(`Comparison failed: ${getErrorMessage(error, "Please check parameters.")}`)
    } finally {
      setLoading(false)
    }
  }

  const currentStrategy = strategies.find(s => s.id === selectedStrategy)
  const isSTZ = currentStrategy?.category === "stz"

  // Split STZ strategies and classic strategies.
  const classicStrategies = strategies.filter(s => s.category === "classic")
  const stzStrategies = strategies.filter(s => s.category === "stz")
  const stzResult = result?.stz_result as StzResultShape | undefined
  const metrics = (result?.metrics || DEFAULT_METRICS) as Record<string, number>
  const equityCurve = (result?.equity_curve || []) as EquityPoint[]
  const trades = (result?.trades || []) as TradeRecord[]
  const comparisonResults = useMemo(() => {
    if (!result?.comparisonData) return {}
    return result.comparisonData.reduce<Record<string, ComparativePanelRow>>((acc, row) => {
      acc[row.id] = {
        id: row.id,
        name: row.name,
        weight: row.weight,
        metrics: {
          total_return: Number(row.metrics.total_return || 0),
          sharpe_ratio: Number(row.metrics.sharpe_ratio || 0),
          max_drawdown: Number(row.metrics.max_drawdown || 0),
          volatility: Number(row.metrics.volatility || 0),
          annual_return: Number(row.metrics.annual_return || 0),
          information_ratio: Number(row.metrics.information_ratio || 0),
          beta: Number(row.metrics.beta || 0),
          alpha: Number(row.metrics.alpha || 0),
        },
        equity_curve: row.equity_curve,
        trades: row.trades,
      }
      return acc
    }, {})
  }, [result?.comparisonData])

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-xl w-fit">
        <Button
          variant="ghost"
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium transition-all",
            !pathname.includes("portfolio") && "bg-background shadow-sm text-foreground"
          )}
          onClick={() => router.push("/backtest")}
        >
          Historical Backtest
        </Button>
        <Button
          variant="ghost"
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium transition-all hover:bg-muted/80",
            pathname.includes("portfolio") && "bg-background shadow-sm text-foreground"
          )}
          onClick={() => router.push("/portfolio-backtest")}
        >
          Portfolio Backtest
        </Button>
        <Button
          variant="ghost"
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium transition-all hover:bg-muted/80",
            pathname.includes("optimizer") && "bg-background shadow-sm text-foreground"
          )}
          onClick={() => router.push("/backtest/optimizer")}
        >
          Parameter Optimization
        </Button>
      </div>

      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">
            Historical Backtest
          </h1>
          <p className="text-[13px] text-foreground/40">
            Validate strategy performance on historical data for both classic quant and STZ scanners.
            <span className="mx-2">|</span>
            Responsive charts enabled
          </p>
        </div>
        {result && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                try {
                  const exportData = {
                    equity_curve: equityCurve,
                    trades,
                    metrics,
                    report_type: "html",
                    include_charts: true,
                  }
                  const res = await api.backtest.export(exportData)
                  if (res?.download_url) {
                    window.open(res.download_url, "_blank")
                  } else {
                    alert("Export succeeded, but no download URL was returned.")
                  }
                } catch (error) {
                  alert(`Export failed: ${getErrorMessage(error, "Unknown error")}`)
                }
              }}
            >
              <Download className="w-4 h-4 mr-2" />
              Export HTML
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open("/api/backtest/export", "_blank")}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Export Report
            </Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Configuration Panel */}
        <GlassCard className="lg:col-span-1 p-6 space-y-6 h-fit">
          <div className="flex items-center gap-2 mb-2">
            <Settings2 className="w-5 h-5 text-primary" />
            <CardTitle>Backtest Configuration</CardTitle>
          </div>

          <div className="space-y-4">
            {/* 绛栫暐閫夋嫨 - 鍒嗙粍 */}
            <div className="space-y-2">
              <Label className="flex items-center gap-1">
                Select Strategy
                <HelpTooltip content="Classic strategies support full backtest outputs; STZ is used for signal validation and screening." />
              </Label>
              <Select value={selectedStrategy} onValueChange={handleStrategyChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select strategy" />
                </SelectTrigger>
                <SelectContent>
                  {classicStrategies.length > 0 && (
                    <>
                      <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground bg-muted/50">
                        Classic Quant Strategies
                      </div>
                      {classicStrategies.map(s => (
                        <SelectItem key={s.id} value={s.id}>
                          <span className="flex items-center gap-2">
                            {s.name}
                          </span>
                        </SelectItem>
                      ))}
                    </>
                  )}
                  {stzStrategies.length > 0 && (
                    <>
                      <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground bg-muted/50 mt-1">
                        STZ Strategies
                      </div>
                      {stzStrategies.map(s => (
                        <SelectItem key={s.id} value={s.id}>
                          <span className="flex items-center gap-2">
                            {s.alias}
                            <span className="text-muted-foreground text-xs">({s.class_name})</span>
                          </span>
                        </SelectItem>
                      ))}
                    </>
                  )}
                </SelectContent>
              </Select>
              {currentStrategy && (
                <div className="flex items-start gap-1.5 mt-1">
                  <Badge
                    variant={isSTZ ? "default" : "secondary"}
                    className="text-xs shrink-0"
                  >
                    {isSTZ ? "STZ" : "Classic"}
                  </Badge>
                  <p className="flex-1 min-w-0 text-xs text-muted-foreground whitespace-normal break-words">
                    {currentStrategy.description}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Tickers (comma-separated)</Label>
              <Input value={tickers} onChange={e => setTickers(e.target.value)} placeholder="e.g. 013281,002611" />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>{isSTZ ? "Trade Date" : "End Date"}</Label>
                <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
              </div>
            </div>

            {!isSTZ && (
              <div className="space-y-2">
                <Label>Initial Capital</Label>
                <Input type="number" value={initialCapital} onChange={e => setInitialCapital(e.target.value)} />
              </div>
            )}

            {/* Dynamic Params */}
            {currentStrategy && Object.keys(params).length > 0 && (
              <div className="pt-4 border-t border-black/[0.04] space-y-4">
                <Label className="text-[11px] font-medium uppercase tracking-wider text-foreground/40">
                  Strategy Parameters
                </Label>

                {/* Strategy Template Selector */}
                <StrategyTemplateSelector
                  currentStrategyId={selectedStrategy}
                  currentStrategyType={isSTZ ? "stz" : "classic"}
                  currentParams={params}
                  onLoadTemplate={(template) => {
                    setParams(template.params as StrategyParams)
                  }}
                />

                {Object.entries(params).map(([key, val]) => {
                  // Skip nested object parameters in this simple editor.
                  if (typeof val === "object" && val !== null) return null
                  return (
                    <div key={key} className="space-y-1">
                      <Label className="text-xs font-mono">{key}</Label>
                      <Input
                        value={String(val ?? "")}
                        onChange={e => handleParamChange(key, e.target.value)}
                        className="h-8"
                      />
                    </div>
                  )
                })}
              </div>
            )}

            <Button
              className="w-full mt-4"
              onClick={handleRun}
              disabled={loading}
            >
              {loading ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1 }}
                  className="mr-2"
                >
                  <RotateCcw className="w-4 h-4" />
                </motion.div>
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              {isSTZ ? "Run Scanner" : "Run Backtest"}
            </Button>

            {/* Compare Strategies Button */}
            {classicStrategies.length >= 2 && (
              <Button
                className="w-full mt-2"
                variant="outline"
                onClick={handleCompareStrategies}
                disabled={loading || classicStrategies.length < 2}
              >
                <TrendingUp className="w-4 h-4 mr-2" />
                Compare Strategies ({classicStrategies.length})
              </Button>
            )}
          </div>
        </GlassCard>

        {/* Results Panel */}
        <div className="lg:col-span-3 space-y-6">
          {/* STZ Scan Results */}
          {stzResult && (
            <GlassCard className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="w-5 h-5 text-blue-500" />
                <CardTitle>Scan Results</CardTitle>
                <Badge variant="secondary">{stzResult.count || 0} signals</Badge>
              </div>
              {stzResult.data && Array.isArray(stzResult.data) && stzResult.data.length > 0 ? (
                <div className="rounded-md border overflow-hidden overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-black/[0.04] text-foreground/40 text-[12px] uppercase tracking-wider bg-muted/30">
                        <th className="py-2 px-3 text-left">Ticker</th>
                        <th className="py-2 px-3 text-left">Name</th>
                        <th className="py-2 px-3 text-left">Selector</th>
                        <th className="py-2 px-3 text-right">Close</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stzResult.data.map((row, idx: number) => (
                        <tr key={idx} className="border-b border-black/[0.03] hover:bg-muted/20">
                          <td className="py-2 px-3 font-mono font-medium">{row.ticker}</td>
                          <td className="py-2 px-3">{row.name || "-"}</td>
                          <td className="py-2 px-3">
                            <Badge variant="outline" className="text-xs">{row.selector_alias}</Badge>
                          </td>
                          <td className="py-2 px-3 text-right">{Number(row.last_close).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-12 text-center text-muted-foreground bg-muted/20 rounded-lg border border-dashed">
                  No symbols matched current conditions.
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-3">{stzResult.message}</p>
            </GlassCard>
          )}

          {/* Classic Backtest Metrics */}
          {!stzResult && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    Total Return
                    <HelpTooltip content={GLOSSARY.TotalReturn.definition} />
                  </span>
                  <span className={cn("text-2xl font-bold", (metrics.total_return || 0) >= 0 ? "text-emerald-500" : "text-red-500")}>
                    {result ? formatPercent(metrics.total_return || 0) : "---"}
                  </span>
                </GlassCard>
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    Sharpe Ratio
                    <HelpTooltip content={GLOSSARY.SharpeRatio.definition} />
                  </span>
                  <span className="text-2xl font-bold">
                    {result ? (metrics.sharpe_ratio || 0).toFixed(2) : "---"}
                  </span>
                </GlassCard>
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    Max Drawdown
                    <HelpTooltip content={GLOSSARY.MaxDrawdown.definition} />
                  </span>
                  <span className="text-2xl font-bold text-red-500">
                    {result ? formatPercent(metrics.max_drawdown || 0) : "---"}
                  </span>
                </GlassCard>
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    Volatility
                    <HelpTooltip content={GLOSSARY.Volatility.definition} />
                  </span>
                  <span className="text-2xl font-bold">
                    {result ? formatPercent(metrics.volatility || 0) : "---"}
                  </span>
                </GlassCard>
              </div>

              {/* Enhanced Chart */}
              <GlassCard className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    <CardTitle className="flex items-center gap-1">
                      Equity Curve
                      <HelpTooltip content={GLOSSARY.EquityCurve.definition} />
                    </CardTitle>
                  </div>
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <ZoomIn className="w-3 h-3" />
                    Zoom and pan supported
                  </span>
                </div>
                <div className="h-[400px] w-full">
                  {result && equityCurve.length > 0 ? (
                    <EnhancedChart data={equityCurve} />
                  ) : (
                    <div className="h-full flex items-center justify-center text-muted-foreground opacity-50">
                      No data yet. Run a backtest first.
                    </div>
                  )}
                </div>
              </GlassCard>

              {/* Trades Table */}
              <GlassCard className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-primary" />
                    <CardTitle>Trade Log ({trades.length || 0})</CardTitle>
                  </div>
                </div>
                <div className="max-h-[300px] overflow-auto rounded-lg border">
                  <table className="w-full text-[13px] text-left">
                    <thead className="sticky top-0 bg-background z-10 shadow-sm">
                      <tr className="border-b border-black/[0.04] text-foreground/40 text-[12px] uppercase tracking-wider">
                        <th className="py-2 px-3 text-left">Time</th>
                        <th className="py-2 px-3 text-left">Ticker</th>
                        <th className="py-2 px-3 text-left">Side</th>
                        <th className="py-2 px-3 text-right">Price</th>
                        <th className="py-2 px-3 text-right">Quantity</th>
                        <th className="py-2 px-3 text-right">Commission</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-black/[0.03]">
                      {trades.map((t, i: number) => (
                        <tr key={i} className="hover:bg-black/[0.02] transition-colors duration-150">
                          <td className="py-2 px-3 font-mono text-xs">{new Date(t.timestamp).toLocaleDateString()}</td>
                          <td className="py-2 px-3 font-bold">{t.symbol}</td>
                          <td className={cn("py-2 px-3 font-bold", t.side === "BUY" ? "text-red-500" : "text-emerald-500")}>
                            {t.side === "BUY" ? "Buy" : "Sell"}
                          </td>
                          <td className="py-2 px-3 text-right font-mono">{t.price.toFixed(2)}</td>
                          <td className="py-2 px-3 text-right font-mono">{t.quantity}</td>
                          <td className="py-2 px-3 text-right font-mono text-muted-foreground">{t.commission.toFixed(2)}</td>
                        </tr>
                      ))}
                      {!trades.length && !stzResult && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground">No trades recorded.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </>
          )}

          {/* Comparison Panel - Show when showComparison is true */}
          {showComparison && Object.keys(comparisonResults).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="lg:col-span-3 space-y-6"
            >
              <ComparativeAnalysisPanel results={comparisonResults} />
            </motion.div>
          )}

          {/* Empty state */}
          {!result && !showComparison && (
            <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground bg-muted/10 rounded-xl border border-dashed">
              <TrendingUp className="h-12 w-12 mb-4 opacity-20" />
              <p className="text-lg font-medium">Ready to run</p>
              <p className="text-sm opacity-70 mt-2">Select a strategy, configure parameters, then run.</p>
              <div className="mt-6 flex gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  Multi-strategy comparison
                </span>
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" /></svg>
                  Parameter optimization
                </span>
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                  Report export
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

