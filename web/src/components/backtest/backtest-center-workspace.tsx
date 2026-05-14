"use client"

import { useSearchParams } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { BarChart3, Download, Play, Radar, RefreshCw, SlidersHorizontal, Workflow } from "lucide-react"
import { EquityChart, SummaryMetric } from "@/components/backtest/backtest-charts"
import { EmptyState } from "@/components/data/empty-state"
import { PanelHeader } from "@/components/data/panel-header"
import { StatusPill } from "@/components/data/status-pill"
import { MultiAssetPicker } from "@/components/shared/multi-asset-picker"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  api,
  type Asset,
  type BacktestRunResponse,
  type DataFreshnessItem,
  type OptimizationResult,
  type RunStrategyResult,
  type UnknownRecord,
} from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { GLOSSARY } from "@/lib/glossary"
import { formatDateInBeijing, getTodayInBeijing } from "@/lib/time"
import { formatCurrency, formatPercent } from "@/lib/utils"

type Mode = "classic" | "scan" | "compare" | "optimize"
type Params = Record<string, string | number | boolean | null>
type Strategy = {
  id: string
  name: string
  description: string
  category: "classic" | "stz"
  default_params: Params
  class_name: string
}
type EquityPoint = { date: string; equity: number }
type TradeRecord = {
  timestamp: string
  symbol: string
  side: "BUY" | "SELL"
  price: number
  quantity: number
  commission: number
}
type ScanRow = { ticker: string; name?: string; selector_alias?: string; last_close?: number }

function normalizeModeParam(value: string | null): Mode {
  if (value === "scan" || value === "compare" || value === "classic" || value === "optimize") return value
  if (value === "portfolio") return "compare"
  return "classic"
}

const PARAM_LABELS: Record<string, string> = {
  short_window: "短均线",
  long_window: "长均线",
  window: "回看窗口",
  std_dev: "标准差",
  fast: "快线",
  slow: "慢线",
  signal: "信号线",
  threshold: "阈值",
  holding_days: "持有天数",
}

const DEFAULT_METRICS = { total_return: 0, sharpe_ratio: 0, max_drawdown: 0, volatility: 0 }

const MODE_META: Record<
  Mode,
  {
    title: string
    description: string
    icon: typeof BarChart3
    tone: "indigo" | "ochre" | "plum"
    emptyDescription: string
  }
> = {
  classic: {
    title: "策略回测",
    description: "验证单一策略在指定资产与时间区间内的收益、回撤与交易节奏。",
    icon: BarChart3,
    tone: "indigo",
    emptyDescription: "先选择一条策略和一组标的，再生成历史权益曲线与交易明细。",
  },
  scan: {
    title: "信号扫描",
    description: "只关注当前时点的候选标的，不强行把扫描结果包装成权益曲线。",
    icon: Radar,
    tone: "ochre",
    emptyDescription: "适合先找今天值得继续研究的候选，再决定是否进入回测。",
  },
  compare: {
    title: "多策略对比",
    description: "把全部经典策略放到同一批标的和区间里，比较风格稳定性与结果差异。",
    icon: Workflow,
    tone: "plum",
    emptyDescription: "先定标的与区间，再比较哪一类经典策略更适合当前样本。",
  },
  optimize: {
    title: "参数优化",
    description: "围绕单一经典策略做网格搜索，找到更匹配当前样本的参数组合。",
    icon: SlidersHorizontal,
    tone: "ochre",
    emptyDescription: "先选择经典策略和参数网格，再运行优化查看最优参数与候选排序。",
  },
}

function normalizeStrategy(row: UnknownRecord): Strategy | null {
  const id = typeof row.id === "string" ? row.id : ""
  if (!id) return null
  const rawParams =
    row.default_params && typeof row.default_params === "object"
      ? (row.default_params as Record<string, unknown>)
      : {}
  return {
    id,
    name: typeof row.name === "string" ? row.name : id,
    description: typeof row.description === "string" ? row.description : "",
    category: row.category === "stz" ? "stz" : "classic",
    default_params: Object.fromEntries(
      Object.entries(rawParams).map(([key, value]) => [
        key,
        typeof value === "object" ? null : (value as string | number | boolean | null),
      ]),
    ),
    class_name: typeof row.class_name === "string" ? row.class_name : id,
  }
}

