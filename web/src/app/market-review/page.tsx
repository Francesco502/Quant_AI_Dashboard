"use client"

import { useEffect, useMemo, useState } from "react"
import { RefreshCw, TrendingDown, TrendingUp } from "lucide-react"

import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api, type MarketIndex, type MarketReviewResponse } from "@/lib/api"
import { cn } from "@/lib/utils"

type MarketValue = "cn" | "us" | "both"

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
      const message = err instanceof Error ? err.message : "加载失败"
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
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">大盘复盘</h1>
          <p className="text-sm text-muted-foreground">每日指数、行业强弱与市场广度快照（Market Review）。</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={market} onValueChange={(value) => setMarket(value as MarketValue)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cn">A股 (CN)</SelectItem>
              <SelectItem value="us">美股 (US)</SelectItem>
              <SelectItem value="both">中美 (CN + US)</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => void loadReview(market)} disabled={loading}>
            {loading ? "加载中..." : <><RefreshCw className="w-4 h-4 mr-1.5" />刷新</>}
          </Button>
        </div>
      </div>

      {error && (
        <GlassCard className="p-4 border-red-200 bg-red-50/50 dark:bg-red-950/20">
          <p className="text-sm text-red-600 dark:text-red-400">获取复盘失败：{error}</p>
        </GlassCard>
      )}

      {!data ? (
        <GlassCard className="p-8 text-sm text-muted-foreground">暂无数据。</GlassCard>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="日期" value={data.date || "-"} help="市场复盘对应的交易日期。" />
            <Metric label="市场" value={data.market || market.toUpperCase()} help="当前聚合的数据市场范围。" />
            <Metric label="上涨家数" value={String(data.overview?.up ?? "-")} help="当日上涨个股数量（Market Breadth）。" />
            <Metric label="下跌家数" value={String(data.overview?.down ?? "-")} help="当日下跌个股数量（Market Breadth）。" />
          </div>

          <GlassCard className="p-5 space-y-4">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold">指数表现</h2>
              <HelpTooltip content="展示核心指数的点位与涨跌幅，红涨绿跌。" />
            </div>
            {data.indices && data.indices.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {data.indices.map((indexItem) => (
                  <IndexCard key={indexItem.name} item={indexItem} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">暂无指数数据。</p>
            )}
          </GlassCard>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <GlassCard className="p-5 space-y-3">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">行业领涨 TOP5</h3>
                <HelpTooltip content="按行业涨跌幅排序，帮助识别资金偏好方向。" />
              </div>
              {gainSectors.length > 0 ? (
                <ul className="space-y-2">
                  {gainSectors.map((sector, idx) => (
                    <li key={`${sector.name}-${idx}`} className="flex items-center justify-between text-sm">
                      <span>{sector.name}</span>
                      <span className="font-mono text-red-500">+{Number(sector.pct_change).toFixed(2)}%</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">暂无行业数据。</p>
              )}
            </GlassCard>

            <GlassCard className="p-5 space-y-3">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">行业领跌 TOP5</h3>
                <HelpTooltip content="关注弱势板块可帮助规避系统性回撤风险。" />
              </div>
              {lossSectors.length > 0 ? (
                <ul className="space-y-2">
                  {lossSectors.map((sector, idx) => (
                    <li key={`${sector.name}-${idx}`} className="flex items-center justify-between text-sm">
                      <span>{sector.name}</span>
                      <span className="font-mono text-emerald-500">-{Math.abs(Number(sector.pct_change)).toFixed(2)}%</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">暂无行业数据。</p>
              )}
            </GlassCard>
          </div>

          {data.northbound && (
            <GlassCard className="p-4">
              <div className="text-sm font-medium mb-1">北向资金</div>
              <p className="text-sm text-muted-foreground">
                {data.northbound.description || "暂无北向资金描述。"}
              </p>
            </GlassCard>
          )}
        </>
      )}
    </div>
  )
}

function Metric({ label, value, help }: { label: string; value: string; help: string }) {
  return (
    <GlassCard className="p-3">
      <div className="text-xs text-muted-foreground uppercase flex items-center">
        {label}
        <HelpTooltip content={help} />
      </div>
      <div className="text-lg font-semibold">{value}</div>
    </GlassCard>
  )
}

function IndexCard({ item }: { item: MarketIndex }) {
  const isUp = Number(item.pct_change) >= 0

  return (
    <GlassCard className="p-4 space-y-1">
      <div className="text-sm text-muted-foreground">{item.name}</div>
      <div className="text-xl font-semibold">{Number(item.value).toFixed(2)}</div>
      <div className={cn("text-sm font-medium flex items-center", isUp ? "text-red-500" : "text-emerald-500")}>
        {isUp ? <TrendingUp className="w-3.5 h-3.5 mr-1" /> : <TrendingDown className="w-3.5 h-3.5 mr-1" />}
        {(isUp ? "+" : "") + Number(item.pct_change).toFixed(2)}%
      </div>
    </GlassCard>
  )
}
