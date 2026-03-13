"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Brain, RefreshCw, TrendingDown, TrendingUp } from "lucide-react"
import { Area, AreaChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { api as apiClient, type Asset, type ForecastResult, type PricePoint } from "@/lib/api"
import { GlassCard, CardDescription, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import { formatPercent, cn } from "@/lib/utils"

type Row = PricePoint & { kind: "history" | "forecast" }

function sma(values: number[], period: number) {
  const out = new Array<number | null>(values.length).fill(null)
  for (let i = period - 1; i < values.length; i += 1) {
    out[i] = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period
  }
  return out
}

function rsi(values: number[], period = 14) {
  const out = new Array<number | null>(values.length).fill(null)
  if (values.length <= period) return out
  let up = 0
  let down = 0
  for (let i = 1; i <= period; i += 1) {
    const d = values[i] - values[i - 1]
    up += Math.max(d, 0)
    down += Math.max(-d, 0)
  }
  let avgUp = up / period
  let avgDown = down / period
  out[period] = avgDown === 0 ? 100 : 100 - 100 / (1 + avgUp / avgDown)
  for (let i = period + 1; i < values.length; i += 1) {
    const d = values[i] - values[i - 1]
    avgUp = (avgUp * (period - 1) + Math.max(d, 0)) / period
    avgDown = (avgDown * (period - 1) + Math.max(-d, 0)) / period
    out[i] = avgDown === 0 ? 100 : 100 - 100 / (1 + avgUp / avgDown)
  }
  return out
}

function getMetric(metrics: ForecastResult["metrics"] | undefined, keys: string[]) {
  if (!metrics) return null
  for (const key of keys) {
    const value = metrics[key as keyof typeof metrics]
    if (typeof value === "number" && Number.isFinite(value)) return value
  }
  return null
}

export default function MarketPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [ticker, setTicker] = useState("")
  const [model, setModel] = useState("xgboost")
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
      if (pool.status === "fulfilled" && pool.value.length > 0) {
        setAssets(pool.value)
        setTicker(pool.value[0].ticker)
      } else {
        setAssets([{ ticker: "600519", alias: "贵州茅台", name: "贵州茅台" }])
        setTicker("600519")
      }
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
    void apiClient.data.getPrices([ticker], Number.parseInt(lookback, 10))
      .then((res) => { if (!cancelled) setHistory(res?.data?.[ticker] ?? []) })
      .catch(() => { if (!cancelled) setHistory([]) })
    return () => { cancelled = true }
  }, [ticker, lookback])

  const predict = async () => {
    if (!ticker) return
    setLoading(true)
    setError(null)
    try {
      setForecast(await apiClient.forecasting.getPrediction(ticker, Number.parseInt(horizon, 10), model, Number.parseInt(lookback, 10)))
    } catch (err) {
      setError(err instanceof Error ? err.message : "预测失败")
      setForecast(null)
    } finally {
      setLoading(false)
    }
  }

  const chart = useMemo<Row[]>(() => [...history.map((x) => ({ ...x, kind: "history" as const })), ...(forecast?.predictions ?? []).map((x) => ({ ...x, kind: "forecast" as const }))], [history, forecast])
  const summary = useMemo(() => {
    if (!history.length || !forecast?.predictions.length) return null
    const now = history[history.length - 1].price
    const target = forecast.predictions[forecast.predictions.length - 1].price
    const pct = (target - now) / Math.max(now, 1e-6)
    return { now, target, pct, up: pct >= 0 }
  }, [history, forecast])
  const modelEval = useMemo(() => {
    const mape = getMetric(forecast?.metrics, ["MAPE", "mape"])
    const mae = getMetric(forecast?.metrics, ["MAE", "mae"])
    if (mape != null || mae != null) return { text: mape != null ? `MAPE ${mape.toFixed(2)}%` : `MAE ${mae?.toFixed(4)}`, source: "历史留出集" }
    if (history.length > 10) {
      const sample = history.slice(-30)
      const e = sample.slice(1).reduce((acc, p, i) => acc + Math.abs(p.price - sample[i].price), 0) / Math.max(sample.length - 1, 1)
      return { text: `MAE ${e.toFixed(4)}`, source: "历史代理评估" }
    }
    return null
  }, [forecast?.metrics, history])
  const indicator = useMemo(() => {
    if (history.length < 30) return []
    const prices = history.map((x) => x.price)
    const s20 = sma(prices, 20)
    const r14 = rsi(prices, 14)
    return history.map((x, i) => ({ ...x, sma20: s20[i], rsi: r14[i] })).filter((x) => x.sma20 != null)
  }, [history])
  const indicatorNote = useMemo(() => {
    if (!indicator.length) return "历史数据不足，建议回溯天数至少 60 天。"
    const last = indicator[indicator.length - 1]
    if ((last.rsi ?? 50) > 70) return "RSI 超买，建议避免追高，等待回落确认。"
    if ((last.rsi ?? 50) < 30) return "RSI 超卖，关注止跌信号后再分批参与。"
    return "RSI 中性，建议结合成交量和趋势方向综合判断。"
  }, [indicator])
  const risk = useMemo(() => {
    if (history.length < 30) return null
    const rets = history.slice(1).map((x, i) => (x.price - history[i].price) / Math.max(history[i].price, 1e-6))
    const mean = rets.reduce((a, b) => a + b, 0) / Math.max(rets.length, 1)
    const std = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(rets.length, 1))
    const annualVol = std * Math.sqrt(252)
    const series = history.map((x) => x.price)
    let peak = -Infinity
    let maxDd = 0
    const drawdown = series.map((p, i) => { peak = Math.max(peak, p); const dd = (peak - p) / Math.max(peak, 1e-6); maxDd = Math.max(maxDd, dd); return { date: history[i].date, drawdown: -dd } })
    return { annualVol, maxDd, drawdown, var95: [...rets].sort((a, b) => a - b)[Math.floor(rets.length * 0.05)] ?? 0 }
  }, [history])

  return (
    <motion.div className="space-y-6 max-w-7xl mx-auto">
      <div className="space-y-1"><h1 className="text-2xl font-semibold">AI 分析</h1><p className="text-sm text-muted-foreground">保留一个入口，整合预测、技术指标与风险分析。</p></div>
      <GlassCard className="!p-4 flex flex-wrap gap-3 items-end">
        <div className="min-w-[180px] flex-1"><div className="text-xs text-muted-foreground mb-1">资产（Asset）</div><Select value={ticker} onValueChange={setTicker}><SelectTrigger className="h-9"><SelectValue /></SelectTrigger><SelectContent>{assets.map((a) => <SelectItem key={a.ticker} value={a.ticker}>{a.alias || a.name || a.ticker}</SelectItem>)}</SelectContent></Select></div>
        <div className="min-w-[120px]"><div className="text-xs text-muted-foreground mb-1">模型（Model）</div><Select value={model} onValueChange={setModel}><SelectTrigger className="h-9"><SelectValue /></SelectTrigger><SelectContent>{models.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent></Select></div>
        <div className="min-w-[100px]"><div className="text-xs text-muted-foreground mb-1">回溯</div><Select value={lookback} onValueChange={setLookback}><SelectTrigger className="h-9"><SelectValue /></SelectTrigger><SelectContent>{[60, 90, 180, 360].map((n) => <SelectItem key={n} value={String(n)}>{n} 天</SelectItem>)}</SelectContent></Select></div>
        <div className="min-w-[100px]"><div className="text-xs text-muted-foreground mb-1">预测</div><Select value={horizon} onValueChange={setHorizon}><SelectTrigger className="h-9"><SelectValue /></SelectTrigger><SelectContent>{[1, 3, 5, 7, 15].map((n) => <SelectItem key={n} value={String(n)}>{n} 天</SelectItem>)}</SelectContent></Select></div>
        <Button className="h-9 px-5" onClick={() => void predict()} disabled={loading || !ticker}>{loading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Brain className="h-4 w-4 mr-2" />}{loading ? "分析中..." : "开始分析"}</Button>
      </GlassCard>
      {error && <GlassCard className="p-4 text-sm text-red-600 dark:text-red-400">请求失败：{error}</GlassCard>}

      <Tabs defaultValue="ai" className="space-y-4">
        <TabsList><TabsTrigger value="ai">AI分析</TabsTrigger><TabsTrigger value="ta">技术指标</TabsTrigger><TabsTrigger value="risk">风险分析</TabsTrigger></TabsList>
        <TabsContent value="ai" className="space-y-4">
          <GlassCard className="p-5 h-[390px]">
            <CardTitle>预测图表</CardTitle>
            <CardDescription>图表单独占一行，展示历史与预测。</CardDescription>
            {chart.length === 0 ? <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">暂无数据</div> : <ResponsiveContainer width="100%" height={300}><ComposedChart data={chart}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" /><XAxis dataKey="date" tickFormatter={(v) => new Date(v).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis width={56} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip /><Line dataKey={(d: Row) => d.kind === "history" ? d.price : null} stroke="#64748B" dot={false} /><Line dataKey={(d: Row) => d.kind === "forecast" ? d.price : null} stroke="#2563EB" dot={false} strokeDasharray="5 4" /></ComposedChart></ResponsiveContainer>}
          </GlassCard>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <GlassCard className="p-5"><div className="text-sm flex items-center gap-1">预测趋势<HelpTooltip content="终点预测相对当前价格的方向。" /></div>{!summary ? <div className="text-muted-foreground mt-2">--</div> : <div className={cn("mt-2 text-2xl font-semibold flex items-center gap-1", summary.up ? "text-red-500" : "text-emerald-600")}>{summary.up ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}{summary.up ? "偏多" : "偏空"} {formatPercent(summary.pct)}</div>}</GlassCard>
            <GlassCard className="p-5"><div className="text-sm flex items-center gap-1">目标价格<HelpTooltip content="预测周期末价格。" /></div><div className="mt-2 text-2xl font-mono">{summary ? summary.target.toFixed(2) : "--"}</div></GlassCard>
            <GlassCard className="p-5"><div className="text-sm flex items-center gap-1">波动率风险<HelpTooltip content="基于历史收益率年化波动率。" /></div><div className="mt-2 text-2xl">{risk ? (risk.annualVol > 0.35 ? "高" : risk.annualVol > 0.2 ? "中" : "低") : "--"}</div><div className="text-xs text-muted-foreground">{risk ? formatPercent(risk.annualVol) : ""}</div></GlassCard>
            <GlassCard className="p-5"><div className="text-sm flex items-center gap-1">模型误差<HelpTooltip content="使用历史留出集或历史代理值评估误差。" /></div><div className="mt-2 text-lg font-semibold">{modelEval ? modelEval.text : "--"}</div><div className="text-xs text-muted-foreground">{modelEval ? modelEval.source : ""}</div></GlassCard>
          </div>
        </TabsContent>
        <TabsContent value="ta" className="space-y-4">
          <GlassCard className="p-4"><div className="text-xs text-muted-foreground mb-1">资产选择（Asset）</div><Select value={ticker} onValueChange={setTicker}><SelectTrigger className="h-9 w-[240px]"><SelectValue /></SelectTrigger><SelectContent>{assets.map((a) => <SelectItem key={a.ticker} value={a.ticker}>{a.alias || a.name || a.ticker}</SelectItem>)}</SelectContent></Select></GlassCard>
          <GlassCard className="p-5 h-[340px]">{indicator.length === 0 ? <div className="h-[280px] flex items-center justify-center text-sm text-muted-foreground">数据不足</div> : <ResponsiveContainer width="100%" height={280}><ComposedChart data={indicator}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" /><XAxis dataKey="date" tickFormatter={(v) => new Date(v).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis width={56} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip /><Line dataKey="price" stroke="#475569" dot={false} /><Line dataKey="sma20" stroke="#2563EB" dot={false} /><Line dataKey="rsi" stroke="#EC4899" dot={false} /></ComposedChart></ResponsiveContainer>}</GlassCard>
          <GlassCard className="p-5"><CardTitle className="text-sm">指标解读建议</CardTitle><p className="text-sm mt-2">{indicatorNote}</p></GlassCard>
        </TabsContent>
        <TabsContent value="risk" className="space-y-4">
          <GlassCard className="p-4"><div className="text-xs text-muted-foreground mb-1">资产选择（Asset）</div><Select value={ticker} onValueChange={setTicker}><SelectTrigger className="h-9 w-[240px]"><SelectValue /></SelectTrigger><SelectContent>{assets.map((a) => <SelectItem key={a.ticker} value={a.ticker}>{a.alias || a.name || a.ticker}</SelectItem>)}</SelectContent></Select></GlassCard>
          {!risk ? <GlassCard className="p-10 text-sm text-muted-foreground">风险分析需要至少 30 个交易日数据。</GlassCard> : <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><GlassCard className="p-4"><div className="text-xs text-muted-foreground">年化波动</div><div className="text-xl font-semibold">{formatPercent(risk.annualVol)}</div></GlassCard><GlassCard className="p-4"><div className="text-xs text-muted-foreground">最大回撤</div><div className="text-xl font-semibold text-red-500">{formatPercent(-risk.maxDd)}</div></GlassCard><GlassCard className="p-4"><div className="text-xs text-muted-foreground">VaR 95%</div><div className="text-xl font-semibold text-amber-600">{formatPercent(risk.var95)}</div></GlassCard></div>
            <GlassCard className="p-5 h-[300px]"><ResponsiveContainer width="100%" height={240}><AreaChart data={risk.drawdown}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" /><XAxis dataKey="date" tickFormatter={(v) => new Date(v).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis width={52} tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip /><Area dataKey="drawdown" stroke="#EF4444" fill="rgba(239,68,68,0.2)" /></AreaChart></ResponsiveContainer></GlassCard>
            <GlassCard className="p-5"><CardTitle className="text-sm">风险建议</CardTitle><p className="text-sm mt-2">{risk.annualVol > 0.35 || Math.abs(risk.maxDd) > 0.25 ? "当前风险偏高，建议降低仓位并设置硬止损。" : risk.annualVol > 0.2 ? "风险中等，建议分批进出并控制单笔风险。" : "风险可控，可结合趋势信号继续跟踪。"}</p></GlassCard>
          </>}
        </TabsContent>
      </Tabs>
    </motion.div>
  )
}
