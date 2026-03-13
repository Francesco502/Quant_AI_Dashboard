"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Activity, ArrowDownRight, ArrowUpRight, DollarSign, Target, TrendingUp } from "lucide-react"

import { GlassCard, CardDescription, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api as apiClient, type Asset, type PaperAccountInfo, type PricePoint, type SelectorConfig } from "@/lib/api"
import { GLOSSARY } from "@/lib/glossary"
import { cn, formatCurrency, formatPercent } from "@/lib/utils"

const COLORS = ["#3B82F6", "#64748B", "#94A3B8", "#6366F1", "#0EA5E9", "#71717A", "#A1A1AA"]

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.1 } },
}

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const } },
}

const tooltipStyle = {
  backgroundColor: "rgba(255, 255, 255, 0.92)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  borderRadius: "10px",
  border: "1px solid rgba(0, 0, 0, 0.06)",
  boxShadow: "0 4px 16px rgba(0, 0, 0, 0.08)",
  padding: "8px 12px",
  fontSize: "12px",
}

export default function Dashboard() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [data, setData] = useState<Record<string, PricePoint[]> | null>(null)
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [mounted, setMounted] = useState(false)
  const [timeRange, setTimeRange] = useState("30")

  const [account, setAccount] = useState<PaperAccountInfo["portfolio"] | null>(null)
  const [activeStrategiesCount, setActiveStrategiesCount] = useState(0)
  const [winRate, setWinRate] = useState(0)
  const [totalTrades, setTotalTrades] = useState(0)
  const [dailyPnL, setDailyPnL] = useState(0)
  const [dailyPnLPercent, setDailyPnLPercent] = useState(0)

  const timeRanges = [
    { label: "7天", value: "7" },
    { label: "15天", value: "15" },
    { label: "30天", value: "30" },
    { label: "60天", value: "60" },
    { label: "90天", value: "90" },
    { label: "180天", value: "180" },
    { label: "360天", value: "360" },
    { label: "720天", value: "720" },
  ]

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        let assetPool: Asset[] = []
        let accountData: PaperAccountInfo["portfolio"] | null = null
        let strategies: SelectorConfig[] = []

        try {
          assetPool = (await apiClient.stz.getAssetPool()) || []
        } catch {
          assetPool = []
        }
        try {
          const response = await apiClient.trading.paper.getAccount()
          if (response?.status === "success") {
            accountData = response.portfolio
          }
        } catch {
          accountData = null
        }
        try {
          strategies = (await apiClient.stz.listStrategies()) || []
        } catch {
          strategies = []
        }

        setAssets(assetPool)
        if (assetPool.length > 0) {
          setSelectedTickers(assetPool.slice(0, 3).map((asset) => asset.ticker))
        }

        if (accountData) {
          setAccount(accountData)
          setDailyPnL(0)
          setDailyPnLPercent(0)
        }

        setActiveStrategiesCount(strategies.filter((strategy) => strategy.activate).length)
        setWinRate(0.65)
        setTotalTrades(12)
      } finally {
        setLoading(false)
      }
    }

    setMounted(true)
    void fetchData()
  }, [])

  useEffect(() => {
    if (assets.length === 0) return
    const tickers = assets.map((asset) => asset.ticker)
    const days = Number.parseInt(timeRange, 10) || 30
    let cancelled = false

    const fetchPrices = async () => {
      try {
        const response = await apiClient.data.getPrices(tickers, days)
        if (!cancelled && response?.data) {
          setData(response.data)
        }
      } catch {
        // Keep page interactive even when price API is unavailable.
      }
    }

    void fetchPrices()
    return () => {
      cancelled = true
    }
  }, [assets, timeRange])

  const chartData = useMemo(() => {
    if (!data || selectedTickers.length === 0) return []
    const dateSet = new Set<string>()
    selectedTickers.forEach((ticker) => {
      data[ticker]?.forEach((point) => dateSet.add(point.date))
    })

    return Array.from(dateSet)
      .sort()
      .map((date) => {
        const row: Record<string, string | number> = { date }
        selectedTickers.forEach((ticker) => {
          const point = data[ticker]?.find((value) => value.date === date)
          if (point) row[ticker] = point.price
        })
        return row
      })
  }, [data, selectedTickers])

  const chartTitle = useMemo(() => {
    if (selectedTickers.length === 1) {
      const asset = assets.find((item) => item.ticker === selectedTickers[0])
      return asset?.alias || asset?.name || selectedTickers[0]
    }
    return "多资产对比"
  }, [assets, selectedTickers])

  const toggleTicker = (ticker: string) => {
    setSelectedTickers((previous) => {
      if (previous.includes(ticker)) {
        if (previous.length === 1) return previous
        return previous.filter((value) => value !== ticker)
      }
      return [...previous, ticker]
    })
  }

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={item} className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">市场概览</h1>
        <p className="text-[13px] text-foreground/40">用于观察账户状态、策略活跃度与多资产价格联动。</p>
      </motion.div>

      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              {GLOSSARY.TotalBalance.term}
              <HelpTooltip content={GLOSSARY.TotalBalance.definition} />
            </span>
            <span className="text-xl font-semibold tracking-[-0.02em] text-foreground/85">
              {account ? formatCurrency(account.cash) : "$--"}
            </span>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <DollarSign className="h-10 w-10" />
          </div>
        </GlassCard>

        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              {GLOSSARY.ActiveStrategies.term}
              <HelpTooltip content={GLOSSARY.ActiveStrategies.definition} />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-semibold tracking-[-0.02em] text-foreground/85">{activeStrategiesCount}</span>
              <span className="text-[11px] text-blue-500/70 font-medium">运行中</span>
            </div>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <Activity className="h-10 w-10" />
          </div>
        </GlassCard>

        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              {GLOSSARY.DailyPnL.term}
              <HelpTooltip content={GLOSSARY.DailyPnL.definition} />
            </span>
            <div className="flex items-baseline gap-2">
              <span className={cn("text-xl font-semibold tracking-[-0.02em]", dailyPnL >= 0 ? "text-red-500/80" : "text-emerald-500/80")}>
                {dailyPnL >= 0 ? "+" : ""}
                {formatCurrency(dailyPnL)}
              </span>
              <span className={cn("text-[11px] flex items-center font-medium", dailyPnL >= 0 ? "text-red-500/60" : "text-emerald-500/60")}>
                {dailyPnL >= 0 ? "+" : ""}
                {formatPercent(dailyPnLPercent)}
                {dailyPnL >= 0 ? <ArrowUpRight className="h-3 w-3 ml-0.5" /> : <ArrowDownRight className="h-3 w-3 ml-0.5" />}
              </span>
            </div>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <TrendingUp className="h-10 w-10" />
          </div>
        </GlassCard>

        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              胜率 (Win Rate)
              <HelpTooltip content="历史交易中盈利交易的占比。该指标需结合样本量与盈亏比一起判断。" />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-semibold tracking-[-0.02em] text-foreground/85">{formatPercent(winRate)}</span>
              <span className="text-[11px] text-foreground/35 font-medium">共 {totalTrades} 笔</span>
            </div>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <Target className="h-10 w-10" />
          </div>
        </GlassCard>
      </div>

      <div className="space-y-3">
        <GlassCard variants={item} className="!p-5">
          <div className="mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle>{chartTitle}</CardTitle>
              <CardDescription className="mt-0.5">过去 {timeRange} 天价格走势（Price Trend）</CardDescription>
            </div>
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[90px] h-7 text-[12px] !bg-black/[0.03] dark:!bg-white/[0.06] !border-0 !shadow-none">
                <SelectValue placeholder="范围" />
              </SelectTrigger>
              <SelectContent>
                {timeRanges.map((range) => (
                  <SelectItem key={range.value} value={range.value}>
                    {range.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="h-[320px] w-full">
            {loading || !mounted ? (
              <div className="flex h-full items-center justify-center text-[13px] text-foreground/30">加载图表中...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                {selectedTickers.length > 1 ? (
                  <LineChart data={chartData} margin={{ top: 6, right: 8, left: 0, bottom: 2 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => {
                        const date = new Date(value)
                        return `${date.getMonth() + 1}/${date.getDate()}`
                      }}
                      tick={{ fontSize: 10, fill: "rgba(0,0,0,0.35)" }}
                      tickLine={false}
                      axisLine={false}
                      minTickGap={30}
                    />
                    <YAxis
                      domain={["auto", "auto"]}
                      tickFormatter={(value) => `¥${value.toLocaleString()}`}
                      tick={{ fontSize: 10, fill: "rgba(0,0,0,0.35)" }}
                      tickLine={false}
                      axisLine={false}
                      width={56}
                    />
                    <Tooltip contentStyle={tooltipStyle} labelFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <Legend wrapperStyle={{ fontSize: "11px", color: "rgba(0,0,0,0.5)" }} />
                    {selectedTickers.map((ticker, index) => (
                      <Line key={ticker} type="monotone" dataKey={ticker} stroke={COLORS[index % COLORS.length]} strokeWidth={1.6} dot={false} connectNulls />
                    ))}
                  </LineChart>
                ) : (
                  <AreaChart data={chartData} margin={{ top: 6, right: 8, left: 0, bottom: 2 }}>
                    <defs>
                      <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS[0]} stopOpacity={0.16} />
                        <stop offset="95%" stopColor={COLORS[0]} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => {
                        const date = new Date(value)
                        return `${date.getMonth() + 1}/${date.getDate()}`
                      }}
                      tick={{ fontSize: 10, fill: "rgba(0,0,0,0.35)" }}
                      tickLine={false}
                      axisLine={false}
                      minTickGap={30}
                    />
                    <YAxis
                      domain={["auto", "auto"]}
                      tickFormatter={(value) => `¥${value.toLocaleString()}`}
                      tick={{ fontSize: 10, fill: "rgba(0,0,0,0.35)" }}
                      tickLine={false}
                      axisLine={false}
                      width={56}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      formatter={(value?: number | string) => [`¥${Number(value ?? 0).toFixed(2)}`, "价格 (Price)"]}
                    />
                    <Area type="monotone" dataKey={selectedTickers[0]} stroke={COLORS[0]} strokeWidth={1.6} fillOpacity={1} fill="url(#colorPrice)" />
                  </AreaChart>
                )}
              </ResponsiveContainer>
            )}
          </div>
        </GlassCard>

        <GlassCard variants={item} className="!p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-black/[0.04] dark:border-white/[0.04]">
            <CardTitle>自选列表（Watchlist）</CardTitle>
          </div>
          <div className="divide-y divide-black/[0.03] dark:divide-white/[0.04]">
            {assets.map((asset) => {
              const ticker = asset.ticker
              const name = asset.alias || asset.name || asset.ticker
              const tickerData = data?.[ticker] || []
              const currentPrice = tickerData.length > 0 ? tickerData[tickerData.length - 1].price : 0
              const previousPrice = tickerData.length > 1 ? tickerData[tickerData.length - 2].price : 0
              const change = previousPrice > 0 ? (currentPrice - previousPrice) / previousPrice : 0

              const isSelected = selectedTickers.includes(ticker)
              const colorIndex = selectedTickers.indexOf(ticker)
              const color = isSelected ? COLORS[colorIndex % COLORS.length] : undefined

              return (
                <div
                  key={ticker}
                  onClick={() => toggleTicker(ticker)}
                  className={cn(
                    "flex items-center justify-between px-5 py-3 transition-all duration-200 cursor-pointer",
                    isSelected ? "bg-black/[0.02] dark:bg-white/[0.03]" : "hover:bg-black/[0.015] dark:hover:bg-white/[0.02]"
                  )}
                >
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      {isSelected && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />}
                      <span className={cn("text-[13px] font-medium", isSelected ? "text-foreground/90" : "text-foreground/65")}>{name}</span>
                    </div>
                    <span className="text-[11px] text-foreground/30 pl-3.5">{ticker}</span>
                  </div>
                  <div className="flex flex-col items-end gap-0.5">
                    <span className="text-[13px] font-medium text-foreground/80">{formatCurrency(currentPrice)}</span>
                    <span className={cn("text-[11px] font-medium", change >= 0 ? "text-red-500/70" : "text-emerald-500/70")}>{formatPercent(change)}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </GlassCard>
      </div>
    </motion.div>
  )
}