function normalizeParams(params: Params) {
  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => {
      if (typeof value === "string") {
        const trimmed = value.trim()
        const numeric = Number(trimmed)
        if (trimmed !== "" && Number.isFinite(numeric)) return [key, numeric]
        if (trimmed === "true") return [key, true]
        if (trimmed === "false") return [key, false]
      }
      return [key, value]
    }),
  )
}

function formatCandidateValue(value: string | number | boolean | null) {
  return value == null ? "" : String(value)
}

function buildDefaultParamGrid(params: Params) {
  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => {
      if (typeof value === "number" && Number.isFinite(value)) {
        const low = Number((value * 0.8).toFixed(4))
        const high = Number((value * 1.2).toFixed(4))
        return [key, Array.from(new Set([low, value, high])).join(", ")]
      }
      return [key, formatCandidateValue(value)]
    }),
  )
}

function parseCandidateValue(value: string) {
  const trimmed = value.trim()
  if (trimmed === "true") return true
  if (trimmed === "false") return false
  const numeric = Number(trimmed)
  return trimmed !== "" && Number.isFinite(numeric) ? numeric : trimmed
}

function parseParamGrid(grid: Record<string, string>, fallback: Params) {
  return Object.fromEntries(
    Object.entries(fallback).map(([key, fallbackValue]) => {
      const candidates = (grid[key] || formatCandidateValue(fallbackValue))
        .split(/[,\uFF0C]/)
        .map((item) => item.trim())
        .filter(Boolean)
        .map(parseCandidateValue)
      return [key, candidates.length > 0 ? candidates : [fallbackValue]]
    }),
  )
}

