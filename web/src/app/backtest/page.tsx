"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { BarChart3, Download, Play, Radar, RefreshCw, Sparkles, Workflow } from "lucide-react"
import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { MultiAssetPicker } from "@/components/shared/multi-asset-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api, type Asset, type BacktestRunResponse, type RunStrategyResult, type UnknownRecord } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { GLOSSARY } from "@/lib/glossary"
import { formatCurrency, formatPercent } from "@/lib/utils"

type Mode = "classic" | "scan" | "compare"
type Params = Record<string, string | number | boolean | null>
type Strategy = { id: string; name: string; description: string; category: "classic" | "stz"; default_params: Params; class_name: string }
type EquityPoint = { date: string; equity: number }
type TradeRecord = { timestamp: string; symbol: string; side: "BUY" | "SELL"; price: number; quantity: number; commission: number }
type ScanRow = { ticker: string; name?: string; selector_alias?: string; last_close?: number }

const PARAM_LABELS: Record<string, string> = { short_window: "短均线", long_window: "长均线", window: "回看窗口", std_dev: "标准差", fast: "快线", slow: "慢线", signal: "信号线", threshold: "阈值", holding_days: "持有天数" }
const DEFAULT_METRICS = { total_return: 0, sharpe_ratio: 0, max_drawdown: 0, volatility: 0 }

