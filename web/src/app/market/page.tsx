"use client"

import { type ReactNode, useEffect, useMemo, useState } from "react"
import { Brain, RefreshCw, ShieldAlert } from "lucide-react"
import { Area, AreaChart, CartesianGrid, Line, Tooltip, XAxis, YAxis } from "recharts"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api as apiClient, type Asset, type ForecastResult, type PricePoint } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { buildErrorInsights, buildForecastRows, formatPrice, getForecastSummary, getYAxisDomain, summarizeError } from "@/lib/forecast-insights"
import { formatPercent } from "@/lib/utils"

type IndicatorRow = PricePoint & { label: string; sma20: number | null; rsi14: number | null }
type DrawdownRow = { date: string; label: string; drawdown: number }

function sma(values: number[], period: number) {
  const out = new Array<number | null>(values.length).fill(null)
  for (let i = period - 1; i < values.length; i += 1) out[i] = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period
  return out
}

function rsi(values: number[], period = 14) {
  const out = new Array<number | null>(values.length).fill(null)
  if (values.length <= period) return out
  let up = 0
  let down = 0
  for (let i = 1; i <= period; i += 1) {
    const diff = values[i] - values[i - 1]
    up += Math.max(diff, 0)
    down += Math.max(-diff, 0)
  }
  let avgUp = up / period
  let avgDown = down / period
  out[period] = avgDown === 0 ? 100 : 100 - 100 / (1 + avgUp / avgDown)
  for (let i = period + 1; i < values.length; i += 1) {
    const diff = values[i] - values[i - 1]
    avgUp = (avgUp * (period - 1) + Math.max(diff, 0)) / period
    avgDown = (avgDown * (period - 1) + Math.max(-diff, 0)) / period
    out[i] = avgDown === 0 ? 100 : 100 - 100 / (1 + avgUp / avgDown)
  }
  return out
}