export function BacktestCenterWorkspace() {
  const searchParams = useSearchParams()
  const queryTickerParam = searchParams.get("tickers") || searchParams.get("ticker") || searchParams.get("symbol") || ""
  const queryTickers = useMemo(
    () =>
      queryTickerParam
        .split(/[,\uFF0C]/)
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
    [queryTickerParam],
  )
  const [mode, setMode] = useState<Mode>(() => normalizeModeParam(searchParams.get("mode") ?? searchParams.get("tab")))
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [manualTickers, setManualTickers] = useState("")
  const [selectedStrategy, setSelectedStrategy] = useState("")
  const [startDate, setStartDate] = useState("2024-01-01")
  const [endDate, setEndDate] = useState("")
  const [initialCapital, setInitialCapital] = useState("100000")
  const [params, setParams] = useState<Params>({})
  const [paramGrid, setParamGrid] = useState<Record<string, string>>({})
  const [optimizeObjective, setOptimizeObjective] = useState("trading_objective")
  const [optimizeCvDays, setOptimizeCvDays] = useState("60")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [classicResult, setClassicResult] = useState<BacktestRunResponse | null>(null)
  const [scanResult, setScanResult] = useState<RunStrategyResult | null>(null)
  const [compareResult, setCompareResult] = useState<BacktestRunResponse | null>(null)
  const [optimizeResult, setOptimizeResult] = useState<OptimizationResult | null>(null)
  const [freshnessItems, setFreshnessItems] = useState<DataFreshnessItem[]>([])

  useEffect(() => {
    const nextMode = normalizeModeParam(searchParams.get("mode") ?? searchParams.get("tab"))
    setMode((current) => (current === nextMode ? current : nextMode))
  }, [searchParams])

  useEffect(() => {
    void (async () => {
      try {
        const [rows, pool, personalAssets] = await Promise.all([
          api.backtest.listStrategies(),
          api.stz.getAssetPool().catch(() => []),
          api.user.assets.getOverview(false).catch(() => ({ assets: [] })),
        ])
        const parsed = (rows || [])
          .map((row) => normalizeStrategy(row as UnknownRecord))
          .filter((row): row is Strategy => row !== null)
        const mergedAssets = new Map<string, Asset>()
        for (const asset of pool || []) {
          mergedAssets.set(asset.ticker, asset)
        }
        for (const asset of personalAssets.assets || []) {
          if (!mergedAssets.has(asset.ticker)) {
            mergedAssets.set(asset.ticker, {
              ticker: asset.ticker,
              name: asset.asset_name || asset.ticker,
            })
          }
        }
        setStrategies(parsed)
        setAssets(Array.from(mergedAssets.values()))
        if (queryTickers.length > 0) {
          setSelectedTickers(queryTickers)
        }
        const firstClassic = parsed.find((item) => item.category === "classic") ?? parsed[0]
        if (firstClassic) {
          setSelectedStrategy(firstClassic.id)
          setParams(firstClassic.default_params)
          setParamGrid(buildDefaultParamGrid(firstClassic.default_params))
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "读取回测配置失败")
      }
    })()
  }, [queryTickers])

  useEffect(() => {
    if (assets.length > 0 && selectedTickers.length === 0) {
      setSelectedTickers(assets.slice(0, 3).map((asset) => asset.ticker))
    }
  }, [assets, selectedTickers.length])

  const classicStrategies = useMemo(
    () => strategies.filter((item) => item.category === "classic"),
    [strategies],
  )
  const scanStrategies = useMemo(
    () => strategies.filter((item) => item.category === "stz"),
    [strategies],
  )
  const strategyGroup = mode === "scan" ? scanStrategies : classicStrategies
  const currentStrategy = strategyGroup.find((item) => item.id === selectedStrategy) ?? strategyGroup[0] ?? null
  const activeTickers = selectedTickers.length > 0
    ? selectedTickers
    : manualTickers
        .split(",")
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean)
  const activeMetrics =
    (classicResult?.metrics ||
      compareResult?.portfolio?.metrics ||
      optimizeResult?.best_result?.metrics ||
      DEFAULT_METRICS) as Record<string, number>
  const activeEquity = (classicResult?.equity_curve ||
    compareResult?.portfolio?.equity_curve ||
    optimizeResult?.best_result?.equity_curve ||
    []) as EquityPoint[]
  const activeTrades = (classicResult?.trades || compareResult?.portfolio?.trades || []) as TradeRecord[]

  useEffect(() => {
    if (strategyGroup.length === 0) return
    if (!strategyGroup.some((item) => item.id === selectedStrategy)) {
      setSelectedStrategy(strategyGroup[0].id)
      setParams(strategyGroup[0].default_params)
      setParamGrid(buildDefaultParamGrid(strategyGroup[0].default_params))
    }
  }, [selectedStrategy, strategyGroup])

  const setStrategy = (id: string) => {
    setSelectedStrategy(id)
    const next = strategies.find((item) => item.id === id)
    if (next) {
      setParams(next.default_params)
      setParamGrid(buildDefaultParamGrid(next.default_params))
    }
  }

  const setParam = (key: string, value: string) => {
    setParams((previous) => ({ ...previous, [key]: value }))
  }

  const resetResults = () => {
    setClassicResult(null)
    setScanResult(null)
    setCompareResult(null)
    setOptimizeResult(null)
  }

  const run = async () => {
    if (activeTickers.length === 0) {
      setError("请先选择至少一个标的。")
      return
    }
    if (mode !== "compare" && !currentStrategy) {
      setError(mode === "scan" ? "当前没有可用的扫描策略。" : "当前没有可用的经典策略。")
      return
    }
    setLoading(true)
    setError("")
    resetResults()
    try {
      const freshnessResponse = await api.dataFreshness.getPrices(activeTickers, 5)
      setFreshnessItems(freshnessResponse.items)
      const blockingItems = freshnessResponse.items.filter((item) => item.should_block)
      if (blockingItems.length > 0) {
        const sample = blockingItems.slice(0, 4).map((item) => item.ticker).join("、")
        await api.audit
          .recordEvent({
            action: "BACKTEST_BLOCKED_STALE_DATA",
            resource: currentStrategy?.id || mode,
            resource_type: "backtest",
            success: false,
            details: { mode, tickers: blockingItems.map((item) => item.ticker), start_date: startDate, end_date: endDate },
            error_message: "回测标的存在过期或缺失价格数据",
          })
          .catch(() => undefined)
        setError(`已阻止运行：${blockingItems.length} 个标的数据过期或缺失（${sample}），请先更新数据源。`)
        return
      }

      if (mode === "classic" && currentStrategy) {
        const response = await api.backtest.run({
          strategy_id: currentStrategy.id,
          tickers: activeTickers,
          start_date: startDate,
          end_date: endDate || undefined,
          initial_capital: Number(initialCapital),
          params: normalizeParams(params),
        })
        setClassicResult(response)
      } else if (mode === "scan" && currentStrategy) {
        const response = await api.stz.run({
          trade_date: endDate || getTodayInBeijing(),
          mode: "universe",
          selector_names: [currentStrategy.class_name],
          selector_params: { [currentStrategy.class_name]: normalizeParams(params) },
          tickers: activeTickers,
        })
        setScanResult(response)
      } else if (mode === "optimize" && currentStrategy) {
        const grid = parseParamGrid(paramGrid, params)
        const response = await api.backtest.optimize({
          strategy_id: currentStrategy.id,
          tickers: activeTickers,
          param_grid: grid,
          start_date: startDate,
          end_date: endDate || undefined,
          initial_capital: Number(initialCapital),
          objective: optimizeObjective,
          cv_days: Number(optimizeCvDays) || 60,
        })
        setOptimizeResult(response)
      } else {
        if (classicStrategies.length === 0) {
          throw new Error("当前没有可用于对比的经典策略。")
        }
        const response = await api.backtest.runMulti({
          strategies: Object.fromEntries(
            classicStrategies.map((item) => [
              item.id,
              { weight: 1 / classicStrategies.length, params: normalizeParams(item.default_params) },
            ]),
          ),
          tickers: activeTickers,
          start_date: startDate,
          end_date: endDate || undefined,
          initial_capital: Number(initialCapital),
          benchmark_ticker: "000300.SH",
        })
        setCompareResult(response)
      }
      await api.audit
        .recordEvent({
          action: mode === "optimize" ? "BACKTEST_OPTIMIZE" : mode === "scan" ? "BACKTEST_SCAN" : mode === "compare" ? "BACKTEST_COMPARE" : "BACKTEST_RUN",
          resource: currentStrategy?.id || mode,
          resource_type: "backtest",
          details: {
            mode,
            tickers: activeTickers,
            start_date: startDate,
            end_date: endDate || undefined,
            objective: mode === "optimize" ? optimizeObjective : undefined,
            cv_days: mode === "optimize" ? Number(optimizeCvDays) || 60 : undefined,
          },
        })
        .catch(() => undefined)
    } catch (requestError) {
      await api.audit
        .recordEvent({
          action: mode === "optimize" ? "BACKTEST_OPTIMIZE" : mode === "scan" ? "BACKTEST_SCAN" : mode === "compare" ? "BACKTEST_COMPARE" : "BACKTEST_RUN",
          resource: currentStrategy?.id || mode,
          resource_type: "backtest",
          success: false,
          details: { mode, tickers: activeTickers, start_date: startDate, end_date: endDate || undefined },
          error_message: requestError instanceof Error ? requestError.message : "运行失败",
        })
        .catch(() => undefined)
      setError(requestError instanceof Error ? requestError.message : "运行失败")
    } finally {
      setLoading(false)
    }
  }

  const exportReport = async (reportType: "html" | "pdf") => {
    try {
      const response = await api.backtest.export({
        equity_curve: activeEquity,
        trades: activeTrades,
        metrics: activeMetrics,
        report_type: reportType,
        include_charts: true,
      })
      if (response?.download_url) window.open(response.download_url, "_blank")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "导出失败")
    }
  }

  const activeModeMeta = MODE_META[mode]
  const selectedModeIcon = activeModeMeta.icon
  const selectedAssetsLabel = activeTickers.length > 0 ? `${activeTickers.length} 个标的` : "待选择"
  const resultReady = Boolean(classicResult || scanResult || compareResult || optimizeResult)
  const scanRows = ((scanResult?.data as ScanRow[] | undefined) ?? [])

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 md:p-10">
      <section className="space-y-3">
        <h1 className="page-title">回测中心</h1>
        <p className="page-subtitle">
          把策略回测、信号扫描与多策略对比收在同一页里，先定标的与区间，再按模式读取结果，不再来回切换旧入口。
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill label="当前模式" value={activeModeMeta.title} icon={selectedModeIcon} tone={activeModeMeta.tone} />
          <StatusPill label="标的范围" value={selectedAssetsLabel} tone="ink" />
          <span className="text-[0.88rem] leading-6 text-foreground/62">
            {mode === "scan" ? "扫描策略" : "可用经典策略"} {strategyGroup.length} 个
          </span>
        </div>
      </section>

      <SegmentedControl
        value={mode}
        onValueChange={setMode}
        ariaLabel="回测中心模式"
        className="segmented-mobile-grid max-w-full overflow-x-auto"
        itemClassName="sm:min-w-[9.25rem]"
        options={[
          { value: "classic", label: "策略回测", icon: <BarChart3 className="h-4 w-4" /> },
          { value: "scan", label: "信号扫描", icon: <Radar className="h-4 w-4" /> },
          { value: "compare", label: "多策略对比", icon: <Workflow className="h-4 w-4" /> },
          { value: "optimize", label: "参数优化", icon: <SlidersHorizontal className="h-4 w-4" /> },
        ]}
      />

      <GlassCard className="space-y-6 p-5 md:p-6">
        <PanelHeader
          title={activeModeMeta.title}
          description="围绕同一组标的、区间与参数安排回测或扫描，再按当前模式读取结果。"
          meta={<span className="text-[0.84rem] leading-6 text-foreground/60">{resultReady ? "已有结果，可继续调参或切换模式。" : "先确定区间与标的，再运行当前模式。"}</span>}
        />

        <div className="grid min-w-0 gap-6 xl:grid-cols-[0.94fr_1.06fr]">
          <div className="min-w-0 space-y-5">
            {mode === "compare" ? (
              <div className="rounded-[24px] border border-border/60 bg-[rgba(250,246,239,0.44)] px-4 py-4">
                <div className="text-[0.94rem] font-medium text-foreground/84">比较范围</div>
                <p className="mt-2 text-[0.88rem] leading-7 text-foreground/68">
                  当前会对比 {classicStrategies.length} 个经典策略：
                  {classicStrategies.map((item) => item.name).join("、") || "暂无可用策略"}。
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Label>策略</Label>
                <Select value={currentStrategy?.id || ""} onValueChange={setStrategy}>
                  <SelectTrigger className="rounded-2xl border-black/[0.07] bg-white/55">
                    <SelectValue placeholder="请选择策略" />
                  </SelectTrigger>
                  <SelectContent>
                    {strategyGroup.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {currentStrategy?.description ? (
                  <p className="text-sm leading-7 text-foreground/72">{currentStrategy.description}</p>
                ) : null}
                {mode === "optimize" ? (
                  <div className="rounded-[22px] border border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.08)] px-4 py-3 text-sm leading-7 text-foreground/72">
                    参数优化只用于发现候选组合，不等于可实盘采用。请同时查看验证窗口、基准对比、交易成本和样本外表现，避免把历史拟合当成稳定收益。
                  </div>
                ) : null}
              </div>
            )}

            <div className="min-w-0 space-y-2">
              <Label>标的范围</Label>
              {assets.length > 0 ? (
                <MultiAssetPicker
                  assets={assets}
                  selected={selectedTickers}
                  onChange={setSelectedTickers}
                  placeholder="默认使用资产池前 3 项"
                  className="min-w-0"
                  maxPreview={1}
                />
              ) : (
                <Input
                  value={manualTickers}
                  onChange={(event) => setManualTickers(event.target.value)}
                  placeholder="例如 013281,002611,160615"
                  className="rounded-2xl border-black/[0.07] bg-white/55"
                />
              )}
              <p className="text-sm leading-7 text-foreground/72">
                当前使用：{activeTickers.length ? activeTickers.join("、") : "请先选择标的"}
              </p>
            </div>
          </div>

          <div className="min-w-0 space-y-5">
            <div className="grid min-w-0 gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>开始日期</Label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="rounded-2xl border-black/[0.07] bg-white/55"
                />
              </div>
              <div className="space-y-2">
                <Label>{mode === "scan" ? "扫描日期" : "结束日期"}</Label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className="rounded-2xl border-black/[0.07] bg-white/55"
                />
              </div>
              <div className="space-y-2">
                <Label>初始资金</Label>
                <Input
                  type="number"
                  value={initialCapital}
                  onChange={(event) => setInitialCapital(event.target.value)}
                  className="rounded-2xl border-black/[0.07] bg-white/55"
                />
                <p className="text-[0.82rem] leading-6 text-foreground/58">仅影响策略回测和多策略对比，不影响信号扫描结果。</p>
              </div>
            </div>

            {mode !== "compare" && Object.keys(params).length > 0 ? (
              <div className="data-panel-muted rounded-[26px] px-5 py-5">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/82">
                  <Workflow className="h-4 w-4 text-tone-ochre" />
                  {mode === "optimize" ? "参数网格" : "核心参数"}
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {Object.entries(params).map(([key, value]) => (
                    <div key={key} className="space-y-1.5">
                      <Label className="text-[0.86rem] text-foreground/76">{PARAM_LABELS[key] ?? key}</Label>
                      <Input
                        value={mode === "optimize" ? (paramGrid[key] ?? formatCandidateValue(value)) : String(value ?? "")}
                        onChange={(event) => {
                          if (mode === "optimize") {
                            setParamGrid((previous) => ({ ...previous, [key]: event.target.value }))
                          } else {
                            setParam(key, event.target.value)
                          }
                        }}
                        placeholder={mode === "optimize" ? "例如 5, 10, 20" : undefined}
                        className="rounded-2xl border-black/[0.07] bg-white/68"
                      />
                      {mode === "optimize" ? (
                        <p className="text-[0.78rem] leading-5 text-foreground/54">候选值用逗号分隔。</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {mode === "optimize" ? (
              <div className="grid gap-4 rounded-[26px] border border-border/60 bg-background/45 p-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>优化目标</Label>
                  <Select value={optimizeObjective} onValueChange={setOptimizeObjective}>
                    <SelectTrigger className="rounded-2xl border-black/[0.07] bg-white/55">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="trading_objective">综合交易目标</SelectItem>
                      <SelectItem value="sharpe_ratio">夏普比率</SelectItem>
                      <SelectItem value="sortino_ratio">索提诺比率</SelectItem>
                      <SelectItem value="total_return">总收益</SelectItem>
                      <SelectItem value="calmar_ratio">Calmar 比率</SelectItem>
                      <SelectItem value="max_drawdown">最大回撤</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>验证窗口天数</Label>
                  <Input
                    type="number"
                    value={optimizeCvDays}
                    onChange={(event) => setOptimizeCvDays(event.target.value)}
                    className="rounded-2xl border-black/[0.07] bg-white/55"
                  />
                </div>
              </div>
            ) : null}

            <div className="grid min-w-0 gap-3 sm:flex sm:flex-wrap sm:items-center">
              <Button className="w-full min-w-0 sm:w-auto" onClick={() => void run()} disabled={loading}>
                {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                {mode === "classic" ? "开始回测" : mode === "scan" ? "运行扫描" : mode === "optimize" ? "开始优化" : "开始对比"}
              </Button>
              <Button className="w-full min-w-0 sm:w-auto" size="sm" variant="outline" onClick={resetResults}>
                清空结果
              </Button>
              <span className="text-[0.84rem] leading-6 text-foreground/58 sm:max-w-md">结果区会保留当前模式输出，便于你连续调参与比较。</span>
            </div>
          </div>
        </div>
      </GlassCard>

      {error ? (
        <div className="surface-tone-cinnabar rounded-[24px] border px-4 py-3 text-sm leading-7">{error}</div>
      ) : null}

      {freshnessItems.length > 0 ? (
        <GlassCard className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-medium text-foreground/84">本次运行数据新鲜度</div>
            <span className="text-xs text-muted-foreground">
              {freshnessItems.filter((item) => item.is_stale).length} 个过期 / {freshnessItems.length} 个已检查
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {freshnessItems.slice(0, 8).map((item) => (
              <span
                key={item.ticker}
                className={`rounded-full border px-3 py-1 text-xs ${
                  item.is_stale
                    ? "border-[rgba(var(--rgb-cinnabar),0.16)] bg-[rgba(var(--rgb-cinnabar),0.08)] text-tone-cinnabar"
                    : "border-[rgba(var(--rgb-celadon),0.16)] bg-[rgba(var(--rgb-celadon),0.08)] text-tone-celadon"
                }`}
              >
                {item.ticker} · {item.last_date ?? "-"}
              </span>
            ))}
          </div>
        </GlassCard>
      ) : null}

      {classicResult || compareResult || optimizeResult ? (
        <div className="space-y-5">
          <PanelHeader
            title={optimizeResult ? "参数优化结果" : compareResult ? "多策略对比结果" : "策略回测结果"}
            description={
              optimizeResult
                ? "先看最优参数和评分，再用权益曲线判断这组参数是否只是短期拟合。"
                : compareResult
                ? "先看组合总结果，再看不同经典策略在同一组资产上的差异。"
                : "围绕收益、回撤、波动率和交易记录判断策略是否匹配你的预期。"
            }
            meta={
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => void exportReport("html")}>
                  <Download className="mr-2 h-4 w-4" />
                  导出 HTML
                </Button>
                <Button variant="outline" onClick={() => void exportReport("pdf")}>
                  <Download className="mr-2 h-4 w-4" />
                  导出 PDF
                </Button>
              </div>
            }
          />

          <div className="grid gap-4 md:grid-cols-4">
            <SummaryMetric
              label="总收益"
              value={formatPercent(activeMetrics.total_return || 0)}
              tone={(activeMetrics.total_return || 0) >= 0 ? "positive" : "negative"}
              help={GLOSSARY.TotalReturn.definition}
            />
            <SummaryMetric
              label="夏普比率"
              value={(activeMetrics.sharpe_ratio || 0).toFixed(2)}
              accentColor={SONG_COLORS.indigo}
              help={GLOSSARY.SharpeRatio.definition}
            />
            <SummaryMetric
              label="最大回撤"
              value={formatPercent(activeMetrics.max_drawdown || 0)}
              accentColor={SONG_COLORS.cinnabar}
              help={GLOSSARY.MaxDrawdown.definition}
            />
            <SummaryMetric
              label="波动率"
              value={formatPercent(activeMetrics.volatility || 0)}
              help={GLOSSARY.Volatility.definition}
            />
          </div>

          <EquityChart data={activeEquity} />

          {optimizeResult ? (
            <GlassCard className="space-y-4 p-5">
              <PanelHeader
                title="候选参数排序"
                description="最优参数只是起点，建议重点比较候选组合之间的分数差距，避免只追逐单次样本。"
                meta={<StatusPill label="目标" value={optimizeResult.objective} tone="ochre" />}
              />
              <div className="grid gap-3 md:grid-cols-[0.9fr_1.1fr]">
                <div className="rounded-[24px] border border-border/60 bg-muted/20 p-4">
                  <div className="text-sm text-muted-foreground">最优参数</div>
                  <div className="mt-3 space-y-2">
                    {Object.entries(optimizeResult.best_params || {}).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-4 rounded-2xl bg-background/55 px-3 py-2 text-sm">
                        <span className="text-foreground/66">{PARAM_LABELS[key] ?? key}</span>
                        <span className="font-mono font-semibold">{String(value)}</span>
                      </div>
                    ))}
                    {Object.keys(optimizeResult.best_params || {}).length === 0 ? (
                      <div className="text-sm text-muted-foreground">当前没有返回最优参数。</div>
                    ) : null}
                  </div>
                  <div className="mt-4 rounded-2xl bg-background/55 px-3 py-2">
                    <div className="text-xs text-muted-foreground">最优评分</div>
                    <div className="mt-1 text-2xl font-semibold tabular-nums">{Number(optimizeResult.best_score || 0).toFixed(4)}</div>
                  </div>
                </div>
                <div className="hidden overflow-hidden rounded-2xl border border-border/60 md:block">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>参数组合</TableHead>
                        <TableHead className="text-right">评分</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(optimizeResult.all_results || []).slice(0, 12).map((row, index) => (
                        <TableRow key={`${row.params}-${index}`}>
                          <TableCell className="font-mono text-[0.84rem]">{row.params}</TableCell>
                          <TableCell className="text-right tabular-nums">{Number(row.score || 0).toFixed(4)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
              <div className="space-y-2 md:hidden">
                {(optimizeResult.all_results || []).slice(0, 8).map((row, index) => (
                  <div key={`${row.params}-${index}`} className="rounded-2xl border border-border/60 bg-muted/20 p-3">
                    <div className="font-mono text-sm">{row.params}</div>
                    <div className="mt-2 text-right text-sm font-semibold tabular-nums">{Number(row.score || 0).toFixed(4)}</div>
                  </div>
                ))}
              </div>
            </GlassCard>
          ) : null}

          {!optimizeResult ? (
          <GlassCard className="space-y-4 p-5">
            <PanelHeader
              title="交易记录"
              description="用交易频率、方向切换与手续费节奏判断策略是否存在过度交易。"
            />
            {activeTrades.length > 0 ? (
              <div className="space-y-3 lg:hidden">
                {activeTrades.map((trade, index) => (
                  <div key={`${trade.symbol}-${trade.timestamp}-${index}`} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-mono text-base font-semibold">{trade.symbol}</div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {formatDateInBeijing(trade.timestamp, {}, trade.timestamp)}
                        </div>
                      </div>
                      <div className={trade.side === "BUY" ? "text-tone-positive" : "text-tone-negative"}>
                        {trade.side === "BUY" ? "买入" : "卖出"}
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                      <div className="rounded-xl bg-background/50 px-3 py-2">
                        <div className="text-xs text-muted-foreground">价格</div>
                        <div className="mt-1 font-medium">{formatCurrency(Number(trade.price || 0))}</div>
                      </div>
                      <div className="rounded-xl bg-background/50 px-3 py-2">
                        <div className="text-xs text-muted-foreground">数量</div>
                        <div className="mt-1 font-medium tabular-nums">{trade.quantity}</div>
                      </div>
                      <div className="rounded-xl bg-background/50 px-3 py-2">
                        <div className="text-xs text-muted-foreground">手续费</div>
                        <div className="mt-1 font-medium">{formatCurrency(Number(trade.commission || 0))}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState description="当前结果还没有交易记录。" />
            )}
            {activeTrades.length > 0 ? (
              <div className="hidden overflow-hidden rounded-2xl border border-border/60 lg:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>代码</TableHead>
                      <TableHead>方向</TableHead>
                      <TableHead className="text-right">价格</TableHead>
                      <TableHead className="text-right">数量</TableHead>
                      <TableHead className="text-right">手续费</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {activeTrades.map((trade, index) => (
                      <TableRow key={`${trade.symbol}-${trade.timestamp}-${index}`}>
                        <TableCell className="font-mono text-[0.86rem]">
                          {formatDateInBeijing(trade.timestamp, {}, trade.timestamp)}
                        </TableCell>
                        <TableCell className="font-medium">{trade.symbol}</TableCell>
                        <TableCell className={trade.side === "BUY" ? "text-tone-positive" : "text-tone-negative"}>
                          {trade.side === "BUY" ? "买入" : "卖出"}
                        </TableCell>
                        <TableCell className="text-right">{formatCurrency(Number(trade.price || 0))}</TableCell>
                        <TableCell className="text-right">{trade.quantity}</TableCell>
                        <TableCell className="text-right">{formatCurrency(Number(trade.commission || 0))}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : null}
          </GlassCard>
          ) : null}
        </div>
      ) : null}

      {scanResult ? (
        <GlassCard className="space-y-4 p-5">
          <PanelHeader
            title="扫描结果"
            description="只展示当前命中的候选标的，便于先做筛选，再决定是否进入回测。"
            meta={<StatusPill label="命中数量" value={`${scanResult.count} 条`} tone="ochre" />}
          />
          {scanRows.length > 0 ? (
            <div className="space-y-3 lg:hidden">
              {scanRows.map((row, index) => (
                <div key={`${row.ticker}-${index}`} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-mono text-base font-semibold">{row.ticker}</div>
                      <div className="mt-1 truncate text-sm text-muted-foreground">{row.name || "未命名标的"}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">收盘价</div>
                      <div className="mt-1 font-semibold tabular-nums">
                        {row.last_close != null ? formatCurrency(Number(row.last_close)) : "-"}
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 rounded-xl bg-background/50 px-3 py-2 text-sm text-foreground/72">
                    扫描器：{row.selector_alias || currentStrategy?.name || "扫描策略"}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState description="当前条件下还没有筛选到符合要求的标的。" />
          )}
          {scanRows.length > 0 ? (
            <div className="hidden overflow-hidden rounded-2xl border border-border/60 lg:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>代码</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead>扫描器</TableHead>
                    <TableHead className="text-right">收盘价</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {scanRows.map((row, index) => (
                    <TableRow key={`${row.ticker}-${index}`}>
                      <TableCell className="font-mono">{row.ticker}</TableCell>
                      <TableCell>{row.name || "-"}</TableCell>
                      <TableCell>{row.selector_alias || currentStrategy?.name || "扫描策略"}</TableCell>
                      <TableCell className="text-right">
                        {row.last_close != null ? formatCurrency(Number(row.last_close)) : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </GlassCard>
      ) : null}

      {!classicResult && !scanResult && !compareResult && !optimizeResult ? (
        <GlassCard className="p-6">
          <EmptyState
            title="尚未生成结果"
            description={activeModeMeta.emptyDescription}
          />
        </GlassCard>
      ) : null}
    </div>
  )
}

export default BacktestCenterWorkspace
