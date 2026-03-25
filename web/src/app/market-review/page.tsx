"use client"

import { useEffect, useMemo, useState } from "react"
import { RefreshCw, TrendingDown, TrendingUp } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api, type MarketIndex, type MarketReviewResponse } from "@/lib/api"
import { cn } from "@/lib/utils"

type MarketValue = "cn" | "us" | "both"

function formatSignedPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

export default function MarketReviewPage() {
  const [market, setMarket] = useState<MarketValue>("cn")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<MarketReviewResponse | null>(null)

  const loadReview = async (selectedMarket: MarketValue) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.market.dailyReview(selectedMarket)
      setData(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载复盘失败"
      setError(message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadReview(market)
  }, [market])

  const gainSectors = useMemo(() => data?.sectors?.gain ?? [], [data])
  const lossSectors = useMemo(() => data?.sectors?.loss ?? [], [data])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <Badge variant="outline" className="w-fit rounded-full px-3 py-1 text-xs">
            每日复盘
          </Badge>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-foreground/90">大盘复盘</h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            展示主要指数、行业强弱和资金流向。修复后，行业涨跌榜会按真实涨跌幅排序；市场广度只在拿到可靠聚合值时才展示，
            避免把错误口径误当成当日市场事实。
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Select value={market} onValueChange={(value) => setMarket(value as MarketValue)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cn">A 股</SelectItem>
              <SelectItem value="us">美股</SelectItem>
              <SelectItem value="both">中美合并</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => void loadReview(market)} disabled={loading}>
            {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            刷新数据
          </Button>
        </div>
      </div>

      {error ? (
        <GlassCard className="border-red-200 bg-red-50/50 p-4 dark:bg-red-950/20">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </GlassCard>
      ) : null}

      {!data ? (
        <GlassCard className="p-8 text-sm text-muted-foreground">暂无复盘数据。</GlassCard>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Metric label="交易日期" value={data.date || "-"} help="接口返回的复盘日期。" />
            <Metric label="市场范围" value={(data.market || market).toUpperCase()} help="当前聚合的市场范围。" />
            <Metric
              label="上涨家数"
              value={data.overview?.up != null ? String(data.overview.up) : "--"}
              help="只有拿到可靠聚合口径时才展示，避免用行业汇总重复计数。"
            />
            <Metric
              label="下跌家数"
              value={data.overview?.down != null ? String(data.overview.down) : "--"}
              help="只有拿到可靠聚合口径时才展示，避免用行业汇总重复计数。"
            />
            <Metric
              label="市场振幅"
              value={data.overview?.amplitude != null ? `${data.overview.amplitude.toFixed(2)}%` : "--"}
              help="来自行业汇总的均值，用于观察市场波动强弱。"
            />
          </div>

          <GlassCard className="space-y-4 p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-1">
                <CardTitle>指数表现</CardTitle>
                <CardDescription>优先展示主要指数收盘位与当日涨跌幅。</CardDescription>
              </div>
              <Badge variant="secondary">截至 {data.date}</Badge>
            </div>
            {data.indices && data.indices.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-3">
                {data.indices.map((indexItem) => (
                  <IndexCard key={indexItem.name} item={indexItem} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">暂无指数数据。</p>
            )}
          </GlassCard>

          <div className="grid gap-4 lg:grid-cols-2">
            <SectorPanel
              title="行业领涨 TOP5"
              subtitle="观察资金偏好的主线方向。"
              items={gainSectors}
              tone="up"
            />
            <SectorPanel
              title="行业领跌 TOP5"
              subtitle="识别当日明显承压的行业。"
              items={lossSectors}
              tone="down"
            />
          </div>

          <GlassCard className="space-y-3 p-5">
            <div className="flex items-center gap-2">
              <CardTitle>北向资金</CardTitle>
              <HelpTooltip content="用于观察外资对 A 股的净流入方向。" />
            </div>
            <p className="text-sm leading-6 text-muted-foreground">
              {data.northbound?.description || "当前数据源未返回北向资金摘要。"}
            </p>
          </GlassCard>
        </>
      )}
    </div>
  )
}

function Metric({ label, value, help }: { label: string; value: string; help: string }) {
  return (
    <GlassCard className="p-4">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {label}
        <HelpTooltip content={help} />
      </div>
      <div className="mt-2 text-xl font-semibold text-foreground/90">{value}</div>
    </GlassCard>
  )
}

function IndexCard({ item }: { item: MarketIndex }) {
  const isUp = Number(item.pct_change) >= 0

  return (
    <GlassCard className="space-y-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">{item.name}</div>
          <div className="mt-1 text-2xl font-semibold">{Number(item.value).toFixed(2)}</div>
        </div>
        <Badge variant={isUp ? "default" : "secondary"}>{isUp ? "走强" : "承压"}</Badge>
      </div>
      <div className={cn("flex items-center text-sm font-medium", isUp ? "text-red-500" : "text-emerald-600")}>
        {isUp ? <TrendingUp className="mr-1 h-4 w-4" /> : <TrendingDown className="mr-1 h-4 w-4" />}
        {formatSignedPercent(Number(item.pct_change))}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <span>成交量 {item.volume != null ? item.volume.toLocaleString() : "--"}</span>
        <span>成交额 {item.amount != null ? `${item.amount.toFixed(2)} 亿` : "--"}</span>
      </div>
    </GlassCard>
  )
}

function SectorPanel({
  title,
  subtitle,
  items,
  tone,
}: {
  title: string
  subtitle: string
  items: Array<{ name: string; pct_change: number }>
  tone: "up" | "down"
}) {
  const valueClass = tone === "up" ? "text-red-500" : "text-emerald-600"

  return (
    <GlassCard className="space-y-4 p-5">
      <div className="space-y-1">
        <CardTitle>{title}</CardTitle>
        <CardDescription>{subtitle}</CardDescription>
      </div>
      {items.length > 0 ? (
        <div className="space-y-3">
          {items.map((sector) => (
            <div key={sector.name} className="flex items-center justify-between rounded-2xl border border-border/60 bg-muted/20 px-4 py-3">
              <div className="text-sm font-medium text-foreground/90">{sector.name}</div>
              <div className={cn("text-sm font-semibold", valueClass)}>{formatSignedPercent(sector.pct_change)}</div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">暂无行业数据。</p>
      )}
    </GlassCard>
  )
}
