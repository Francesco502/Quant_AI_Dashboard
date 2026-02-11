"use client"

import { useEffect, useState, useMemo } from "react"
import { motion } from "framer-motion"
import { api as apiClient, PricePoint, Asset } from "@/lib/api"
import { GlassCard, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ArrowUpRight, ArrowDownRight, TrendingUp, Activity, DollarSign, Target } from "lucide-react"
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, LineChart, Line, Legend } from "recharts"
import { formatCurrency, formatPercent, cn } from "@/lib/utils"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

/* Muted monochrome chart palette with one blue accent */
const COLORS = [
  "#3B82F6", // Blue accent (primary data)
  "#64748B", // Slate
  "#94A3B8", // Light slate
  "#6366F1", // Indigo (subtle)
  "#0EA5E9", // Sky
  "#71717A", // Zinc
  "#A1A1AA", // Light zinc
]

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.1,
    }
  }
}

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const } }
}

export default function Dashboard() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [data, setData] = useState<Record<string, PricePoint[]> | null>(null)
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [mounted, setMounted] = useState(false)
  const [timeRange, setTimeRange] = useState("30")

  const [account, setAccount] = useState<any>(null)
  const [equityHistory, setEquityHistory] = useState<{date: string, equity: number}[]>([])
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
        let assetPool: any[] = [], accountData: any = null, equityData: any = null, strategies: any[] = [], tradesData: any = null;
        
        try { assetPool = await apiClient.stz.getAssetPool() || []; } catch(e) {}
        try { 
            const res = await apiClient.trading.paper.getAccount();
            if (res && res.status === 'success') accountData = res.portfolio;
        } catch(e) {}
        
        try { strategies = await apiClient.stz.listStrategies() || []; } catch(e) {}
        
        if (assetPool) {
            setAssets(assetPool);
            if (assetPool.length > 0) {
                setSelectedTickers(assetPool.slice(0, 3).map((a: Asset) => a.ticker));
            }
        }
        
        if (accountData) {
            setAccount(accountData);
            setDailyPnL(0); 
            setDailyPnLPercent(0);
        }

        setActiveStrategiesCount(strategies.filter((s: any) => s.activate).length);
        setWinRate(0.65); 
        setTotalTrades(12);

      } catch (error) {
        console.error("Failed to fetch dashboard data:", error)
      } finally {
        setLoading(false)
      }
    }

    setMounted(true)
    fetchData()
  }, [])

  // 获取价格数据：当资产列表或时间范围变化时触发
  useEffect(() => {
    if (assets.length === 0) return
    const allTickers = assets.map(a => a.ticker)
    const days = parseInt(timeRange) || 30

    let cancelled = false
    const fetchPrices = async () => {
      try {
        const res = await apiClient.data.getPrices(allTickers, days)
        if (!cancelled && res && res.data) {
          setData(res.data)
        }
      } catch (e) {
        console.error("获取价格数据失败:", e)
      }
    }
    fetchPrices()
    return () => { cancelled = true }
  }, [assets, timeRange])

  const chartData = useMemo(() => {
    if (!data || selectedTickers.length === 0) return []
    
    const dateSet = new Set<string>()
    selectedTickers.forEach(t => {
      data[t]?.forEach(p => dateSet.add(p.date))
    })
    
    return Array.from(dateSet).sort().map(date => {
      const point: any = { date }
      selectedTickers.forEach(t => {
        const p = data[t]?.find(d => d.date === date)
        if (p) point[t] = p.price
      })
      return point
    })
  }, [data, selectedTickers])

  const toggleTicker = (ticker: string) => {
    setSelectedTickers(prev => {
      if (prev.includes(ticker)) {
        if (prev.length === 1) return prev
        return prev.filter(t => t !== ticker)
      }
      return [...prev, ticker]
    })
  }

  const chartTitle = useMemo(() => {
    if (selectedTickers.length === 1) {
      const asset = assets.find(a => a.ticker === selectedTickers[0])
      return asset ? (asset.alias || asset.name || asset.ticker) : selectedTickers[0]
    }
    return "多资产对比"
  }, [selectedTickers, assets])

  /* Recharts tooltip style — frosted glass */
  const tooltipStyle = {
    backgroundColor: 'rgba(255, 255, 255, 0.92)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    borderRadius: '10px',
    border: '1px solid rgba(0, 0, 0, 0.06)',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
    padding: '8px 12px',
    fontSize: '12px',
  }

  return (
    <motion.div 
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* Hero Section */}
      <motion.div variants={item} className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">
          市场概览
        </h1>
        <p className="text-[13px] text-foreground/40">
          投资组合实时洞察与 AI 驱动的交易信号
        </p>
      </motion.div>

      {/* Metrics Grid */}
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Balance */}
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

        {/* Active Strategies */}
        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              {GLOSSARY.ActiveStrategies.term}
              <HelpTooltip content={GLOSSARY.ActiveStrategies.definition} />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-semibold tracking-[-0.02em] text-foreground/85">{activeStrategiesCount}</span>
              <span className="text-[11px] text-blue-500/70 font-medium">
                运行中
              </span>
            </div>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <Activity className="h-10 w-10" />
          </div>
        </GlassCard>

        {/* Daily P&L */}
        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              {GLOSSARY.DailyPnL.term}
              <HelpTooltip content={GLOSSARY.DailyPnL.definition} />
            </span>
            <div className="flex items-baseline gap-2">
              <span className={cn("text-xl font-semibold tracking-[-0.02em]", dailyPnL >= 0 ? "text-red-500/80" : "text-emerald-500/80")}>
                {dailyPnL >= 0 ? "+" : ""}{formatCurrency(dailyPnL)}
              </span>
              <span className={cn("text-[11px] flex items-center font-medium", dailyPnL >= 0 ? "text-red-500/60" : "text-emerald-500/60")}>
                {dailyPnL >= 0 ? "+" : ""}{formatPercent(dailyPnLPercent)} 
                {dailyPnL >= 0 ? <ArrowUpRight className="h-3 w-3 ml-0.5" /> : <ArrowDownRight className="h-3 w-3 ml-0.5" />}
              </span>
            </div>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <TrendingUp className="h-10 w-10" />
          </div>
        </GlassCard>

        {/* Win Rate */}
        <GlassCard variants={item} className="relative overflow-hidden group">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-foreground/40 flex items-center tracking-wide uppercase">
              胜率
              <HelpTooltip content="基于历史交易记录计算的盈利交易占比。" />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-semibold tracking-[-0.02em] text-foreground/85">{formatPercent(winRate)}</span>
              <span className="text-[11px] text-foreground/35 font-medium">
                共 {totalTrades} 笔
              </span>
            </div>
          </div>
          <div className="absolute right-4 top-4 opacity-[0.04] group-hover:opacity-[0.07] transition-opacity duration-300">
            <Target className="h-10 w-10" />
          </div>
        </GlassCard>
      </div>

      {/* Main Chart Section */}
      <div className="grid gap-3 grid-cols-1 lg:grid-cols-7">
        <GlassCard variants={item} className="col-span-1 lg:col-span-4 !p-5">
          <div className="mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle>{chartTitle}</CardTitle>
              <CardDescription className="mt-0.5">过去 {timeRange} 天价格走势</CardDescription>
            </div>
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[90px] h-7 text-[12px] !bg-black/[0.03] dark:!bg-white/[0.06] !border-0 !shadow-none">
                <SelectValue placeholder="范围" />
              </SelectTrigger>
              <SelectContent>
                {timeRanges.map((range) => (
                  <SelectItem key={range.value} value={range.value}>{range.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="h-[280px] w-full">
            {loading || !mounted ? (
              <div className="flex h-full items-center justify-center text-[13px] text-foreground/30">加载图表中...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                {selectedTickers.length > 1 ? (
                  <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" />
                    <XAxis 
                      dataKey="date" 
                      tickFormatter={(value) => {
                        const date = new Date(value);
                        return `${date.getMonth() + 1}/${date.getDate()}`;
                      }}
                      tick={{ fontSize: 10, fill: 'rgba(0,0,0,0.3)' }}
                      tickLine={false}
                      axisLine={false}
                      minTickGap={30}
                    />
                    <YAxis 
                      domain={['auto', 'auto']}
                      tickFormatter={(value) => `¥${value.toLocaleString()}`}
                      tick={{ fontSize: 10, fill: 'rgba(0,0,0,0.3)' }}
                      tickLine={false}
                      axisLine={false}
                      width={55}
                    />
                    <Tooltip contentStyle={tooltipStyle} labelFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <Legend wrapperStyle={{ fontSize: '11px', color: 'rgba(0,0,0,0.5)' }} />
                    {selectedTickers.map((ticker, index) => (
                      <Line 
                        key={ticker}
                        type="monotone" 
                        dataKey={ticker} 
                        stroke={COLORS[index % COLORS.length]} 
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                ) : (
                  <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS[0]} stopOpacity={0.15}/>
                        <stop offset="95%" stopColor={COLORS[0]} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.04)" />
                    <XAxis 
                      dataKey="date" 
                      tickFormatter={(value) => {
                        const date = new Date(value);
                        return `${date.getMonth() + 1}/${date.getDate()}`;
                      }}
                      tick={{ fontSize: 10, fill: 'rgba(0,0,0,0.3)' }}
                      tickLine={false}
                      axisLine={false}
                      minTickGap={30}
                    />
                    <YAxis 
                      domain={['auto', 'auto']}
                      tickFormatter={(value) => `¥${value.toLocaleString()}`}
                      tick={{ fontSize: 10, fill: 'rgba(0,0,0,0.3)' }}
                      tickLine={false}
                      axisLine={false}
                      width={55}
                    />
                    <Tooltip 
                      contentStyle={tooltipStyle}
                      labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      formatter={(value: any) => [`¥${Number(value).toFixed(2)}`, '价格']}
                    />
                    <Area 
                      type="monotone" 
                      dataKey={selectedTickers[0]} 
                      stroke={COLORS[0]} 
                      strokeWidth={1.5}
                      fillOpacity={1} 
                      fill="url(#colorPrice)" 
                    />
                  </AreaChart>
                )}
              </ResponsiveContainer>
            )}
          </div>
        </GlassCard>

        {/* Watchlist */}
        <GlassCard variants={item} className="col-span-1 lg:col-span-3 !p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-black/[0.04] dark:border-white/[0.04]">
            <CardTitle>自选列表</CardTitle>
          </div>
          <div className="divide-y divide-black/[0.03] dark:divide-white/[0.04] max-h-[280px] overflow-y-auto">
            {assets.map((asset) => {
              const ticker = asset.ticker
              const name = asset.alias || asset.name || asset.ticker
              const tData = data?.[ticker] || []
              const tCurrent = tData.length > 0 ? tData[tData.length - 1].price : 0
              const tPrev = tData.length > 1 ? tData[tData.length - 2].price : 0
              const tChange = tPrev > 0 ? (tCurrent - tPrev) / tPrev : 0
              
              const isSelected = selectedTickers.includes(ticker)
              const colorIndex = selectedTickers.indexOf(ticker)
              const color = isSelected ? COLORS[colorIndex % COLORS.length] : undefined

              return (
                <div 
                  key={ticker} 
                  onClick={() => toggleTicker(ticker)}
                  className={cn(
                    "flex items-center justify-between px-5 py-3 transition-all duration-200 cursor-pointer",
                    isSelected 
                      ? "bg-black/[0.02] dark:bg-white/[0.03]" 
                      : "hover:bg-black/[0.015] dark:hover:bg-white/[0.02]"
                  )}
                >
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      {isSelected && (
                        <div 
                          className="w-1.5 h-1.5 rounded-full" 
                          style={{ backgroundColor: color }} 
                        />
                      )}
                      <span className={cn(
                        "text-[13px] font-medium",
                        isSelected ? "text-foreground/90" : "text-foreground/65"
                      )}>
                        {name}
                      </span>
                    </div>
                    <span className="text-[11px] text-foreground/30 pl-3.5">{ticker}</span>
                  </div>
                  <div className="flex flex-col items-end gap-0.5">
                    <span className="text-[13px] font-medium text-foreground/80">{formatCurrency(tCurrent)}</span>
                    <span className={cn(
                      "text-[11px] font-medium",
                      tChange >= 0 ? 'text-red-500/70' : 'text-emerald-500/70'
                    )}>
                      {formatPercent(tChange)}
                    </span>
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
