"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  ArrowRight,
  Bot,
  Compass,
  Layers3,
  PlayCircle,
  WalletCards,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { MeasuredChart } from "@/components/charts/measured-chart"
import { api as apiClient, type Asset, type AutoTradingStatusResponse, type PaperAccountInfo, type PricePoint, type UserAssetOverview } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { useAuth } from "@/lib/auth-context"
import { getWorkspaceGroups } from "@/lib/workspace-nav"
import { cn, formatCurrency, formatPercent } from "@/lib/utils"

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.08 } },
}

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] as const } },
}

const chartPalette = [SONG_COLORS.celadon, SONG_COLORS.indigo, SONG_COLORS.plum, SONG_COLORS.ochre]

const toneClasses = {
  indigo: "from-[#6F7C8E]/12 via-[#6F7C8E]/4 to-transparent",
  celadon: "from-[#4D7358]/12 via-[#4D7358]/4 to-transparent",
  plum: "from-[#7A6973]/12 via-[#7A6973]/4 to-transparent",
  ochre: "from-[#B08E61]/12 via-[#B08E61]/4 to-transparent",
  ink: "from-[#4D4742]/12 via-[#4D4742]/4 to-transparent",
} as const

const tooltipStyle = {
  backgroundColor: "rgba(248, 244, 238, 0.96)",
  borderRadius: "18px",
  border: "1px solid rgba(77, 71, 66, 0.10)",
  boxShadow: "0 18px 40px rgba(41, 33, 25, 0.10)",
  padding: "10px 12px",
  fontSize: "12px",
}

function formatDateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export default function HomePage() {
  const { user } = useAuth()
  const isAdmin = user?.role === "admin"
  const workspaceGroups = useMemo(() => getWorkspaceGroups(isAdmin), [isAdmin])

  const [assetPool, setAssetPool] = useState<Asset[]>([])
  const [portfolio, setPortfolio] = useState<UserAssetOverview | null>(null)
  const [account, setAccount] = useState<PaperAccountInfo["portfolio"] | null>(null)
  const [autoStatus, setAutoStatus] = useState<AutoTradingStatusResponse | null>(null)
  const [priceData, setPriceData] = useState<Record<string, PricePoint[]>>({})
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    const loadWorkspace = async () => {
      setLoading(true)

      const [assetPoolResult, portfolioResult, accountResult, autoResult] = await Promise.allSettled([
        apiClient.stz.getAssetPool(),
        apiClient.user.assets.getOverview(false),
        apiClient.trading.paper.getAccount(),
        apiClient.trading.auto.getStatus(),
      ])

      if (cancelled) {
        return
      }

      const nextAssetPool = assetPoolResult.status === "fulfilled" ? assetPoolResult.value ?? [] : []
      setAssetPool(nextAssetPool)
      setSelectedTickers(nextAssetPool.slice(0, 4).map((asset) => asset.ticker))

      setPortfolio(portfolioResult.status === "fulfilled" ? portfolioResult.value : null)
      setAccount(accountResult.status === "fulfilled" ? accountResult.value?.portfolio ?? null : null)
      setAutoStatus(autoResult.status === "fulfilled" ? autoResult.value : null)
      setLoading(false)
    }

    void loadWorkspace()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (assetPool.length === 0) {
      return
    }

    let cancelled = false
    const tickers = assetPool.slice(0, 6).map((asset) => asset.ticker)

    const loadPrices = async () => {
      try {
        const response = await apiClient.data.getPrices(tickers, 90)
        if (!cancelled && response?.data) {
          setPriceData(response.data)
        }
      } catch {
        if (!cancelled) {
          setPriceData({})
        }
      }
    }

    void loadPrices()
    return () => {
      cancelled = true
    }
  }, [assetPool])

  const chartRows = useMemo(() => {
    if (selectedTickers.length === 0) return []

    const dateSet = new Set<string>()
    selectedTickers.forEach((ticker) => {
      priceData[ticker]?.forEach((point) => dateSet.add(point.date))
    })

    return Array.from(dateSet)
      .sort()
      .map((date) => {
        const row: Record<string, string | number> = { date }
        selectedTickers.forEach((ticker) => {
          const point = priceData[ticker]?.find((entry) => entry.date === date)
          if (point) {
            row[ticker] = point.price
          }
        })
        return row
      })
  }, [priceData, selectedTickers])

  const watchRows = useMemo(() => {
    return assetPool.slice(0, 6).map((asset) => {
      const series = priceData[asset.ticker] ?? []
      const current = series.at(-1)?.price ?? 0
      const previous = series.at(-2)?.price ?? current
      const change = previous > 0 ? (current - previous) / previous : 0

      return {
        ...asset,
        current,
        change,
      }
    })
  }, [assetPool, priceData])

  const summaryCards = [
    {
      label: "模拟账户权益",
      value: account ? formatCurrency(account.total_assets) : "待连接",
      detail: account ? `现金 ${formatCurrency(account.cash)}` : "连接后显示权益与现金结构",
    },
    {
      label: "个人资产市值",
      value: portfolio ? formatCurrency(portfolio.summary.total_market_value) : "待同步",
      detail: portfolio ? `共 ${portfolio.summary.asset_count} 项持仓` : "进入资产页后可继续编辑定投与持仓",
    },
    {
      label: "自动交易状态",
      value: autoStatus?.config.enabled ? "已启用" : "手动模式",
      detail: autoStatus ? `${autoStatus.config.strategy_ids.length} 个候选策略` : "可在模拟交易页配置策略与频率",
    },
  ]

  const heroHighlights = [
    {
      icon: Compass,
      title: "先进入工作台",
      text: "先看全局概览、当日状态和关键提醒，再决定接下来进入哪一组工作区。",
    },
    {
      icon: Bot,
      title: "再切到研究",
      text: "AI分析、大盘复盘、市场扫描、预测研究和决策仪表盘都收进同一组二级导航。",
    },
    {
      icon: PlayCircle,
      title: "最后去执行",
      text: "模拟交易、策略回测与量化策略继续保持连贯，避免在顶栏里堆成一排。",
    },
  ]

  const rangeSummaries = [
    {
      label: "日变化",
      value: portfolio?.summary.day_change ?? 0,
    },
    {
      label: "周变化",
      value: portfolio?.summary.week_change ?? 0,
    },
    {
      label: "月变化",
      value: portfolio?.summary.month_change ?? 0,
    },
    {
      label: "年变化",
      value: portfolio?.summary.year_change ?? 0,
    },
  ]

  const autoRunSummary = autoStatus?.daemon.last_trading_run
    ? new Date(autoStatus.daemon.last_trading_run).toLocaleString("zh-CN")
    : "尚未执行"
  const autoUniverseSummary =
    autoStatus?.config.universe_mode === "cn_a_share"
      ? "A股全市场"
      : `${autoStatus?.universe_summary?.ticker_count ?? autoStatus?.config.universe.length ?? assetPool.length} 个`

  const selectedLabel =
    selectedTickers.length === 1
      ? watchRows.find((item) => item.ticker === selectedTickers[0])?.alias ||
        watchRows.find((item) => item.ticker === selectedTickers[0])?.name ||
        selectedTickers[0]
      : "资产池观察"

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
      <motion.section
        variants={item}
        className="grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_360px]"
      >
        <div className="relative overflow-hidden rounded-[34px] border border-black/[0.07] bg-[linear-gradient(135deg,rgba(248,244,238,0.96),rgba(242,236,228,0.84))] px-6 py-7 shadow-[0_30px_70px_rgba(41,33,25,0.08)] sm:px-8 sm:py-8">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(111,124,142,0.12),transparent_34%),radial-gradient(circle_at_12%_18%,rgba(176,142,97,0.12),transparent_26%)]" />
          <div className="relative max-w-3xl">
            <div className="text-[11px] font-medium tracking-[0.24em] text-foreground/34">今日总览</div>
            <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-0.04em] text-foreground/92 sm:text-[38px]">
              把研究、执行、资产与系统安排在同一张清雅而清晰的案头上。
            </h1>
            <p className="mt-4 max-w-2xl text-[14px] leading-7 text-foreground/56 sm:text-[15px]">
              顶部只保留五个一级工作区：工作台、研究、执行、资产、系统。进入一级后，左侧再显示对应二级页面，让层级更稳定，也更适合长期研习与记录。
            </p>
          </div>

          <div className="relative mt-8 grid gap-3 sm:grid-cols-3">
            {heroHighlights.map((highlight) => (
              <div
                key={highlight.title}
                className="rounded-[24px] border border-black/[0.05] bg-white/62 p-4 shadow-[0_12px_32px_rgba(41,33,25,0.04)]"
              >
                <div className="flex items-center gap-2 text-[13px] font-medium text-foreground/84">
                  <highlight.icon className="h-4 w-4 text-[#6F7C8E]" />
                  {highlight.title}
                </div>
                <p className="mt-2 text-[13px] leading-6 text-foreground/54">{highlight.text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-[30px] border border-black/[0.07] bg-[rgba(247,243,237,0.95)] p-5 shadow-[0_24px_60px_rgba(41,33,25,0.06)]">
            <div className="text-[11px] font-medium tracking-[0.22em] text-foreground/34">今日状态</div>
            <div className="mt-3 text-[20px] font-semibold tracking-[-0.03em] text-foreground/90">
              当前工作面
            </div>
            <div className="mt-5 space-y-3">
              {summaryCards.map((summary) => (
                <div key={summary.label} className="rounded-[22px] border border-black/[0.05] bg-white/72 px-4 py-3">
                  <div className="text-[12px] text-foreground/42">{summary.label}</div>
                  <div className="mt-1 text-[18px] font-semibold tracking-[-0.03em] text-foreground/88">{summary.value}</div>
                  <div className="mt-1 text-[12px] leading-5 text-foreground/48">{summary.detail}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[30px] border border-black/[0.07] bg-[rgba(247,243,237,0.95)] p-5 shadow-[0_20px_52px_rgba(41,33,25,0.05)]">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[11px] font-medium tracking-[0.22em] text-foreground/34">自动交易</div>
                <div className="mt-2 text-[17px] font-semibold tracking-[-0.02em] text-foreground/88">
                  {autoStatus?.config.enabled ? "自动执行中" : "等待手动配置"}
                </div>
              </div>
              <div
                className={cn(
                  "rounded-full px-2.5 py-1 text-[11px] font-medium",
                  autoStatus?.config.enabled ? "bg-market-up-soft text-market-up" : "bg-black/[0.05] text-foreground/56"
                )}
              >
                {autoStatus?.daemon.daemon_running ? "调度器在线" : "调度器离线"}
              </div>
            </div>
            <div className="mt-4 space-y-2 text-[12px] leading-6 text-foreground/52">
              <div>最近执行：{autoRunSummary}</div>
              <div>策略数：{autoStatus?.config.strategy_ids.length ?? 0} 个</div>
              <div>标的池：{autoUniverseSummary}</div>
            </div>
            <Button asChild variant="outline" className="mt-4 w-full justify-between rounded-2xl">
              <Link href="/trading">
                进入模拟交易
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </motion.section>

      <motion.section
        variants={item}
        className="grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_360px]"
      >
        <div className="overflow-hidden rounded-[34px] border border-black/[0.07] bg-[rgba(247,243,237,0.92)] shadow-[0_30px_72px_rgba(41,33,25,0.06)]">
          <div className="border-b border-black/[0.06] px-6 py-5 sm:px-7">
            <div className="text-[11px] font-medium tracking-[0.22em] text-foreground/34">工作脉络</div>
            <h2 className="mt-2 text-[24px] font-semibold tracking-[-0.03em] text-foreground/90">主工作流</h2>
            <p className="mt-2 max-w-2xl text-[13px] leading-6 text-foreground/52">
              相关功能不再全部堆在顶栏里，而是按一级工作区和左侧二级导航重新组织，便于先定方向，再进入具体页面。
            </p>
          </div>

          <div className="divide-y divide-black/[0.06]">
            {workspaceGroups.map((group) => (
              <div key={group.id} className="grid gap-4 px-6 py-5 sm:grid-cols-[220px_minmax(0,1fr)] sm:px-7">
                <div className="relative">
                  <div className={cn("absolute inset-y-0 left-0 w-12 rounded-full bg-gradient-to-b opacity-80 blur-2xl", toneClasses[group.tone])} />
                  <div className="relative flex items-start gap-3">
                    <div className="rounded-[20px] border border-black/[0.05] bg-white/74 p-2.5 text-foreground/78">
                      <group.icon className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-[16px] font-semibold tracking-[-0.02em] text-foreground/88">{group.name}</div>
                      <p className="mt-1 text-[13px] leading-6 text-foreground/50">{group.description}</p>
                    </div>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {group.items.map((itemLink) => (
                    <Link
                      key={itemLink.href}
                      href={itemLink.href}
                      className="group rounded-[24px] border border-black/[0.05] bg-white/72 px-4 py-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-black/[0.08] hover:bg-white/88"
                    >
                      <div className="flex items-center gap-2 text-[13px] font-medium text-foreground/84">
                        <itemLink.icon className="h-4 w-4 text-foreground/52 transition-transform duration-200 group-hover:-translate-y-0.5" />
                        {itemLink.name}
                      </div>
                      <p className="mt-2 text-[12px] leading-6 text-foreground/50">{itemLink.description}</p>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-[30px] border border-black/[0.07] bg-[rgba(247,243,237,0.95)] p-5 shadow-[0_24px_60px_rgba(41,33,25,0.05)]">
            <div className="flex items-center gap-2 text-[12px] font-medium tracking-[0.18em] text-foreground/34">
              <WalletCards className="h-4 w-4" />
              资产脉络
            </div>
            <div className="mt-4 grid gap-3">
              {rangeSummaries.map((range) => {
                const positive = range.value >= 0
                return (
                  <div key={range.label} className="flex items-center justify-between rounded-[22px] border border-black/[0.05] bg-white/70 px-4 py-3">
                    <span className="text-[13px] text-foreground/58">{range.label}</span>
                    <span className={cn("text-[14px] font-semibold tracking-[-0.02em]", positive ? "text-market-up" : "text-market-down")}>
                      {positive ? "+" : ""}
                      {formatCurrency(range.value)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="rounded-[30px] border border-black/[0.07] bg-[rgba(247,243,237,0.95)] p-5 shadow-[0_20px_52px_rgba(41,33,25,0.05)]">
            <div className="flex items-center gap-2 text-[12px] font-medium tracking-[0.18em] text-foreground/34">
              <Layers3 className="h-4 w-4" />
              下一步
            </div>
            <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-foreground/88">从工作区直接进入当前任务</div>
            <p className="mt-2 text-[13px] leading-6 text-foreground/52">
              如果要继续优化持仓与定投，进入资产；如果要验证策略，则从执行区切到回测与自动交易。
            </p>
            <div className="mt-4 grid gap-2">
              <Button asChild variant="outline" className="justify-between rounded-2xl">
                <Link href="/portfolio">
                  进入个人资产
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" className="justify-between rounded-2xl">
                <Link href="/dashboard-llm">
                  进入决策仪表盘
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section
        variants={item}
        className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_360px]"
      >
        <div className="overflow-hidden rounded-[34px] border border-black/[0.07] bg-[rgba(247,243,237,0.94)] p-6 shadow-[0_26px_64px_rgba(41,33,25,0.05)] sm:p-7">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="text-[11px] font-medium tracking-[0.22em] text-foreground/34">静观标的</div>
              <h2 className="mt-2 text-[24px] font-semibold tracking-[-0.03em] text-foreground/90">{selectedLabel}</h2>
              <p className="mt-2 text-[13px] leading-6 text-foreground/52">从资产池中选取少量核心标的，保持低噪声的观察视角。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {watchRows.slice(0, 4).map((asset) => {
                const active = selectedTickers.includes(asset.ticker)
                return (
                  <button
                    key={asset.ticker}
                    type="button"
                    onClick={() =>
                      setSelectedTickers((current) => {
                        if (current.includes(asset.ticker)) {
                          return current.length === 1 ? current : current.filter((ticker) => ticker !== asset.ticker)
                        }
                        return [...current, asset.ticker]
                      })
                    }
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-[12px] transition-colors",
                      active
                        ? "border-black/[0.08] bg-white/88 text-foreground/86"
                        : "border-black/[0.05] bg-white/54 text-foreground/54 hover:bg-white/75"
                    )}
                  >
                    {asset.alias || asset.name || asset.ticker}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="mt-6 h-[320px] w-full">
            {loading ? (
              <div className="flex h-full items-center justify-center text-[13px] text-foreground/36">正在整理资产池数据…</div>
            ) : chartRows.length === 0 ? (
              <div className="flex h-full items-center justify-center text-[13px] text-foreground/36">暂未取到可展示的价格序列。</div>
            ) : selectedTickers.length === 1 ? (
              <MeasuredChart height={320}>
                {(width, height) => (
                <AreaChart width={width} height={height} data={chartRows} margin={{ top: 10, right: 6, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="workspaceChartFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={SONG_COLORS.indigo} stopOpacity={0.22} />
                      <stop offset="95%" stopColor={SONG_COLORS.indigo} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke={SONG_COLORS.grid} strokeDasharray="4 6" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDateLabel}
                    tick={{ fill: SONG_COLORS.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={28}
                  />
                  <YAxis
                    tick={{ fill: SONG_COLORS.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(value) => new Date(value).toLocaleDateString("zh-CN")}
                    formatter={(value?: number | string) => [Number(value ?? 0).toFixed(4), "价格"]}
                  />
                  <Area
                    type="monotone"
                    dataKey={selectedTickers[0]}
                    stroke={SONG_COLORS.indigo}
                    strokeWidth={1.8}
                    fill="url(#workspaceChartFill)"
                  />
                </AreaChart>
                )}
              </MeasuredChart>
            ) : (
              <MeasuredChart height={320}>
                {(width, height) => (
                <LineChart width={width} height={height} data={chartRows} margin={{ top: 10, right: 6, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={SONG_COLORS.grid} strokeDasharray="4 6" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDateLabel}
                    tick={{ fill: SONG_COLORS.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={28}
                  />
                  <YAxis
                    tick={{ fill: SONG_COLORS.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelFormatter={(value) => new Date(value).toLocaleDateString("zh-CN")} />
                  {selectedTickers.map((ticker, index) => (
                    <Line
                      key={ticker}
                      type="monotone"
                      dataKey={ticker}
                      stroke={chartPalette[index % chartPalette.length]}
                      strokeWidth={1.7}
                      dot={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
                )}
              </MeasuredChart>
            )}
          </div>
        </div>

        <div className="rounded-[34px] border border-black/[0.07] bg-[rgba(247,243,237,0.94)] p-5 shadow-[0_24px_60px_rgba(41,33,25,0.05)]">
          <div className="text-[11px] font-medium tracking-[0.22em] text-foreground/34">轻量观察</div>
          <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.03em] text-foreground/90">轻量观察列表</h2>
          <p className="mt-2 text-[13px] leading-6 text-foreground/52">
            保留少量关键资产，避免把首页做成拥挤的行情大屏。更深入的研究可继续进入对应工作区。
          </p>

          <div className="mt-5 divide-y divide-black/[0.06]">
            {watchRows.length === 0 ? (
              <div className="py-6 text-[13px] text-foreground/42">资产池为空时，这里会显示最近关注的标的。</div>
            ) : (
              watchRows.map((asset) => (
                <button
                  key={asset.ticker}
                  type="button"
                  onClick={() => setSelectedTickers([asset.ticker])}
                  className="flex w-full items-center justify-between gap-3 py-3 text-left"
                >
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium text-foreground/86">
                      {asset.alias || asset.name || asset.ticker}
                    </div>
                    <div className="mt-1 text-[12px] text-foreground/44">{asset.ticker}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[13px] font-medium text-foreground/84">{asset.current > 0 ? formatCurrency(asset.current) : "—"}</div>
                    <div className={cn("mt-1 text-[12px] font-medium", asset.change >= 0 ? "text-market-up" : "text-market-down")}>
                      {asset.change >= 0 ? "+" : ""}
                      {formatPercent(asset.change)}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </motion.section>
    </motion.div>
  )
}
