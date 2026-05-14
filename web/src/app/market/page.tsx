"use client"

import Link from "next/link"
import { type ReactNode, useEffect, useMemo, useState } from "react"
import { ArrowUpRight, RefreshCw, ShieldAlert } from "lucide-react"
import { Area, AreaChart, CartesianGrid, Line, Tooltip, XAxis, YAxis } from "recharts"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { PanelHeader } from "@/components/data/panel-header"
import { StatusPill } from "@/components/data/status-pill"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { CardSkeleton } from "@/components/ui/skeleton"
import { api as apiClient, type Asset, type PricePoint } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import {
  formatPrice,
  getYAxisDomain,
} from "@/lib/forecast-insights"
import { formatMonthDayInBeijing } from "@/lib/time"
import { formatPercent } from "@/lib/utils"

type IndicatorRow = PricePoint & { label: string; sma20: number | null; rsi14: number | null }
type DrawdownRow = { date: string; label: string; drawdown: number }

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
  const [lookback, setLookback] = useState("180")
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [history, setHistory] = useState<PricePoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showIndicatorDetails, setShowIndicatorDetails] = useState(false)
  const [showRiskDetails, setShowRiskDetails] = useState(false)

  useEffect(() => {
    let cancelled = false

    void apiClient.stz.getAssetPool().then(
      (pool) => {
        if (cancelled) return

        const poolAssets = pool.length > 0 ? pool : [{ ticker: "600519", alias: "贵州茅台", name: "贵州茅台" }]
        setAssets(poolAssets)
        setTicker((current) => current || poolAssets[0].ticker)
      },
    ).catch(() => {
      if (cancelled) return
      const fallbackAssets = [{ ticker: "600519", alias: "贵州茅台", name: "贵州茅台" }]
      setAssets(fallbackAssets)
      setTicker((current) => current || fallbackAssets[0].ticker)
    })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!ticker) return

    let cancelled = false
    void apiClient.data
      .getPrices([ticker], Number.parseInt(lookback, 10))
      .then((res) => {
        if (!cancelled) {
          setHistory(res?.data?.[ticker] ?? [])
          setError(null)
        }
      })
      .catch((requestError) => {
        if (!cancelled) setHistory([])
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : "价格数据加载失败。")
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [ticker, lookback, historyRefreshKey])

  const indicatorRows = useMemo<IndicatorRow[]>(() => {
    if (history.length < 20) return []
    const prices = history.map((item) => item.price)
    const s20 = sma(prices, 20)
    const r14 = rsi(prices, 14)
    return history.map((item, index) => ({
      ...item,
      label: formatMonthDayInBeijing(item.date, item.date),
      sma20: s20[index],
      rsi14: r14[index],
    }))
  }, [history])
  const indicatorDomain = useMemo(
    () =>
      getYAxisDomain(
        indicatorRows
          .flatMap((row) => [row.price, row.sma20])
          .filter((value): value is number => typeof value === "number"),
      ),
    [indicatorRows],
  )
  const latestIndicator = indicatorRows.at(-1)
  const indicatorNote = useMemo(() => {
    if (!latestIndicator || latestIndicator.rsi14 == null || latestIndicator.sma20 == null) {
      return "当前历史样本不足以稳定解释技术指标，建议把回看窗口提升到 90 天以上。"
    }
    if (
      latestIndicator.price > latestIndicator.sma20 &&
      latestIndicator.rsi14 >= 55 &&
      latestIndicator.rsi14 <= 70
    ) {
      return "价格位于均线上方，且 RSI 仍处在偏强但未过热的区间，更适合顺势跟踪。"
    }
    if (latestIndicator.rsi14 > 70) {
      return "RSI 已经偏热，短线动能很强，但也说明回踩确认的重要性更高。"
    }
    if (latestIndicator.rsi14 < 30) {
      return "RSI 已经偏弱，重点应放在止跌确认，而不是只因低位就提前抄底。"
    }
    return "价格、均线与 RSI 仍在中性区，更适合等待后续方向确认。"
  }, [latestIndicator])

  const risk = useMemo(() => {
    if (history.length < 30) return null
    const returns = history
      .slice(1)
      .map((item, index) => (item.price - history[index].price) / Math.max(history[index].price, 1e-6))
    const mean = returns.reduce((acc, value) => acc + value, 0) / Math.max(returns.length, 1)
    const std = Math.sqrt(
      returns.reduce((acc, value) => acc + (value - mean) ** 2, 0) / Math.max(returns.length, 1),
    )
    const annualVol = std * Math.sqrt(252)
    const var95 = [...returns].sort((a, b) => a - b)[Math.floor(returns.length * 0.05)] ?? 0
    let peak = -Infinity
    let maxDd = 0
    const drawdown: DrawdownRow[] = history.map((point) => {
      peak = Math.max(peak, point.price)
      const dd = (peak - point.price) / Math.max(peak, 1e-6)
      maxDd = Math.max(maxDd, dd)
      return {
        date: point.date,
        label: formatMonthDayInBeijing(point.date, point.date),
        drawdown: -dd,
      }
    })
    return {
      annualVol,
      maxDd,
      var95,
      drawdown,
      worstDaily: Math.min(...returns),
      bestDaily: Math.max(...returns),
    }
  }, [history])

  const riskNote = useMemo(() => {
    if (!risk) return "风险分析至少需要 30 个交易日样本。"
    if (risk.annualVol > 0.35 || risk.maxDd > 0.25) {
      return "当前波动和回撤都偏高，更适合降低仓位并提前设定退出条件。"
    }
    if (risk.annualVol > 0.2) {
      return "当前风险处于中等区间，适合参与，但不宜一次性重仓。"
    }
    return "波动与回撤仍在可控范围内，但依然需要配合仓位与止损管理。"
  }, [risk])
  const riskTable = useMemo(() => (risk ? risk.drawdown.slice(-8).reverse() : []), [risk])
  const recentIndicatorRows = useMemo(() => indicatorRows.slice(-8).reverse(), [indicatorRows])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="space-y-2">
        <h1 className="page-title">技术与风险分析</h1>
        <p className="page-subtitle">
          聚焦价格位置、趋势动能与风险拆解；AI 预测统一放到预测研究页，避免两个入口重复解释同一件事。
        </p>
      </section>

      <GlassCard className="space-y-3 p-5 md:p-6">
        <PanelHeader
          title="分析设置"
          description="选定资产与回看窗口后，页面会自动刷新历史价格，并给出技术指标与风险拆解。"
          meta={
            <StatusPill
              label="当前资产"
              value={assets.find((asset) => asset.ticker === ticker)?.alias || assets.find((asset) => asset.ticker === ticker)?.name || ticker || "待选择"}
              tone="ink"
            />
          }
        />
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="分析资产" hint="默认读取资产池中的常用标的。先维护资产池，再到这里分析。">
            <Select value={ticker} onValueChange={setTicker}>
              <SelectTrigger className="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {assets.map((asset) => (
                  <SelectItem key={asset.ticker} value={asset.ticker}>
                    {asset.alias || asset.name || asset.ticker}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="回看窗口" hint="窗口过短容易受噪声影响，过长则会牺牲灵敏度。">
            <Select value={lookback} onValueChange={setLookback}>
              <SelectTrigger className="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[60, 90, 180, 360].map((days) => (
                  <SelectItem key={days} value={String(days)}>
                    {days} 天
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            className="h-10 px-5"
            onClick={() => {
              setHistoryLoading(true)
              setHistoryRefreshKey((value) => value + 1)
            }}
            disabled={historyLoading || !ticker}
          >
            <RefreshCw className={historyLoading ? "mr-2 h-4 w-4 animate-spin" : "mr-2 h-4 w-4"} />
            {historyLoading ? "正在刷新" : "刷新价格"}
          </Button>
          <Button asChild variant="outline" className="h-10 px-5">
            <Link href="/predictions">
              去 AI 预测研究
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </GlassCard>

      {error ? (
        <div className="surface-tone-cinnabar rounded-[24px] border p-4 text-sm leading-7">
          {error}
        </div>
      ) : null}

      <section className="space-y-4">
      {historyLoading ? (
        <CardSkeleton rows={4} />
      ) : (
      <>
        <div className="space-y-1">
          <CardTitle>技术指标</CardTitle>
          <CardDescription>用价格、均线与 RSI 一起判断位置、趋势与动能。</CardDescription>
        </div>

        <GlassCard className="space-y-4 p-5">
          <div className="space-y-1">
            <TitleWithHint
              title="价格、均线与 RSI"
              hint="价格与均线负责看趋势位置，RSI 负责看动能冷热。三者一起看，能减少单一指标误导。"
            />
          </div>
          <div className="text-xs text-muted-foreground lg:hidden">图表会优先保留关键走势，触摸图表可查看具体点位。</div>
          <MeasuredChart height={340}>
            {(width, height) => (
              <AreaChart width={width} height={height} data={indicatorRows}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                <XAxis dataKey="label" tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} minTickGap={24} />
                <YAxis yAxisId="price" domain={indicatorDomain} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={64} />
                <YAxis yAxisId="rsi" orientation="right" domain={[0, 100]} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={44} />
                <Tooltip
                  contentStyle={{ borderRadius: 16, border: "1px solid var(--chart-tooltip-border)", background: "var(--chart-tooltip-bg)" }}
                />
                <Line yAxisId="price" type="monotone" dataKey="price" stroke={SONG_COLORS.ink} strokeWidth={2.3} dot={false} />
                <Line yAxisId="price" type="monotone" dataKey="sma20" stroke={SONG_COLORS.celadon} strokeWidth={2} dot={false} connectNulls />
                <Line yAxisId="rsi" type="monotone" dataKey="rsi14" stroke={SONG_COLORS.plum} strokeWidth={1.9} dot={false} connectNulls />
              </AreaChart>
            )}
          </MeasuredChart>
        </GlassCard>

        <div className="grid gap-3 md:grid-cols-4">
          <InfoCard
            label="最新收盘价"
            hint="技术判断的基准价格，均线位置和动能状态都从这里展开。"
            value={latestIndicator ? formatPrice(latestIndicator.price) : "--"}
          />
          <InfoCard
            label="SMA20"
            hint="20 日均线常用于观察中短期趋势中枢。"
            value={latestIndicator?.sma20 != null ? formatPrice(latestIndicator.sma20) : "--"}
            accentColor={SONG_COLORS.celadon}
          />
          <InfoCard
            label="RSI14"
            hint="RSI 用来判断动能冷热，70 上方偏热，30 下方偏弱。"
            value={latestIndicator?.rsi14 != null ? latestIndicator.rsi14.toFixed(2) : "--"}
            accentColor={SONG_COLORS.plum}
          />
          <InfoCard
            label="均线偏离"
            hint="看当前价格相对 SMA20 偏离多少，偏离越大，回归中枢压力通常越强。"
            value={
              latestIndicator?.sma20 != null
                ? formatPercent((latestIndicator.price - latestIndicator.sma20) / Math.max(latestIndicator.sma20, 1e-6))
                : "--"
            }
            accentColor={SONG_COLORS.ochre}
          />
        </div>

        <GlassCard className="space-y-4 p-5">
          <div className="space-y-1">
            <TitleWithHint title="指标解读与明细" hint="先看结论，再看最近几天的明细，把判断和证据放在一起。" />
            <CardDescription>{indicatorNote}</CardDescription>
          </div>
          <div className="space-y-3 lg:hidden">
            {recentIndicatorRows.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
                暂无指标明细。
              </div>
            ) : null}
            {(showIndicatorDetails ? recentIndicatorRows : recentIndicatorRows.slice(0, 3)).map((row) => (
              <div key={row.date} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs text-muted-foreground">日期</div>
                    <div className="mt-1 font-medium">{row.date.slice(0, 10)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-muted-foreground">收盘价</div>
                    <div className="mt-1 text-lg font-semibold tabular-nums">{formatPrice(row.price)}</div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-xl bg-background/50 px-3 py-2">
                    <div className="text-xs text-muted-foreground">SMA20</div>
                    <div className="mt-1 font-medium">{row.sma20 != null ? formatPrice(row.sma20) : "--"}</div>
                  </div>
                  <div className="rounded-xl bg-background/50 px-3 py-2">
                    <div className="text-xs text-muted-foreground">RSI14</div>
                    <div className="mt-1 font-medium">{row.rsi14 != null ? row.rsi14.toFixed(2) : "--"}</div>
                  </div>
                </div>
              </div>
            ))}
            {recentIndicatorRows.length > 3 ? (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => setShowIndicatorDetails((current) => !current)}
              >
                {showIndicatorDetails ? "收起指标明细" : `展开最近 ${recentIndicatorRows.length} 条指标明细`}
              </Button>
            ) : null}
          </div>
          <div className="hidden overflow-hidden rounded-2xl border border-border/60 lg:block">
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
                {recentIndicatorRows.map((row) => (
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
      </>
      )}
      </section>

      <section className="space-y-4">
      {historyLoading ? (
        <CardSkeleton rows={3} />
      ) : (
      <>
        <div className="space-y-1">
          <CardTitle>风险拆解</CardTitle>
          <CardDescription>把回撤、波动与风险结论放在同一页，不再拆成独立子页。</CardDescription>
        </div>

        {!risk ? (
          <GlassCard className="p-6 text-sm text-foreground/68">风险分析至少需要 30 个交易日样本。</GlassCard>
        ) : (
          <>
            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <TitleWithHint
                  title="回撤轨迹"
                  hint="回撤轨迹反映历史从高点回落的深度与持续时间，比单日涨跌更能描述持有压力。"
                />
              </div>
              <div className="text-xs text-muted-foreground lg:hidden">回撤图保留完整轨迹，下方默认只列最近 3 条风险记录。</div>
              <MeasuredChart height={320}>
                {(width, height) => (
                  <AreaChart width={width} height={height} data={risk.drawdown}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={SONG_COLORS.grid} />
                    <XAxis dataKey="label" tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} minTickGap={24} />
                    <YAxis tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`} tick={{ fontSize: 12, fill: SONG_COLORS.axis }} axisLine={false} tickLine={false} width={56} />
                    <Tooltip
                      formatter={(value?: number | string) => [`${(Number(value ?? 0) * 100).toFixed(2)}%`, "回撤"]}
                      contentStyle={{ borderRadius: 16, border: "1px solid var(--chart-tooltip-border)", background: "var(--chart-tooltip-bg)" }}
                    />
                    <Area type="monotone" dataKey="drawdown" stroke={SONG_COLORS.cinnabar} strokeWidth={2} fill={SONG_COLORS.riskFill} />
                  </AreaChart>
                )}
              </MeasuredChart>
            </GlassCard>

            <div className="grid gap-3 md:grid-cols-4">
              <InfoCard label="年化波动" hint="波动越高，净值起伏越大。" value={formatPercent(risk.annualVol)} />
              <InfoCard label="最大回撤" hint="历史上从峰值回落最深的一次跌幅。" value={formatPercent(-risk.maxDd)} accentColor={SONG_COLORS.cinnabar} />
              <InfoCard label="VaR 95%" hint="在 95% 置信下的单日潜在损失阈值。" value={formatPercent(risk.var95)} accentColor={SONG_COLORS.ochre} />
              <InfoCard
                label="风险结论"
                hint="综合波动与最大回撤后的风险层级。"
                value={risk.annualVol > 0.35 || risk.maxDd > 0.25 ? "偏高" : risk.annualVol > 0.2 ? "中等" : "可控"}
                secondary={riskNote}
                accentColor={
                  risk.annualVol > 0.35 || risk.maxDd > 0.25
                    ? SONG_COLORS.cinnabar
                    : risk.annualVol > 0.2
                      ? SONG_COLORS.ochre
                      : SONG_COLORS.celadon
                }
              />
            </div>

            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4" style={{ color: SONG_COLORS.cinnabar }} />
                  <TitleWithHint title="风险明细" hint="先给结论与关键数字，再给最近回撤记录，避免左右内容高度失衡。" />
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <MetricPanel label="最佳单日收益" value={formatPercent(risk.bestDaily)} hint="样本内涨幅最大的单日表现。" color={SONG_COLORS.celadon} />
                <MetricPanel label="最差单日收益" value={formatPercent(risk.worstDaily)} hint="样本内跌幅最大的单日表现。" color={SONG_COLORS.cinnabar} />
                <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                  <div className="mb-2 flex items-center gap-1 text-sm font-medium text-foreground/90">
                    <span>风险提示</span>
                  </div>
                  <p className="text-sm leading-6 text-foreground/72">{riskNote}</p>
                </div>
              </div>

              <div className="space-y-3 lg:hidden">
                {(showRiskDetails ? riskTable : riskTable.slice(0, 3)).map((row) => (
                  <div key={row.date} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-xs text-muted-foreground">日期</div>
                        <div className="mt-1 font-medium">{row.date.slice(0, 10)}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-muted-foreground">回撤</div>
                        <div className="mt-1 text-lg font-semibold tabular-nums" style={{ color: SONG_COLORS.cinnabar }}>
                          {formatPercent(row.drawdown)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {riskTable.length > 3 ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => setShowRiskDetails((current) => !current)}
                  >
                    {showRiskDetails ? "收起风险明细" : `展开最近 ${riskTable.length} 条风险明细`}
                  </Button>
                ) : null}
              </div>
              <div className="hidden overflow-hidden rounded-2xl border border-border/60 lg:block">
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
                        <TableCell className="font-medium" style={{ color: SONG_COLORS.cinnabar }}>
                          {formatPercent(row.drawdown)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </GlassCard>
          </>
        )}
      </>
      )}
      </section>
    </div>
  )
}

function Field({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <div className="min-w-[140px] space-y-2.5">
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
    <GlassCard className="space-y-2.5 p-4" title={hint}>
      <div className="text-[0.88rem] font-medium text-foreground/78">
        <span>{label}</span>
      </div>
      <div className="text-2xl font-semibold" style={{ color: accentColor ?? SONG_COLORS.ink }}>
        {value}
      </div>
      {secondary ? <div className="text-[0.84rem] leading-6 text-foreground/66">{secondary}</div> : null}
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
    <div className="rounded-2xl border border-border/60 bg-muted/20 p-4" title={hint}>
      <div className="mb-2 text-sm font-medium text-foreground/90">
        <span>{label}</span>
      </div>
      <div className="text-2xl font-semibold" style={{ color }}>
        {value}
      </div>
    </div>
  )
}