export default function MarketPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [ticker, setTicker] = useState("")
  const [model, setModel] = useState("xgboost")
  const [activeTab, setActiveTab] = useState<"ai" | "ta" | "risk">("ai")
  const [models, setModels] = useState<string[]>(["xgboost", "lightgbm", "prophet", "arima"])
  const [lookback, setLookback] = useState("180")
  const [horizon, setHorizon] = useState("5")
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<PricePoint[]>([])
  const [forecast, setForecast] = useState<ForecastResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void Promise.allSettled([apiClient.stz.getAssetPool(), apiClient.forecasting.getModelList()]).then(([pool, list]) => {
      if (cancelled) return
      const poolAssets = pool.status === "fulfilled" && pool.value.length > 0 ? pool.value : [{ ticker: "600519", alias: "贵州茅台", name: "贵州茅台" }]
      setAssets(poolAssets)
      setTicker((current) => current || poolAssets[0].ticker)
      if (list.status === "fulfilled" && list.value.models?.length) {
        setModels(list.value.models)
        if (!list.value.models.includes(model)) setModel(list.value.models[0])
      }
    })
    return () => {
      cancelled = true
    }
  }, [model])

  useEffect(() => {
    if (!ticker) return
    let cancelled = false
    void apiClient.data.getPrices([ticker], Number.parseInt(lookback, 10)).then((res) => {
      if (!cancelled) setHistory(res?.data?.[ticker] ?? [])
    }).catch(() => {
      if (!cancelled) setHistory([])
    })
    return () => {
      cancelled = true
    }
  }, [ticker, lookback])

  const runAnalysis = async () => {
    if (!ticker) return
    setLoading(true)
    setError(null)
    try {
      setForecast(await apiClient.forecasting.getPrediction(ticker, Number.parseInt(horizon, 10), model, Number.parseInt(lookback, 10)))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "分析失败")
      setForecast(null)
    } finally {
      setLoading(false)
    }
  }

  const forecastRows = useMemo(() => buildForecastRows(history, forecast?.predictions ?? []), [history, forecast?.predictions])
  const forecastDomain = useMemo(() => getYAxisDomain(forecastRows.flatMap((row) => [row.historyPrice, row.forecastPrice]).filter((v): v is number => typeof v === "number")), [forecastRows])
  const forecastOnlyDomain = useMemo(() => getYAxisDomain((forecast?.predictions ?? []).map((point) => point.price)), [forecast?.predictions])
  const latestHistory = history.at(-1)?.price ?? null
  const forecastSummary = useMemo(() => getForecastSummary(history, forecast?.predictions ?? []), [history, forecast?.predictions])
  const errorInsights = useMemo(() => buildErrorInsights(forecast?.metrics, latestHistory), [forecast?.metrics, latestHistory])
  const errorSummary = useMemo(() => summarizeError(errorInsights), [errorInsights])

  const indicatorRows = useMemo<IndicatorRow[]>(() => {
    if (history.length < 20) return []
    const prices = history.map((item) => item.price)
    const s20 = sma(prices, 20)
    const r14 = rsi(prices, 14)
    return history.map((item, index) => ({ ...item, label: new Date(item.date).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }), sma20: s20[index], rsi14: r14[index] }))
  }, [history])
  const indicatorDomain = useMemo(() => getYAxisDomain(indicatorRows.flatMap((row) => [row.price, row.sma20]).filter((v): v is number => typeof v === "number")), [indicatorRows])
  const latestIndicator = indicatorRows.at(-1)
  const indicatorNote = useMemo(() => {
    if (!latestIndicator || latestIndicator.rsi14 == null || latestIndicator.sma20 == null) return "当前历史样本不足以稳定解释技术指标，建议把回看窗口提高到 90 天以上。"
    if (latestIndicator.price > latestIndicator.sma20 && latestIndicator.rsi14 >= 55 && latestIndicator.rsi14 <= 70) return "价格在均线上方且 RSI 仍处强势但未过热区间，更适合顺势跟踪。"
    if (latestIndicator.rsi14 > 70) return "RSI 已经偏热，说明短线动能强，但也意味着回踩确认的重要性更高。"
    if (latestIndicator.rsi14 < 30) return "RSI 已经偏弱，重点应放在止跌确认，而不是只凭低位就提前抄底。"
    return "价格、均线与 RSI 仍在中性区，更适合等待后续方向确认。"
  }, [latestIndicator])

  const risk = useMemo(() => {
    if (history.length < 30) return null
    const returns = history.slice(1).map((item, index) => (item.price - history[index].price) / Math.max(history[index].price, 1e-6))
    const mean = returns.reduce((acc, value) => acc + value, 0) / Math.max(returns.length, 1)
    const std = Math.sqrt(returns.reduce((acc, value) => acc + (value - mean) ** 2, 0) / Math.max(returns.length, 1))
    const annualVol = std * Math.sqrt(252)
    const var95 = [...returns].sort((a, b) => a - b)[Math.floor(returns.length * 0.05)] ?? 0
    let peak = -Infinity
    let maxDd = 0
    const drawdown: DrawdownRow[] = history.map((point) => {
      peak = Math.max(peak, point.price)
      const dd = (peak - point.price) / Math.max(peak, 1e-6)
      maxDd = Math.max(maxDd, dd)
      return { date: point.date, label: new Date(point.date).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }), drawdown: -dd }
    })
    return { annualVol, maxDd, var95, drawdown, worstDaily: Math.min(...returns), bestDaily: Math.max(...returns) }
  }, [history])

  const riskNote = useMemo(() => {
    if (!risk) return "风险分析至少需要 30 个交易日样本。"
    if (risk.annualVol > 0.35 || risk.maxDd > 0.25) return "当前波动和回撤都偏高，更适合降低仓位并提前设定退出条件。"
    if (risk.annualVol > 0.2) return "当前风险处于中等区间，适合参与，但不宜一次性重仓。"
    return "波动与回撤仍在可控范围内，但依然需要配合仓位与止损管理。"
  }, [risk])
  const riskTable = useMemo(() => (risk ? risk.drawdown.slice(-8).reverse() : []), [risk])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="space-y-2">
        <Badge variant="outline" className="w-fit rounded-full px-3 py-1 text-xs">AI分析</Badge>
        <h1 className="text-3xl font-semibold tracking-[-0.03em] text-foreground/90">一体化分析台</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">把预测、技术指标和风险放在同一页，并把关键数据、误差说明和教学提示放在图表下方，避免只有结论没有依据。</p>
      </div>

      <GlassCard className="flex flex-wrap items-end gap-3 p-5">
        <Field label="资产" hint="默认读取资产池中的常用标的。先维护资产池，再来这里分析。">
          <Select value={ticker} onValueChange={setTicker}>
            <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
            <SelectContent>{assets.map((asset) => <SelectItem key={asset.ticker} value={asset.ticker}>{asset.alias || asset.name || asset.ticker}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="模型" hint="建议至少横向比较两种模型，再决定是否采信。">
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
            <SelectContent>{models.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="回看窗口" hint="窗口过短容易受噪声影响，过长则会牺牲灵敏度。">
          <Select value={lookback} onValueChange={setLookback}>
            <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
            <SelectContent>{[60, 90, 180, 360].map((days) => <SelectItem key={days} value={String(days)}>{days} 天</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="预测窗口" hint="预测越长，越应该把结果当作方向参考，而不是精确目标价。">
          <Select value={horizon} onValueChange={setHorizon}>
            <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
            <SelectContent>{[1, 3, 5, 7, 15].map((days) => <SelectItem key={days} value={String(days)}>{days} 天</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Button className="h-10 px-5" onClick={() => void runAnalysis()} disabled={loading || !ticker}>
          {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Brain className="mr-2 h-4 w-4" />}
          {loading ? "分析中" : "开始分析"}
        </Button>
      </GlassCard>

      {error ? <div className="rounded-2xl border p-4 text-sm" style={{ color: SONG_COLORS.cinnabar, borderColor: "rgba(163,110,99,0.18)", background: "rgba(163,110,99,0.08)" }}>{error}</div> : null}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "ai" | "ta" | "risk")} className="space-y-4">
        <TabsList>
          <TabsTrigger value="ai">AI分析</TabsTrigger>
          <TabsTrigger value="ta">技术指标</TabsTrigger>
          <TabsTrigger value="risk">风险分析</TabsTrigger>
        </TabsList>
        <TabsContent value="ai" className="space-y-4">
          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1">
              <TitleWithHint title="历史与预测路径" hint="先看历史段和预测段是否平滑衔接，再看目标位是否落在合理波动区间内。" />
              <CardDescription>实线是历史价格，虚线是未来路径。这里更适合看方向和节奏，而不是精确点位。</CardDescription>
            </div>
            <MeasuredChart height={360}>
              {(width, height) => (
                <AreaChart width={width} height={height} data={forecastRows}>
                  <defs>
                    <linearGradient id="market-ai-history-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={SONG_COLORS.celadon} stopOpacity={0.24} />
                      <stop offset="95%" stopColor={SONG_COLORS.celadon} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} minTickGap={24} />
                  <YAxis domain={forecastDomain} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={64} />
                  <Tooltip
                    formatter={(value?: number | string) => (value == null ? ["--", ""] : [formatPrice(Number(value)), "价格"])}
                    labelFormatter={(label) => `日期 ${label}`}
                    contentStyle={{ borderRadius: 16, border: "1px solid rgba(77,71,66,0.08)", background: "rgba(255,255,255,0.92)" }}
                  />
                  <Area type="monotone" dataKey="historyPrice" stroke={SONG_COLORS.celadon} strokeWidth={2.2} fill="url(#market-ai-history-fill)" connectNulls />
                  <Line type="monotone" dataKey="forecastPrice" stroke={SONG_COLORS.indigo} strokeWidth={2.4} strokeDasharray="6 5" dot={false} connectNulls />
                </AreaChart>
              )}
            </MeasuredChart>
          </GlassCard>

          <div className="grid gap-3 md:grid-cols-4">
            <InfoCard label="预测趋势" hint="比较最新价格与预测终点的方向差，适合做方向判断。" value={forecastSummary ? (forecastSummary.up ? "偏多" : "偏谨慎") : "--"} secondary={forecastSummary ? `区间变化 ${(forecastSummary.pct * 100).toFixed(2)}%` : "等待模型返回"} accentColor={forecastSummary?.up ? SONG_COLORS.celadon : SONG_COLORS.cinnabar} />
            <InfoCard label="最新价格" hint="历史样本最后一个可用价格，是目标价和误差比例的基准。" value={forecastSummary ? formatPrice(forecastSummary.current) : "--"} secondary={history.at(-1)?.date?.slice(0, 10) ?? "暂无历史样本"} />
            <InfoCard label="目标价格" hint="预测窗口最后一天的价格，更适合作为区间终点预期。" value={forecastSummary ? formatPrice(forecastSummary.target) : "--"} secondary={forecast?.predictions.at(-1)?.date?.slice(0, 10) ?? "暂无目标时点"} accentColor={SONG_COLORS.indigo} />
            <InfoCard label="综合误差" hint="综合参考 MAPE、MAE、RMSE 和标准化误差。" value={errorSummary.title} secondary={errorSummary.description} accentColor={errorSummary.title.includes("偏高") ? SONG_COLORS.cinnabar : SONG_COLORS.ochre} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint title="单独预测路径" hint="只保留未来预测段，方便观察预测本身的斜率、节奏和拐点。" />
                <CardDescription>适合单独检查未来几天的路径结构是否顺滑。</CardDescription>
              </div>
              <MeasuredChart height={300}>
                {(width, height) => (
                  <AreaChart width={width} height={height} data={forecast?.predictions ?? []}>
                    <defs>
                      <linearGradient id="market-ai-forecast-fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={SONG_COLORS.indigo} stopOpacity={0.18} />
                        <stop offset="95%" stopColor={SONG_COLORS.indigo} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                    <XAxis dataKey="date" tickFormatter={(value) => value.slice(5, 10)} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} />
                    <YAxis domain={forecastOnlyDomain} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={64} />
                    <Tooltip
                      formatter={(value?: number | string) => (value == null ? ["--", ""] : [formatPrice(Number(value)), "预测价格"])}
                      labelFormatter={(label) => `日期 ${String(label).slice(0, 10)}`}
                      contentStyle={{ borderRadius: 16, border: "1px solid rgba(77,71,66,0.08)", background: "rgba(255,255,255,0.92)" }}
                    />
                    <Area type="monotone" dataKey="price" stroke={SONG_COLORS.indigo} strokeWidth={2.4} fill="url(#market-ai-forecast-fill)" />
                  </AreaChart>
                )}
              </MeasuredChart>
            </GlassCard>

            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint title="预测明细表" hint="逐日表格更适合教学讲解和复盘留档，可以直接核对每个预测点相对最新价格的变化。" />
                <CardDescription>这里保留逐日目标价和相对最新价格变化，便于讲解。</CardDescription>
              </div>
              <div className="overflow-hidden rounded-2xl border border-border/60">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>预测价格</TableHead>
                      <TableHead>较最新价格</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(forecast?.predictions ?? []).map((point) => {
                      const delta = latestHistory != null ? (point.price - latestHistory) / Math.max(latestHistory, 1e-6) : null
                      return (
                        <TableRow key={point.date}>
                          <TableCell>{point.date.slice(0, 10)}</TableCell>
                          <TableCell className="font-medium">{formatPrice(point.price)}</TableCell>
                          <TableCell style={{ color: delta != null && delta < 0 ? SONG_COLORS.cinnabar : SONG_COLORS.celadon }}>
                            {delta != null ? `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(2)}%` : "--"}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            </GlassCard>
          </div>

          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1">
              <TitleWithHint title="模型误差与说明" hint="不要只看 MAPE。MAE 看平均偏离多少价格单位，RMSE 看大偏差是否突出，NRMSE 便于跨标的比较。" />
              <CardDescription>{errorSummary.description}</CardDescription>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {errorInsights.map((item) => (
                <GlassCard key={item.key} className="space-y-2 border border-border/60 bg-white/45 p-4 dark:bg-white/[0.03]">
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span>{item.label}</span>
                    <HelpTooltip content={item.hint} />
                  </div>
                  <div className="text-2xl font-semibold text-foreground/90">{item.valueText}</div>
                  <p className="text-xs leading-5 text-muted-foreground">{item.description}</p>
                  <p className="text-sm leading-6" style={{ color: SONG_COLORS.ink }}>{item.interpretation}</p>
                </GlassCard>
              ))}
            </div>
          </GlassCard>
        </TabsContent>
        <TabsContent value="ta" className="space-y-4">
          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1">
              <TitleWithHint title="价格、均线与 RSI" hint="价格与均线负责看趋势位置，RSI 负责看动能冷热。三者一起看，才能避免单个指标误导。" />
              <CardDescription>左轴展示价格与 SMA20，右轴展示 RSI14。配色统一为更克制的宋式灰青、黛蓝与烟紫。</CardDescription>
            </div>
            <MeasuredChart height={360}>
              {(width, height) => (
                <AreaChart width={width} height={height} data={indicatorRows}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} minTickGap={24} />
                  <YAxis yAxisId="price" domain={indicatorDomain} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={64} />
                  <YAxis yAxisId="rsi" orientation="right" domain={[0, 100]} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={44} />
                  <Tooltip contentStyle={{ borderRadius: 16, border: "1px solid rgba(77,71,66,0.08)", background: "rgba(255,255,255,0.92)" }} />
                  <Line yAxisId="price" type="monotone" dataKey="price" stroke={SONG_COLORS.ink} strokeWidth={2.3} dot={false} />
                  <Line yAxisId="price" type="monotone" dataKey="sma20" stroke={SONG_COLORS.celadon} strokeWidth={2} dot={false} connectNulls />
                  <Line yAxisId="rsi" type="monotone" dataKey="rsi14" stroke={SONG_COLORS.plum} strokeWidth={1.9} dot={false} connectNulls />
                </AreaChart>
              )}
            </MeasuredChart>
          </GlassCard>

          <div className="grid gap-3 md:grid-cols-4">
            <InfoCard label="最新收盘价" hint="当前技术判断的基准价格，均线位置和动能状态都以这里展开。" value={latestIndicator ? formatPrice(latestIndicator.price) : "--"} />
            <InfoCard label="SMA20" hint="20 日均线常用来观察短中期趋势中枢。价格站上均线，通常说明趋势偏强。" value={latestIndicator?.sma20 != null ? formatPrice(latestIndicator.sma20) : "--"} accentColor={SONG_COLORS.celadon} />
            <InfoCard label="RSI14" hint="RSI 主要看动能冷热。70 上方通常偏热，30 下方通常偏弱，但都需要结合趋势一起看。" value={latestIndicator?.rsi14 != null ? latestIndicator.rsi14.toFixed(2) : "--"} accentColor={SONG_COLORS.plum} />
            <InfoCard label="均线偏离" hint="看当前价格相对 SMA20 偏离了多少。偏离越大，短线回归中枢的压力通常越强。" value={latestIndicator?.sma20 != null ? formatPercent((latestIndicator.price - latestIndicator.sma20) / Math.max(latestIndicator.sma20, 1e-6)) : "--"} accentColor={SONG_COLORS.ochre} />
          </div>

          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1">
              <TitleWithHint title="指标解读与明细" hint="先看解释，再看最近几天的数据明细。这样能把结论和证据放在一起，教学时更清楚。" />
              <CardDescription>{indicatorNote}</CardDescription>
            </div>
            <div className="overflow-hidden rounded-2xl border border-border/60">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日期</TableHead>
                    <TableHead>收盘价</TableHead>
                    <TableHead>SMA20</TableHead>
                    <TableHead>RSI14</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {indicatorRows.slice(-8).reverse().map((row) => (
                    <TableRow key={row.date}>
                      <TableCell>{row.date.slice(0, 10)}</TableCell>
                      <TableCell className="font-medium">{formatPrice(row.price)}</TableCell>
                      <TableCell>{row.sma20 != null ? formatPrice(row.sma20) : "--"}</TableCell>
                      <TableCell>{row.rsi14 != null ? row.rsi14.toFixed(2) : "--"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </GlassCard>
        </TabsContent>
        <TabsContent value="risk" className="space-y-4">
          {!risk ? (
            <GlassCard className="p-10 text-sm text-muted-foreground">风险分析至少需要 30 个交易日样本。</GlassCard>
          ) : (
            <>
              <GlassCard className="space-y-4 p-5">
                <div className="space-y-1">
                  <TitleWithHint title="回撤轨迹" hint="回撤轨迹反映历史从高点回落的深度和持续时间，比单日涨跌更能描述持有压力。" />
                  <CardDescription>回撤越深，说明这段持有经历中承受的净值压力越大。</CardDescription>
                </div>
                <MeasuredChart height={320}>
                  {(width, height) => (
                    <AreaChart width={width} height={height} data={risk.drawdown}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                      <XAxis dataKey="label" tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} minTickGap={24} />
                      <YAxis tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={56} />
                      <Tooltip formatter={(value?: number | string) => [`${(Number(value ?? 0) * 100).toFixed(2)}%`, "回撤"]} contentStyle={{ borderRadius: 16, border: "1px solid rgba(77,71,66,0.08)", background: "rgba(255,255,255,0.92)" }} />
                      <Area type="monotone" dataKey="drawdown" stroke={SONG_COLORS.cinnabar} strokeWidth={2} fill={SONG_COLORS.riskFill} />
                    </AreaChart>
                  )}
                </MeasuredChart>
              </GlassCard>

              <div className="grid gap-3 md:grid-cols-4">
                <InfoCard label="年化波动" hint="波动越高，净值起伏越大。它衡量的是持有过程的摇摆程度。" value={formatPercent(risk.annualVol)} />
                <InfoCard label="最大回撤" hint="历史上从峰值回落最深的一次跌幅，用来衡量最痛的持有时刻。" value={formatPercent(-risk.maxDd)} accentColor={SONG_COLORS.cinnabar} />
                <InfoCard label="VaR 95%" hint="在 95% 置信下的单日潜在损失阈值。它是风险下限估计，不代表最坏情况只有这么多。" value={formatPercent(risk.var95)} accentColor={SONG_COLORS.ochre} />
                <InfoCard label="风险结论" hint="综合波动与最大回撤给出的风险层级，用于帮助你决定仓位和参与节奏。" value={risk.annualVol > 0.35 || risk.maxDd > 0.25 ? "偏高" : risk.annualVol > 0.2 ? "中等" : "可控"} secondary={riskNote} accentColor={risk.annualVol > 0.35 || risk.maxDd > 0.25 ? SONG_COLORS.cinnabar : risk.annualVol > 0.2 ? SONG_COLORS.ochre : SONG_COLORS.celadon} />
              </div>

              <GlassCard className="space-y-4 p-5">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4" style={{ color: SONG_COLORS.cinnabar }} />
                    <TitleWithHint title="风险明细" hint="这里改成上下两段：先给结论和关键数字，再给最近回撤记录，避免左右高度不一致。" />
                  </div>
                  <CardDescription>上半部分给出结论和关键数字，下半部分保留最近回撤明细，阅读会更稳定。</CardDescription>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricPanel label="最佳单日收益" value={formatPercent(risk.bestDaily)} hint="样本里涨幅最大的单日表现，反映向上弹性。" color={SONG_COLORS.celadon} />
                  <MetricPanel label="最差单日收益" value={formatPercent(risk.worstDaily)} hint="样本里跌幅最大的单日表现，用来感受短线极端压力。" color={SONG_COLORS.cinnabar} />
                  <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                    <div className="mb-2 flex items-center gap-1 text-sm font-medium text-foreground/90">
                      <span>教学说明</span>
                      <HelpTooltip content="把风险数字翻译成持有体验，便于讲解时不只报数字。" />
                    </div>
                    <p className="text-sm leading-6 text-muted-foreground">{riskNote}</p>
                  </div>
                </div>

                <div className="overflow-hidden rounded-2xl border border-border/60">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>日期</TableHead>
                        <TableHead>回撤</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {riskTable.map((row) => (
                        <TableRow key={row.date}>
                          <TableCell>{row.date.slice(0, 10)}</TableCell>
                          <TableCell className="font-medium" style={{ color: SONG_COLORS.cinnabar }}>{formatPercent(row.drawdown)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </GlassCard>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Field({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <div className="min-w-[140px] flex-1 space-y-2">
      <Label className="flex items-center gap-1"><span>{label}</span><HelpTooltip content={hint} /></Label>
      {children}
    </div>
  )
}

function TitleWithHint({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="flex items-center gap-1">
      <CardTitle>{title}</CardTitle>
      <HelpTooltip content={hint} />
    </div>
  )
}

function InfoCard({
  label,
  hint,
  value,
  secondary,
  accentColor,
}: {
  label: string
  hint: string
  value: string
  secondary?: string
  accentColor?: string
}) {
  return (
    <GlassCard className="space-y-2 p-4">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <span>{label}</span>
        <HelpTooltip content={hint} />
      </div>
      <div className="text-2xl font-semibold" style={{ color: accentColor ?? SONG_COLORS.ink }}>{value}</div>
      {secondary ? <div className="text-xs leading-5 text-muted-foreground">{secondary}</div> : null}
    </GlassCard>
  )
}

function MetricPanel({
  label,
  value,
  hint,
  color,
}: {
  label: string
  value: string
  hint: string
  color: string
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
      <div className="mb-2 flex items-center gap-1 text-sm font-medium text-foreground/90">
        <span>{label}</span>
        <HelpTooltip content={hint} />
      </div>
      <div className="text-2xl font-semibold" style={{ color }}>{value}</div>
    </div>
  )
}
