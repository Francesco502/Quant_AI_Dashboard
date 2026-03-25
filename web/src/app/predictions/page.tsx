"use client"

import { type ReactNode, useEffect, useMemo, useState } from "react"
import { Activity, ArrowUpRight, RefreshCw, Sparkles, Target } from "lucide-react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api, type ForecastResult, type PricePoint } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import {
  buildErrorInsights,
  buildForecastRows,
  formatPrice,
  getForecastSummary,
  getYAxisDomain,
  summarizeError,
} from "@/lib/forecast-insights"

export default function PredictionsPage() {
  const [ticker, setTicker] = useState("600519")
  const [horizon, setHorizon] = useState("5")
  const [lookback, setLookback] = useState("365")
  const [model, setModel] = useState("prophet")
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [result, setResult] = useState<ForecastResult | null>(null)
  const [history, setHistory] = useState<PricePoint[]>([])

  useEffect(() => {
    void api.forecasting
      .getModelList()
      .then((response) => {
        const nextModels = response.models || []
        setModels(nextModels.length > 0 ? nextModels : ["prophet"])
        if (nextModels.length > 0) {
          setModel(nextModels.includes("xgboost") ? "xgboost" : nextModels[0])
        }
      })
      .catch(() => {
        setModels(["prophet"])
      })
  }, [])

  const handlePredict = async () => {
    const cleanTicker = ticker.trim()
    if (!cleanTicker) {
      setError("请输入有效的标的代码。")
      return
    }

    setLoading(true)
    setError("")
    setResult(null)
    try {
      const [prediction, historyResponse] = await Promise.all([
        api.forecasting.getPrediction(cleanTicker, Number(horizon) || 5, model, Number(lookback) || 365),
        api.data.getPrices([cleanTicker], Number(lookback) || 365),
      ])
      setResult(prediction)
      setHistory(historyResponse?.data?.[cleanTicker] ?? [])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "预测失败")
      setHistory([])
    } finally {
      setLoading(false)
    }
  }

  const chartRows = useMemo(() => buildForecastRows(history, result?.predictions ?? []), [history, result?.predictions])
  const chartDomain = useMemo(
    () =>
      getYAxisDomain(
        chartRows
          .flatMap((row) => [row.historyPrice, row.forecastPrice])
          .filter((value): value is number => typeof value === "number")
      ),
    [chartRows]
  )
  const forecastOnlyDomain = useMemo(
    () => getYAxisDomain((result?.predictions ?? []).map((point) => point.price)),
    [result?.predictions]
  )

  const latestHistory = history.at(-1)?.price ?? null
  const summary = useMemo(() => getForecastSummary(history, result?.predictions ?? []), [history, result?.predictions])
  const errorInsights = useMemo(() => buildErrorInsights(result?.metrics, latestHistory), [result?.metrics, latestHistory])
  const errorSummary = useMemo(() => summarizeError(errorInsights), [errorInsights])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="space-y-2">
        <Badge variant="outline" className="w-fit rounded-full px-3 py-1 text-xs">
          预测中心
        </Badge>
        <h1 className="text-3xl font-semibold tracking-[-0.03em] text-foreground/90">价格预测</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          先看历史与预测是否连贯，再看未来路径和误差解释。页面会把趋势、目标价、误差口径和逐日预测表放在同一处，便于你做教学和复盘。
        </p>
      </div>

      <GlassCard className="space-y-4 p-5">
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="标的代码" hint="支持股票、基金、ETF 等代码。保持和数据源中的代码格式一致。">
            <Input value={ticker} onChange={(event) => setTicker(event.target.value)} />
          </Field>
          <Field label="预测天数" hint="预测窗口越长，参考价值越偏方向而非精确点位。短周期更适合做节奏判断。">
            <Input type="number" value={horizon} onChange={(event) => setHorizon(event.target.value)} />
          </Field>
          <Field label="回看窗口" hint="回看窗口决定模型可见的历史上下文。趋势型资产可适当加长，震荡型资产不宜过长。">
            <Input type="number" value={lookback} onChange={(event) => setLookback(event.target.value)} />
          </Field>
          <Field label="模型" hint="不同模型的适用场景不同。树模型更偏特征拟合，统计模型更偏时间序列结构。">
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {models.map((modelName) => (
                  <SelectItem key={modelName} value={modelName}>
                    {modelName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>

        <Button onClick={() => void handlePredict()} disabled={loading}>
          {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          {loading ? "正在预测" : "开始预测"}
        </Button>
      </GlassCard>

      {error ? <div className="rounded-2xl border border-[rgba(163,110,99,0.18)] bg-[rgba(163,110,99,0.08)] p-4 text-sm" style={{ color: SONG_COLORS.cinnabar }}>{error}</div> : null}

      {result ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <SummaryCard
              label="预测趋势"
              hint="比较最新历史价格与预测终点的方向差。它用于看方向，不代表中途不会出现反向波动。"
              value={summary ? (summary.up ? "偏多" : "偏谨慎") : "--"}
              secondary={summary ? `区间变化 ${(summary.pct * 100).toFixed(2)}%` : "等待模型结果"}
              icon={<ArrowUpRight className="h-4 w-4" />}
              accentColor={summary?.up ? SONG_COLORS.celadon : SONG_COLORS.cinnabar}
            />
            <SummaryCard
              label="最新价格"
              hint="历史样本最后一个可用价格，一般是最近收盘价或最近净值。它是所有相对变化的基准。"
              value={latestHistory != null ? formatPrice(latestHistory) : "--"}
              secondary={history.at(-1)?.date?.slice(0, 10) ?? "暂无历史数据"}
            />
            <SummaryCard
              label="目标价格"
              hint="预测窗口最后一个时点的价格。更适合看区间终点预期，而不是精确挂单价位。"
              value={summary ? formatPrice(summary.target) : "--"}
              secondary={result.predictions.at(-1)?.date?.slice(0, 10) ?? "暂无目标时点"}
              icon={<Target className="h-4 w-4" />}
            />
            <SummaryCard
              label="综合误差"
              hint="综合参考 MAPE、MAE、RMSE 与标准化误差。误差越低，预测路径越适合做节奏参考。"
              value={errorSummary.title}
              secondary={errorSummary.description}
              icon={<Activity className="h-4 w-4" />}
              accentColor={errorSummary.title.includes("偏高") ? SONG_COLORS.cinnabar : SONG_COLORS.ochre}
            />
          </div>

          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1">
              <TitleWithHint
                title="历史与预测路径"
                hint="先看历史段和预测段是否平滑衔接，再看目标位是否落在合理波动区间内。若衔接过于突兀，通常意味着模型稳定性一般。"
              />
              <CardDescription>实线是历史价格，虚线是未来预测。Y 轴会根据当前数据自动留边，避免图形被压扁。</CardDescription>
            </div>

            <MeasuredChart height={360}>
              {(width, height) => (
                <AreaChart width={width} height={height} data={chartRows}>
                  <defs>
                    <linearGradient id="prediction-history-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={SONG_COLORS.celadon} stopOpacity={0.24} />
                      <stop offset="95%" stopColor={SONG_COLORS.celadon} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} minTickGap={24} />
                  <YAxis domain={chartDomain} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={64} />
                  <Tooltip
                    formatter={(value?: number | string) => (value == null ? ["--", ""] : [formatPrice(Number(value)), "价格"])}
                    labelFormatter={(label) => `日期 ${label}`}
                    contentStyle={{ borderRadius: 16, border: "1px solid rgba(77,71,66,0.08)", background: "rgba(255,255,255,0.92)" }}
                  />
                  {latestHistory != null ? (
                    <ReferenceLine
                      y={latestHistory}
                      stroke={SONG_COLORS.ochre}
                      strokeDasharray="4 4"
                      label={{ value: "最新价格", fill: SONG_COLORS.axis }}
                    />
                  ) : null}
                  <Area type="monotone" dataKey="historyPrice" stroke={SONG_COLORS.celadon} strokeWidth={2.2} fill="url(#prediction-history-fill)" connectNulls />
                  <Line type="monotone" dataKey="forecastPrice" stroke={SONG_COLORS.indigo} strokeWidth={2.4} strokeDasharray="6 5" dot={false} connectNulls />
                </AreaChart>
              )}
            </MeasuredChart>
          </GlassCard>

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint
                  title="单独预测路径"
                  hint="只展示未来预测段，方便你观察预测本身的斜率、拐点和目标价分布，不会被历史走势干扰。"
                />
                <CardDescription>适合单独看未来数日的节奏变化和斜率变化。</CardDescription>
              </div>
              <MeasuredChart height={320}>
                {(width, height) => (
                  <AreaChart width={width} height={height} data={result.predictions}>
                    <defs>
                      <linearGradient id="prediction-forecast-fill" x1="0" y1="0" x2="0" y2="1">
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
                    {latestHistory != null ? <ReferenceLine y={latestHistory} stroke={SONG_COLORS.ochre} strokeDasharray="4 4" /> : null}
                    <Area type="monotone" dataKey="price" stroke={SONG_COLORS.indigo} strokeWidth={2.4} fill="url(#prediction-forecast-fill)" />
                  </AreaChart>
                )}
              </MeasuredChart>
            </GlassCard>

            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint
                  title="未来路径表格"
                  hint="逐日表格适合核对每个预测点相对最新价格的变化，方便做教学讲解和复盘留档。"
                />
                <CardDescription>把预测点拆成逐日明细，更方便你校对目标价和区间变化。</CardDescription>
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
                    {result.predictions.map((point) => {
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
              <TitleWithHint
                title="模型误差与说明"
                hint="误差部分不只看 MAPE。MAE 看平均偏离多少价格单位，RMSE 看大偏差是否集中，NRMSE 用来做跨标的比较。"
              />
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
                  <p className="text-sm leading-6" style={{ color: SONG_COLORS.ink }}>
                    {item.interpretation}
                  </p>
                </GlassCard>
              ))}
            </div>
          </GlassCard>
        </>
      ) : null}
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label className="flex items-center gap-1">
        <span>{label}</span>
        <HelpTooltip content={hint} />
      </Label>
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

function SummaryCard({
  label,
  hint,
  value,
  secondary,
  icon,
  accentColor,
}: {
  label: string
  hint: string
  value: string
  secondary?: string
  icon?: ReactNode
  accentColor?: string
}) {
  return (
    <GlassCard className="space-y-2 p-4">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <span>{label}</span>
          <HelpTooltip content={hint} />
        </div>
        {icon}
      </div>
      <div className="text-2xl font-semibold" style={{ color: accentColor ?? SONG_COLORS.ink }}>
        {value}
      </div>
      {secondary ? <div className="text-xs leading-5 text-muted-foreground">{secondary}</div> : null}
    </GlassCard>
  )
}
