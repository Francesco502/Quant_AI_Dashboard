"use client"

import { useEffect, useMemo, useState } from "react"
import { BarChart3, Download, Play, Radar, RefreshCw, Workflow } from "lucide-react"
import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { EmptyState } from "@/components/data/empty-state"
import { MetricCard } from "@/components/data/metric-card"
import { PanelHeader } from "@/components/data/panel-header"
import { StatusPill } from "@/components/data/status-pill"
import { MultiAssetPicker } from "@/components/shared/multi-asset-picker"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, type Asset, type BacktestRunResponse, type RunStrategyResult, type UnknownRecord } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { GLOSSARY } from "@/lib/glossary"
import { formatDateInBeijing, getTodayInBeijing } from "@/lib/time"
import { formatCurrency, formatPercent } from "@/lib/utils"

type Mode = "classic" | "scan" | "compare"
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

function SummaryMetric({
  label,
  value,
  tone = "default",
  accentColor,
  help,
  secondary,
}: {
  label: string
  value: string
  tone?: "default" | "positive" | "negative" | "accent"
  accentColor?: string
  help?: string
  secondary?: string
}) {
  return (
    <MetricCard
      label={label}
      value={value}
      tone={tone}
      accentColor={accentColor}
      help={help}
      secondary={secondary}
      compact
      surface="muted"
      className="h-full rounded-[24px]"
      valueClassName="mt-2 text-[1.44rem] font-semibold tracking-[-0.03em]"
    />
  )
}

function EquityChart({ data }: { data: EquityPoint[] }) {
  if (data.length === 0) {
    return (
      <GlassCard className="p-6">
        <EmptyState
          title="暂无权益曲线"
          description="当前结果还没有足够的权益点可以绘制曲线。"
        />
      </GlassCard>
    )
  }

  const values = data.map((item) => item.equity)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max((max - min) * 0.12, max * 0.01)

  return (
    <GlassCard className="space-y-4 p-5">
      <PanelHeader
        title="权益曲线"
        description="Y 轴会随当前样本自动缩放，便于观察回撤与趋势切换。"
      />
      <div className="h-[280px]">
        <MeasuredChart height={280}>
          {(width, height) => (
            <AreaChart width={width} height={height} data={data}>
              <defs>
                <linearGradient id="bt-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SONG_COLORS.indigo} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={SONG_COLORS.indigo} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={SONG_COLORS.grid} vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={36} stroke={SONG_COLORS.axis} />
              <YAxis
                tickLine={false}
                axisLine={false}
                stroke={SONG_COLORS.axis}
                domain={[Math.max(0, min - pad), max + pad]}
                tickFormatter={(value) => `¥${(Number(value) / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(value) => [formatCurrency(Number(value)), "权益"]}
                labelFormatter={(label) => `日期：${label}`}
                contentStyle={{
                  borderRadius: 18,
                  border: "1px solid rgba(77,71,66,0.08)",
                  backgroundColor: "rgba(255,255,255,0.94)",
                }}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke={SONG_COLORS.indigo}
                strokeWidth={2.2}
                fill="url(#bt-fill)"
              />
            </AreaChart>
          )}
        </MeasuredChart>
      </div>
    </GlassCard>
  )
}

export function BacktestCenterWorkspace() {
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
    (classicResult?.metrics || compareResult?.portfolio?.metrics || DEFAULT_METRICS) as Record<string, number>
  const activeEquity = (classicResult?.equity_curve ||
    compareResult?.portfolio?.equity_curve ||
    []) as EquityPoint[]
  const activeTrades = (classicResult?.trades || compareResult?.portfolio?.trades || []) as TradeRecord[]

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
      } else {
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
    } catch (requestError) {
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
  const resultReady = Boolean(classicResult || scanResult || compareResult)
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
            {mode === "scan" ? "扫描策略" : "可用策略"} {strategyGroup.length} 个
          </span>
        </div>
      </section>

      <Tabs value={mode} onValueChange={(value) => setMode(value as Mode)} className="space-y-4">
        <TabsList className="inline-flex h-auto w-auto max-w-full justify-start gap-1.5 overflow-x-auto rounded-[22px] border border-black/[0.05] bg-[rgba(249,245,239,0.78)] p-1.5 shadow-none">
          <TabsTrigger value="classic" className="gap-2 rounded-[18px] px-4 py-2.5">
            <BarChart3 className="h-4 w-4" />
            策略回测
          </TabsTrigger>
          <TabsTrigger value="scan" className="gap-2 rounded-[18px] px-4 py-2.5">
            <Radar className="h-4 w-4" />
            信号扫描
          </TabsTrigger>
          <TabsTrigger value="compare" className="gap-2 rounded-[18px] px-4 py-2.5">
            <Workflow className="h-4 w-4" />
            多策略对比
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <GlassCard className="space-y-6 p-5 md:p-6">
        <PanelHeader
          title={activeModeMeta.title}
          description="围绕同一组标的、区间与参数安排回测或扫描，再按当前模式读取结果。"
          meta={<span className="text-[0.84rem] leading-6 text-foreground/60">{resultReady ? "已有结果，可继续调参或切换模式。" : "先确定区间与标的，再运行当前模式。"}</span>}
        />

        <div className="grid gap-6 xl:grid-cols-[0.94fr_1.06fr]">
          <div className="space-y-5">
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
              </div>
            )}

            <div className="space-y-2">
              <Label>标的范围</Label>
              {assets.length > 0 ? (
                <MultiAssetPicker
                  assets={assets}
                  selected={selectedTickers}
                  onChange={setSelectedTickers}
                  placeholder="默认使用资产池前 3 项"
                  maxPreview={4}
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

          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-3">
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
                  核心参数
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {Object.entries(params).map(([key, value]) => (
                    <div key={key} className="space-y-1.5">
                      <Label className="text-[0.86rem] text-foreground/76">{PARAM_LABELS[key] ?? key}</Label>
                      <Input
                        value={String(value ?? "")}
                        onChange={(event) => setParam(key, event.target.value)}
                        className="rounded-2xl border-black/[0.07] bg-white/68"
                      />
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => void run()} disabled={loading}>
                {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                {mode === "classic" ? "开始回测" : mode === "scan" ? "运行扫描" : "开始对比"}
              </Button>
              <Button size="sm" variant="outline" onClick={resetResults}>
                清空结果
              </Button>
              <span className="text-[0.84rem] leading-6 text-foreground/58">结果区会保留当前模式输出，便于你连续调参与比较。</span>
            </div>
          </div>
        </div>
      </GlassCard>

      {error ? (
        <div className="surface-tone-cinnabar rounded-[24px] border px-4 py-3 text-sm leading-7">{error}</div>
      ) : null}

      {classicResult || compareResult ? (
        <div className="space-y-5">
          <PanelHeader
            title={compareResult ? "多策略对比结果" : "策略回测结果"}
            description={
              compareResult
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

          <GlassCard className="space-y-4 p-5">
            <PanelHeader
              title="交易记录"
              description="用交易频率、方向切换与手续费节奏判断策略是否存在过度交易。"
            />
            {activeTrades.length > 0 ? (
              <div className="overflow-hidden rounded-2xl border border-border/60">
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
            ) : (
              <EmptyState description="当前结果还没有交易记录。" />
            )}
          </GlassCard>
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
            <div className="overflow-hidden rounded-2xl border border-border/60">
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
          ) : (
            <EmptyState description="当前条件下还没有筛选到符合要求的标的。" />
          )}
        </GlassCard>
      ) : null}

      {!classicResult && !scanResult && !compareResult ? (
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