function normalizeStrategy(row: UnknownRecord): Strategy | null {
  const id = typeof row.id === "string" ? row.id : ""
  if (!id) return null
  const rawParams = row.default_params && typeof row.default_params === "object" ? (row.default_params as Record<string, unknown>) : {}
  return {
    id,
    name: typeof row.name === "string" ? row.name : id,
    description: typeof row.description === "string" ? row.description : "",
    category: row.category === "stz" ? "stz" : "classic",
    default_params: Object.fromEntries(Object.entries(rawParams).map(([key, value]) => [key, typeof value === "object" ? null : (value as string | number | boolean | null)])),
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

function Metric({ label, value, tone = SONG_COLORS.ink, help }: { label: string; value: string; tone?: string; help?: string }) {
  return (
    <GlassCard className="space-y-2 p-4">
      <div className="flex items-center gap-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        <span>{label}</span>
        {help ? <HelpTooltip content={help} /> : null}
      </div>
      <div className="text-2xl font-semibold tracking-[-0.04em]" style={{ color: tone }}>{value}</div>
    </GlassCard>
  )
}

function EquityChart({ data }: { data: EquityPoint[] }) {
  if (data.length === 0) {
    return <GlassCard className="flex h-[320px] items-center justify-center p-6 text-sm text-muted-foreground">暂无权益曲线数据。</GlassCard>
  }
  const values = data.map((item) => item.equity)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max((max - min) * 0.12, max * 0.01)
  return (
    <GlassCard className="space-y-4 p-5">
      <div className="space-y-1">
        <CardTitle>权益曲线</CardTitle>
        <CardDescription>Y 轴会随当前数据自动缩放，便于观察波动。</CardDescription>
      </div>
      <div className="h-[280px]">
        <MeasuredChart height={280}>
          {(width, height) => (
            <AreaChart width={width} height={height} data={data}>
              <defs>
                <linearGradient id="bt-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SONG_COLORS.indigo} stopOpacity={0.24} />
                  <stop offset="100%" stopColor={SONG_COLORS.indigo} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={SONG_COLORS.grid} vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={36} stroke={SONG_COLORS.axis} />
              <YAxis tickLine={false} axisLine={false} stroke={SONG_COLORS.axis} domain={[Math.max(0, min - pad), max + pad]} tickFormatter={(v) => `¥${(Number(v) / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(value) => [formatCurrency(Number(value)), "权益"]} labelFormatter={(label) => `日期：${label}`} contentStyle={{ borderRadius: 18, border: "1px solid rgba(0,0,0,0.06)", backgroundColor: "rgba(255,255,255,0.95)" }} />
              <Area type="monotone" dataKey="equity" stroke={SONG_COLORS.indigo} strokeWidth={2.2} fill="url(#bt-fill)" />
            </AreaChart>
          )}
        </MeasuredChart>
      </div>
    </GlassCard>
  )
}

export default function BacktestPage() {
  const [mode, setMode] = useState<Mode>("classic")
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [manualTickers, setManualTickers] = useState("")
  const [selectedStrategy, setSelectedStrategy] = useState("")
  const [startDate, setStartDate] = useState("2024-01-01")
  const [endDate, setEndDate] = useState("")
  const [initialCapital, setInitialCapital] = useState("100000")
  const [params, setParams] = useState<Params>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [classicResult, setClassicResult] = useState<BacktestRunResponse | null>(null)
  const [scanResult, setScanResult] = useState<RunStrategyResult | null>(null)
  const [compareResult, setCompareResult] = useState<BacktestRunResponse | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const [rows, pool, personalAssets] = await Promise.all([
          api.backtest.listStrategies(),
          api.stz.getAssetPool().catch(() => []),
          api.user.assets.getOverview(false).catch(() => ({ assets: [] })),
        ])
        const parsed = (rows || []).map((row) => normalizeStrategy(row as UnknownRecord)).filter((row): row is Strategy => row !== null)
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
        const firstClassic = parsed.find((item) => item.category === "classic") ?? parsed[0]
        if (firstClassic) {
          setSelectedStrategy(firstClassic.id)
          setParams(firstClassic.default_params)
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "读取回测配置失败")
      }
    })()
  }, [])

  useEffect(() => {
    if (assets.length > 0 && selectedTickers.length === 0) {
      setSelectedTickers(assets.slice(0, 3).map((asset) => asset.ticker))
    }
  }, [assets, selectedTickers.length])

  const classicStrategies = useMemo(() => strategies.filter((item) => item.category === "classic"), [strategies])
  const scanStrategies = useMemo(() => strategies.filter((item) => item.category === "stz"), [strategies])
  const strategyGroup = mode === "scan" ? scanStrategies : classicStrategies
  const currentStrategy = strategyGroup.find((item) => item.id === selectedStrategy) ?? strategyGroup[0] ?? null
  const activeTickers = selectedTickers.length > 0 ? selectedTickers : manualTickers.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean)
  const activeMetrics = (classicResult?.metrics || compareResult?.portfolio?.metrics || DEFAULT_METRICS) as Record<string, number>
  const activeEquity = ((classicResult?.equity_curve || compareResult?.portfolio?.equity_curve || []) as EquityPoint[])
  const activeTrades = ((classicResult?.trades || compareResult?.portfolio?.trades || []) as TradeRecord[])

  useEffect(() => {
    if (strategyGroup.length === 0) return
    if (!strategyGroup.some((item) => item.id === selectedStrategy)) {
      setSelectedStrategy(strategyGroup[0].id)
      setParams(strategyGroup[0].default_params)
    }
  }, [selectedStrategy, strategyGroup])

  const setStrategy = (id: string) => {
    setSelectedStrategy(id)
    const next = strategies.find((item) => item.id === id)
    if (next) setParams(next.default_params)
  }

  const setParam = (key: string, value: string) => {
    setParams((previous) => ({ ...previous, [key]: value }))
  }

  const resetResults = () => {
    setClassicResult(null)
    setScanResult(null)
    setCompareResult(null)
  }

  const run = async () => {
    if (activeTickers.length === 0) {
      setError("请先选择至少一个标的。")
      return
    }
    setLoading(true)
    setError("")
    resetResults()
    try {
      if (mode === "classic" && currentStrategy) {
        const response = await api.backtest.run({ strategy_id: currentStrategy.id, tickers: activeTickers, start_date: startDate, end_date: endDate || undefined, initial_capital: Number(initialCapital), params: normalizeParams(params) })
        setClassicResult(response)
      } else if (mode === "scan" && currentStrategy) {
        const response = await api.stz.run({ trade_date: endDate || new Date().toISOString().split("T")[0], mode: "universe", selector_names: [currentStrategy.class_name], selector_params: { [currentStrategy.class_name]: normalizeParams(params) }, tickers: activeTickers })
        setScanResult(response)
      } else {
        const response = await api.backtest.runMulti({
          strategies: Object.fromEntries(classicStrategies.map((item) => [item.id, { weight: 1 / classicStrategies.length, params: normalizeParams(item.default_params) }])),
          tickers: activeTickers,
          start_date: startDate,
          end_date: endDate || undefined,
          initial_capital: Number(initialCapital),
          benchmark_ticker: "000300.SH",
        })
        setCompareResult(response)
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "运行失败")
    } finally {
      setLoading(false)
    }
  }

  const exportReport = async (reportType: "html" | "pdf") => {
    try {
      const response = await api.backtest.export({ equity_curve: activeEquity, trades: activeTrades, metrics: activeMetrics, report_type: reportType, include_charts: true })
      if (response?.download_url) window.open(response.download_url, "_blank")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "导出失败")
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8 md:space-y-12 p-6 md:p-10">
      <section className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/60 px-3 py-1 text-xs">回测中心</Badge>
          <Badge variant="outline" className="rounded-full border-black/[0.05] bg-white/45 px-3 py-1 text-xs text-muted-foreground">回测 / 扫描 / 对比</Badge>
        </div>
        <h1 className="text-3xl font-medium tracking-wide text-foreground/90">把回测流程拆成三件清楚的事</h1>
        <p className="max-w-4xl text-base font-light tracking-wide text-foreground/60">策略回测看单一策略，信号扫描看当期候选，多策略对比看风格差异。不再把所有控件挤在一个侧栏里。</p>
      </section>

      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline"><Link href="/backtest">历史回测</Link></Button>
        <Button asChild variant="outline"><Link href="/portfolio-backtest">组合回测</Link></Button>
        <Button asChild variant="outline"><Link href="/backtest/optimizer">参数优化</Link></Button>
      </div>

      <Tabs value={mode} onValueChange={(value) => setMode(value as Mode)} className="space-y-8">
        <TabsList className="h-auto flex-wrap rounded-[24px] bg-white/40 backdrop-blur-md border border-white/60 p-2 shadow-[0_4px_16px_rgba(0,0,0,0.02)]">
          <TabsTrigger value="classic" className="gap-2 rounded-[18px] px-4 py-2.5"><BarChart3 className="h-4 w-4" />策略回测</TabsTrigger>
          <TabsTrigger value="scan" className="gap-2 rounded-[18px] px-4 py-2.5"><Radar className="h-4 w-4" />信号扫描</TabsTrigger>
          <TabsTrigger value="compare" className="gap-2 rounded-[18px] px-4 py-2.5"><Workflow className="h-4 w-4" />多策略对比</TabsTrigger>
        </TabsList>

        <TabsContent value={mode} className="space-y-5">
          <GlassCard className="space-y-8 p-6 md:p-8 border-white/40 bg-white/30 backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
            <div className="grid gap-8 md:gap-12 xl:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-4">
                <div className="space-y-1">
                  <CardTitle>{mode === "classic" ? "选择一个经典策略" : mode === "scan" ? "选择一个 STZ 扫描器" : "自动对比全部经典策略"}</CardTitle>
                  <CardDescription>{mode === "classic" ? "适合验证历史收益、回撤与交易记录。" : mode === "scan" ? "适合快速发现当前候选标的，不输出权益曲线。" : "适合判断哪一类经典策略更稳健。"} </CardDescription>
                </div>
                {mode === "compare" ? (
                  <div className="rounded-[24px] border border-black/[0.05] bg-white/55 px-4 py-4 text-sm leading-7 text-muted-foreground">
                    当前会对比 {classicStrategies.length} 个经典策略：{classicStrategies.map((item) => item.name).join("、") || "暂无可用策略"}。
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Label>策略</Label>
                    <Select value={currentStrategy?.id || ""} onValueChange={setStrategy}>
                      <SelectTrigger className="rounded-2xl border-black/[0.07] bg-white/55"><SelectValue placeholder="请选择策略" /></SelectTrigger>
                      <SelectContent>{strategyGroup.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}</SelectContent>
                    </Select>
                    {currentStrategy?.description ? <p className="text-[12px] leading-6 text-muted-foreground">{currentStrategy.description}</p> : null}
                  </div>
                )}
                <div className="space-y-2">
                  <Label>标的</Label>
                  {assets.length > 0 ? <MultiAssetPicker assets={assets} selected={selectedTickers} onChange={setSelectedTickers} placeholder="默认使用资产池前 3 项" maxPreview={3} /> : <Input value={manualTickers} onChange={(event) => setManualTickers(event.target.value)} placeholder="例如 013281,002611,160615" className="rounded-2xl border-black/[0.07] bg-white/55" />}
                  <p className="text-[12px] leading-6 text-muted-foreground">当前使用：{activeTickers.length ? activeTickers.join("、") : "请先选择标的"}</p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2"><Label>开始日期</Label><Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="rounded-2xl border-black/[0.07] bg-white/55" /></div>
                  <div className="space-y-2"><Label>{mode === "scan" ? "扫描日期" : "结束日期"}</Label><Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="rounded-2xl border-black/[0.07] bg-white/55" /></div>
                  <div className="space-y-2"><Label>初始资金<HelpTooltip content="仅影响经典回测和多策略对比。" /></Label><Input type="number" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} className="rounded-2xl border-black/[0.07] bg-white/55" /></div>
                </div>

                {mode !== "compare" && Object.keys(params).length > 0 ? (
                  <div className="rounded-[24px] border border-black/[0.05] bg-white/45 p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/82"><Workflow className="h-4 w-4" style={{ color: SONG_COLORS.ochre }} />核心参数</div>
                    <div className="grid gap-4 md:grid-cols-2">
                      {Object.entries(params).map(([key, value]) => (
                        <div key={key} className="space-y-1.5">
                          <Label className="text-xs font-medium">{PARAM_LABELS[key] ?? key}</Label>
                          <Input value={String(value ?? "")} onChange={(event) => setParam(key, event.target.value)} className="rounded-2xl border-black/[0.07] bg-white/70" />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => void run()} disabled={loading}>{loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}{mode === "classic" ? "开始回测" : mode === "scan" ? "运行扫描" : "开始对比"}</Button>
                  <Button variant="outline" onClick={resetResults}>清空结果</Button>
                </div>
              </div>
            </div>
          </GlassCard>
        </TabsContent>
      </Tabs>

      {error ? <div className="rounded-[26px] border px-4 py-4 text-sm leading-7" style={{ borderColor: "rgba(182,69,60,0.18)", color: SONG_COLORS.negative, backgroundColor: "rgba(182,69,60,0.08)" }}>{error}</div> : null}

      {(classicResult || compareResult) ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1"><CardTitle>{compareResult ? "组合对比结果" : "策略回测结果"}</CardTitle><CardDescription>{compareResult ? "先看组合总结果，再看各经典策略差异。" : "看收益、回撤、波动率与交易记录是否匹配你的预期。"} </CardDescription></div>
            <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void exportReport("html")}><Download className="mr-2 h-4 w-4" />导出 HTML</Button><Button variant="outline" onClick={() => void exportReport("pdf")}><Download className="mr-2 h-4 w-4" />导出 PDF</Button></div>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            <Metric label="总收益" value={formatPercent(activeMetrics.total_return || 0)} tone={(activeMetrics.total_return || 0) >= 0 ? SONG_COLORS.positive : SONG_COLORS.negative} help={GLOSSARY.TotalReturn.definition} />
            <Metric label="夏普比率" value={(activeMetrics.sharpe_ratio || 0).toFixed(2)} tone={SONG_COLORS.indigo} help={GLOSSARY.SharpeRatio.definition} />
            <Metric label="最大回撤" value={formatPercent(activeMetrics.max_drawdown || 0)} tone={SONG_COLORS.negative} help={GLOSSARY.MaxDrawdown.definition} />
            <Metric label="波动率" value={formatPercent(activeMetrics.volatility || 0)} help={GLOSSARY.Volatility.definition} />
          </div>
          <EquityChart data={activeEquity} />
          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1"><CardTitle>交易记录</CardTitle><CardDescription>判断策略是否存在过度交易或节奏失衡。</CardDescription></div>
            {activeTrades.length > 0 ? (
              <div className="overflow-x-auto rounded-[24px] border border-black/[0.05] bg-white/45">
                <table className="w-full min-w-[680px] text-sm">
                  <thead><tr className="border-b border-black/[0.05] text-left text-[12px] uppercase tracking-[0.12em] text-muted-foreground"><th className="px-4 py-3">日期</th><th className="px-4 py-3">代码</th><th className="px-4 py-3">方向</th><th className="px-4 py-3 text-right">价格</th><th className="px-4 py-3 text-right">数量</th><th className="px-4 py-3 text-right">手续费</th></tr></thead>
                  <tbody>{activeTrades.map((trade, index) => <tr key={`${trade.symbol}-${trade.timestamp}-${index}`} className="border-b border-black/[0.04] last:border-b-0"><td className="px-4 py-3 font-mono text-[12px] text-foreground/70">{new Date(trade.timestamp).toLocaleDateString("zh-CN")}</td><td className="px-4 py-3 font-medium text-foreground/82">{trade.symbol}</td><td className="px-4 py-3 font-medium" style={{ color: trade.side === "BUY" ? SONG_COLORS.negative : SONG_COLORS.positive }}>{trade.side === "BUY" ? "买入" : "卖出"}</td><td className="px-4 py-3 text-right">{formatCurrency(Number(trade.price || 0))}</td><td className="px-4 py-3 text-right">{trade.quantity}</td><td className="px-4 py-3 text-right">{formatCurrency(Number(trade.commission || 0))}</td></tr>)}</tbody>
                </table>
              </div>
            ) : <div className="rounded-[22px] border border-dashed border-black/[0.08] bg-white/40 px-4 py-8 text-center text-sm text-muted-foreground">当前结果没有交易记录。</div>}
          </GlassCard>
        </div>
      ) : null}

      {scanResult ? (
        <GlassCard className="space-y-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1"><CardTitle>扫描结果</CardTitle><CardDescription>STZ 扫描只关心当前命中的候选标的，不强行展示权益曲线。</CardDescription></div>
            <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/60 px-3 py-1 text-xs">{scanResult.count} 条信号</Badge>
          </div>
          {(scanResult.data as ScanRow[]).length > 0 ? (
            <div className="overflow-x-auto rounded-[24px] border border-black/[0.05] bg-white/45">
              <table className="w-full min-w-[640px] text-sm">
                <thead><tr className="border-b border-black/[0.05] text-left text-[12px] uppercase tracking-[0.12em] text-muted-foreground"><th className="px-4 py-3">代码</th><th className="px-4 py-3">名称</th><th className="px-4 py-3">扫描器</th><th className="px-4 py-3 text-right">收盘价</th></tr></thead>
                <tbody>{(scanResult.data as ScanRow[]).map((row, index) => <tr key={`${row.ticker}-${index}`} className="border-b border-black/[0.04] last:border-b-0"><td className="px-4 py-3 font-mono">{row.ticker}</td><td className="px-4 py-3">{row.name || "-"}</td><td className="px-4 py-3">{row.selector_alias || currentStrategy?.name || "STZ"}</td><td className="px-4 py-3 text-right">{row.last_close != null ? formatCurrency(Number(row.last_close)) : "-"}</td></tr>)}</tbody>
              </table>
            </div>
          ) : <div className="rounded-[22px] border border-dashed border-black/[0.08] bg-white/40 px-4 py-8 text-center text-sm text-muted-foreground">当前条件下没有筛选到符合要求的标的。</div>}
        </GlassCard>
      ) : null}

      {!classicResult && !scanResult && !compareResult ? (
        <GlassCard className="p-6">
          <div className="flex items-start gap-4">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl" style={{ backgroundColor: "rgba(111,124,142,0.12)", color: SONG_COLORS.indigo }}><Sparkles className="h-5 w-5" /></div>
            <div className="space-y-2"><CardTitle>第一次使用建议</CardTitle><p className="text-sm leading-7 text-muted-foreground">先用“策略回测”验证一个经典策略，再切到“多策略对比”看风格差异；若你只想找今天的候选标的，就用“信号扫描”。</p></div>
          </div>
        </GlassCard>
      ) : null}
    </div>
  )
}
