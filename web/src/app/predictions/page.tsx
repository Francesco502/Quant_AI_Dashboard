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
import { EmptyState } from "@/components/data/empty-state"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
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
      setError(requestError instanceof Error ? requestError.message : "预测失败。")
      setHistory([])
    } finally {
      setLoading(false)
    }
  }

  const chartRows = useMemo(
    () => buildForecastRows(history, result?.predictions ?? []),
    [history, result?.predictions],
  )
  const chartDomain = useMemo(
    () =>
      getYAxisDomain(
        chartRows
          .flatMap((row) => [row.historyPrice, row.forecastPrice])
          .filter((value): value is number => typeof value === "number"),
      ),
    [chartRows],
  )
  const forecastOnlyDomain = useMemo(
    () => getYAxisDomain((result?.predictions ?? []).map((point) => point.price)),
    [result?.predictions],
  )

  const latestHistory = history.at(-1)?.price ?? null
  const summary = useMemo(
    () => getForecastSummary(history, result?.predictions ?? []),
    [history, result?.predictions],
  )
  const errorInsights = useMemo(
    () => buildErrorInsights(result?.metrics, latestHistory),
    [result?.metrics, latestHistory],
  )
  const errorSummary = useMemo(() => summarizeError(errorInsights), [errorInsights])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="space-y-2">
        <h1 className="page-title">AI 预测研究</h1>
        <p className="page-subtitle">
          先看历史走势与预测路径是否衔接，再看目标价与误差解释是否合理。这里把趋势、预测、误差与逐日明细收在同一处，便于你快速判断结果是否值得继续跟踪。
        </p>
      </section>

      <GlassCard className="space-y-5 p-5 md:p-6">
        <div className="grid gap-4 md:grid-cols-4">
          <Field
            label="标的代码"
            hint="支持股票、基金、ETF 等代码，保持与数据源中的代码格式一致。"
          >
            <Input value={ticker} onChange={(event) => setTicker(event.target.value)} />
          </Field>
          <Field
            label="预测天数"
            hint="预测窗口越长，越适合看方向与节奏，不适合用作精确挂单价格。"
          >
            <Input type="number" value={horizon} onChange={(event) => setHorizon(event.target.value)} />
          </Field>
          <Field
            label="回看窗口"
            hint="回看窗口决定模型能看到多长的历史背景，趋势型资产可适当加长。"
          >
            <Input type="number" value={lookback} onChange={(event) => setLookback(event.target.value)} />
          </Field>
          <Field
            label="预测模型"
            hint="树模型更偏特征拟合，统计模型更偏时间序列结构，建议横向比较。"
          >
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

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => void handlePredict()} disabled={loading}>
            {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            {loading ? "正在生成预测" : "开始预测"}
          </Button>
          <p className="text-[0.84rem] leading-7 text-foreground/60">
            默认会同时拉取历史价格与预测结果，相关说明已经并入各区块的文字层，不再用显性的问号提示。
          </p>
        </div>
      </GlassCard>

      {error ? (
        <div className="surface-tone-cinnabar rounded-[24px] border p-4 text-sm leading-7">
          {error}
        </div>
      ) : null}

      {result ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <SummaryCard
              label="预测方向"
              hint="比较最新历史价格与预测终点的方向差，用于快速识别偏多或偏谨慎。"
              value={summary ? (summary.up ? "偏多" : "偏谨慎") : "--"}
              secondary={summary ? `区间变化 ${(summary.pct * 100).toFixed(2)}%` : "等待模型结果"}
              icon={<ArrowUpRight className="h-4 w-4" />}
              accentColor={summary?.up ? SONG_COLORS.celadon : SONG_COLORS.cinnabar}
            />
            <SummaryCard
              label="最新价格"
              hint="历史样本最后一个可用价格，一般为最近收盘价或净值。"
              value={latestHistory != null ? formatPrice(latestHistory) : "--"}
              secondary={history.at(-1)?.date?.slice(0, 10) ?? "暂无历史样本"}
            />
            <SummaryCard
              label="目标价格"
              hint="预测窗口最后一个时点的价格，更适合作为区间终点预期。"
              value={summary ? formatPrice(summary.target) : "--"}
              secondary={result.predictions.at(-1)?.date?.slice(0, 10) ?? "暂无目标时点"}
              icon={<Target className="h-4 w-4" />}
              accentColor={SONG_COLORS.indigo}
            />
            <SummaryCard
              label="综合误差"
              hint="综合参考 MAPE、MAE、RMSE 与标准化误差，用来判断路径是否可靠。"
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
                hint="先看历史段和预测段是否衔接平滑，再看目标价是否落在合理波动区间。"
              />
              <CardDescription>
                实线是历史价格，虚线是未来预测。Y 轴会自动留边，避免图形被压扁。
              </CardDescription>
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
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 12, fill: SONG_COLORS.axis }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={24}
                  />
                  <YAxis
                    domain={chartDomain}
                    tick={{ fontSize: 12, fill: SONG_COLORS.axis }}
                    axisLine={false}
                    tickLine={false}
                    width={64}
                  />
                  <Tooltip
                    formatter={(value?: number | string) =>
                      value == null ? ["--", ""] : [formatPrice(Number(value)), "价格"]
                    }
                    labelFormatter={(label) => `日期 ${label}`}
                    contentStyle={{
                      borderRadius: 16,
                      border: "1px solid rgba(77,71,66,0.08)",
                      background: "rgba(255,255,255,0.92)",
                    }}
                  />
                  {latestHistory != null ? (
                    <ReferenceLine
                      y={latestHistory}
                      stroke={SONG_COLORS.ochre}
                      strokeDasharray="4 4"
                      label={{ value: "最新价格", fill: SONG_COLORS.axis }}
                    />
                  ) : null}
                  <Area
                    type="monotone"
                    dataKey="historyPrice"
                    stroke={SONG_COLORS.celadon}
                    strokeWidth={2.2}
                    fill="url(#prediction-history-fill)"
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="forecastPrice"
                    stroke={SONG_COLORS.indigo}
                    strokeWidth={2.4}
                    strokeDasharray="6 5"
                    dot={false}
                    connectNulls
                  />
                </AreaChart>
              )}
            </MeasuredChart>
          </GlassCard>

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint
                  title="单独预测路径"
                  hint="只保留未来预测段，方便你观察斜率、节奏与目标位。"
                />
                <CardDescription>更适合单独看未来数日的节奏变化与方向延续。</CardDescription>
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
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => value.slice(5, 10)}
                      tick={{ fontSize: 12, fill: SONG_COLORS.axis }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={forecastOnlyDomain}
                      tick={{ fontSize: 12, fill: SONG_COLORS.axis }}
                      axisLine={false}
                      tickLine={false}
                      width={64}
                    />
                    <Tooltip
                      formatter={(value?: number | string) =>
                        value == null ? ["--", ""] : [formatPrice(Number(value)), "预测价格"]
                      }
                      labelFormatter={(label) => `日期 ${String(label).slice(0, 10)}`}
                      contentStyle={{
                        borderRadius: 16,
                        border: "1px solid rgba(77,71,66,0.08)",
                        background: "rgba(255,255,255,0.92)",
                      }}
                    />
                    {latestHistory != null ? (
                      <ReferenceLine y={latestHistory} stroke={SONG_COLORS.ochre} strokeDasharray="4 4" />
                    ) : null}
                    <Area
                      type="monotone"
                      dataKey="price"
                      stroke={SONG_COLORS.indigo}
                      strokeWidth={2.4}
                      fill="url(#prediction-forecast-fill)"
                    />
                  </AreaChart>
                )}
              </MeasuredChart>
            </GlassCard>

            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint
                  title="未来路径表格"
                  hint="逐日明细便于你核对每个预测点相对最新价格的变化。"
                />
                <CardDescription>把预测点拆成逐日表格，便于教学讲解和复盘留档。</CardDescription>
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
                      const delta =
                        latestHistory != null
                          ? (point.price - latestHistory) / Math.max(latestHistory, 1e-6)
                          : null
                      return (
                        <TableRow key={point.date}>
                          <TableCell>{point.date.slice(0, 10)}</TableCell>
                          <TableCell className="font-medium">{formatPrice(point.price)}</TableCell>
                          <TableCell
                            style={{ color: delta != null && delta < 0 ? SONG_COLORS.cinnabar : SONG_COLORS.celadon }}
                          >
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
                title="模型误差与解释"
                hint="不要只看单一误差项，最好结合 MAPE、MAE、RMSE 与标准化误差一起判断。"
              />
              <CardDescription>{errorSummary.description}</CardDescription>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {errorInsights.map((item) => (
                <GlassCard
                  key={item.key}
                  className="space-y-2 border border-border/60 bg-[rgba(250,246,239,0.45)] p-4"
                  title={item.hint}
                >
                  <div className="text-[0.88rem] font-medium text-foreground/76">{item.label}</div>
                  <div className="text-2xl font-semibold text-foreground/90">{item.valueText}</div>
                  <p className="text-[0.84rem] leading-6 text-foreground/72">{item.description}</p>
                  <p className="text-sm leading-6" style={{ color: SONG_COLORS.ink }}>
                    {item.interpretation}
                  </p>
                </GlassCard>
              ))}
            </div>
          </GlassCard>
        </>
      ) : !loading && !error ? (
        <GlassCard className="p-5">
          <EmptyState
            compact
            title="等待生成预测"
            description="输入标的代码并选择预测窗口后，即可在这里查看历史走势、目标价格、误差评估和逐日预测明细。"
            className="flex min-h-[156px] flex-col justify-center"
          />
        </GlassCard>
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
    <div className="space-y-2.5">
      <Label className="text-[0.94rem] font-medium text-foreground/88">{label}</Label>
      {children}
      <p className="text-[0.82rem] leading-6 text-foreground/58">{hint}</p>
    </div>
  )
}

function TitleWithHint({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="space-y-1.5">
      <CardTitle>{title}</CardTitle>
      <p className="max-w-2xl text-[0.84rem] leading-6 text-foreground/60">{hint}</p>
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
    <GlassCard className="space-y-2.5 p-4" title={hint}>
      <div className="flex items-center justify-between gap-2 text-[0.88rem] font-medium text-foreground/78">
        <div className="flex items-center gap-1">
          <span>{label}</span>
        </div>
        {icon}
      </div>
      <div className="text-2xl font-semibold" style={{ color: accentColor ?? SONG_COLORS.ink }}>
        {value}
      </div>
      {secondary ? <div className="text-[0.84rem] leading-6 text-foreground/66">{secondary}</div> : null}
    </GlassCard>
  )
}
