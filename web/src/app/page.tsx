"use client"

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

import { MeasuredChart } from "@/components/charts/measured-chart"
import { Skeleton } from "@/components/ui/skeleton"
import {
  api as apiClient,
  type Asset,
  type AutoTradingStatusResponse,
  type MarketReviewResponse,
  type PaperAccountInfo,
  type PricePoint,
  type UserAssetOverview,
} from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import {
  diffBeijingCalendarDays,
  formatDateInBeijing,
  formatDateTimeInBeijing,
  formatMonthDayInBeijing,
  formatTimeInBeijing,
  toBeijingDate,
} from "@/lib/time"
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

const tooltipStyle = {
  backgroundColor: "var(--chart-tooltip-bg)",
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  borderRadius: "18px",
  border: "1px solid var(--chart-tooltip-border)",
  boxShadow: "var(--chart-tooltip-shadow)",
  padding: "10px 12px",
  fontSize: "12px",
}

function formatDateLabel(value: string) {
  return formatMonthDayInBeijing(value, value)
}

function parseFreshnessDate(value?: string | null) {
  if (!value) return null
  return toBeijingDate(value)
}

function hasExplicitTime(value?: string | null) {
  return Boolean(value && /(?:T|\s)\d{1,2}:\d{2}/.test(value))
}

function formatFreshnessSource(value?: string | null) {
  const date = parseFreshnessDate(value)
  if (!date) return "未获取"
  if (hasExplicitTime(value)) {
    return formatTimeInBeijing(date, { hour: "2-digit", minute: "2-digit", hour12: false }, "未获取")
  }
  return formatMonthDayInBeijing(date, "未获取")
}

function resolveFreshnessLabel(values: Array<string | null | undefined>) {
  const candidates = values
    .map((value) => ({ raw: value, date: parseFreshnessDate(value) }))
    .filter((item): item is { raw: string; date: Date } => Boolean(item.raw && item.date))

  if (candidates.length === 0) return "待同步"

  const freshest = candidates.reduce((latest, item) => (item.date > latest.date ? item : latest))
  const lagDays = diffBeijingCalendarDays(new Date(), freshest.date) ?? 0

  if (lagDays > 0) {
    return `已滞后 ${lagDays} 天`
  }

  if (hasExplicitTime(freshest.raw)) {
    return `${formatTimeInBeijing(freshest.date, { hour: "2-digit", minute: "2-digit", hour12: false })} 已更新`
  }

  return "今日已更新"
}

export default function HomePage() {
  const [assetPool, setAssetPool] = useState<Asset[]>([])
  const [portfolio, setPortfolio] = useState<UserAssetOverview | null>(null)
  const [account, setAccount] = useState<PaperAccountInfo["portfolio"] | null>(null)
  const [autoStatus, setAutoStatus] = useState<AutoTradingStatusResponse | null>(null)
  const [marketReview, setMarketReview] = useState<MarketReviewResponse | null>(null)
  const [priceData, setPriceData] = useState<Record<string, PricePoint[]>>({})
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [loadingAssetPool, setLoadingAssetPool] = useState(true)
  const [loadingPortfolio, setLoadingPortfolio] = useState(true)
  const [loadingAccount, setLoadingAccount] = useState(true)
  const [loadingAutoStatus, setLoadingAutoStatus] = useState(true)
  const [loadingMarketReview, setLoadingMarketReview] = useState(true)
  const [accountLoadError, setAccountLoadError] = useState(false)

  useEffect(() => {
    let cancelled = false
    const maxRetryAttempts = 2
    const retryDelayMs = 1200

    const fetchAssetPool = async (attempt = 0) => {
      try {
        const val = await apiClient.stz.getAssetPool()
        if (cancelled) return
        setAssetPool(val ?? [])
        setSelectedTickers((val ?? []).slice(0, 6).map((asset) => asset.ticker))
        setLoadingAssetPool(false)
      } catch {
        if (cancelled) return
        if (attempt < maxRetryAttempts - 1) {
          setTimeout(() => void fetchAssetPool(attempt + 1), retryDelayMs)
        } else {
          setLoadingAssetPool(false)
        }
      }
    }

    const fetchPortfolio = async (attempt = 0) => {
      try {
        const val = await apiClient.user.assets.getOverview(false)
        if (cancelled) return
        setPortfolio(val)
        setLoadingPortfolio(false)
      } catch {
        if (cancelled) return
        if (attempt < maxRetryAttempts - 1) {
          setTimeout(() => void fetchPortfolio(attempt + 1), retryDelayMs)
        } else {
          setLoadingPortfolio(false)
        }
      }
    }

    const fetchAccount = async (attempt = 0) => {
      try {
        const val = await apiClient.trading.paper.getAccount()
        if (cancelled) return
        setAccount(val?.portfolio ?? null)
        setAccountLoadError(false)
        setLoadingAccount(false)
      } catch {
        if (cancelled) return
        if (attempt < maxRetryAttempts - 1) {
          setTimeout(() => void fetchAccount(attempt + 1), retryDelayMs)
        } else {
          setAccountLoadError(true)
          setLoadingAccount(false)
        }
      }
    }

    const fetchAutoStatus = async (attempt = 0) => {
      try {
        const val = await apiClient.trading.auto.getStatus()
        if (cancelled) return
        setAutoStatus(val)
        setLoadingAutoStatus(false)
      } catch {
        if (cancelled) return
        if (attempt < maxRetryAttempts - 1) {
          setTimeout(() => void fetchAutoStatus(attempt + 1), retryDelayMs)
        } else {
          setLoadingAutoStatus(false)
        }
      }
    }

    const fetchMarketReview = async (attempt = 0) => {
      try {
        const val = await apiClient.market.dailyReview("cn")
        if (cancelled) return
        setMarketReview(val)
        setLoadingMarketReview(false)
      } catch {
        if (cancelled) return
        if (attempt < maxRetryAttempts - 1) {
          setTimeout(() => void fetchMarketReview(attempt + 1), retryDelayMs)
        } else {
          setLoadingMarketReview(false)
        }
      }
    }

    void fetchAssetPool()
    void fetchPortfolio()
    void fetchAccount()
    void fetchAutoStatus()
    void fetchMarketReview()

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

  const assetLabelMap = useMemo(
    () =>
      Object.fromEntries(
        assetPool.map((asset) => [asset.ticker, asset.alias || asset.name || asset.ticker]),
      ),
    [assetPool],
  )

  const scannerUpdatedAt = useMemo(() => {
    const datedAssets = assetPool
      .map((asset) => ({ raw: asset.last_price_date, date: parseFreshnessDate(asset.last_price_date) }))
      .filter((item): item is { raw: string; date: Date } => Boolean(item.raw && item.date))

    if (datedAssets.length === 0) return null
    return datedAssets.reduce((latest, item) => (item.date > latest.date ? item : latest)).raw
  }, [assetPool])

  const holdingsUpdatedAt = portfolio?.summary.updated_at ?? null
  const marketReviewUpdatedAt = marketReview?.date ?? null
  const freshnessLabel = resolveFreshnessLabel([
    marketReviewUpdatedAt,
    scannerUpdatedAt,
    holdingsUpdatedAt,
  ])
  const freshnessDetail = `复盘 ${formatFreshnessSource(marketReviewUpdatedAt)} · 扫描 ${formatFreshnessSource(scannerUpdatedAt)} · 持仓 ${formatFreshnessSource(holdingsUpdatedAt)}`
  const autoRunSummary = autoStatus?.daemon.last_trading_run
    ? formatDateTimeInBeijing(autoStatus.daemon.last_trading_run)
    : "尚未执行"
  const autoUniverseSummary =
    autoStatus?.config.universe_mode === "cn_a_share"
      ? "A股全市场"
      : `${autoStatus?.universe_summary?.ticker_count ?? autoStatus?.config.universe.length ?? assetPool.length} 个`

  const summaryCards = [
    {
      label: "模拟账户权益",
      value: account ? formatCurrency(account.total_assets) : accountLoadError ? "加载失败" : "未创建",
      detail: account ? `现金 ${formatCurrency(account.cash)}` : accountLoadError ? "无法读取模拟账户" : "可在模拟交易页创建账户",
      footer: account ? `持仓市值 ${formatCurrency(account.market_value)}` : null,
      loading: loadingAccount,
    },
    {
      label: "个人资产市值",
      value: portfolio ? formatCurrency(portfolio.summary.total_market_value) : "待同步",
      detail: portfolio ? `共 ${portfolio.summary.asset_count} 项持仓` : "进入资产页后可继续编辑定投与持仓",
      footer: holdingsUpdatedAt ? `估值 ${formatFreshnessSource(holdingsUpdatedAt)}` : null,
      loading: loadingPortfolio,
    },
    {
      label: "自动交易",
      value: autoStatus?.safety?.auto_trading_allowed === false ? "硬门禁关闭" : autoStatus?.config.enabled ? "已启用" : "手动模式",
      detail: autoStatus
        ? `${autoStatus.config.strategy_ids.length} 个策略 · ${autoStatus.daemon.daemon_running ? "调度器在线" : "调度器离线"}`
        : "可在模拟交易页配置策略与频率",
      footer: `最近执行 ${autoRunSummary} · ${autoUniverseSummary}`,
      loading: loadingAutoStatus,
    },
    {
      label: "数据新鲜度",
      value: freshnessLabel,
      detail: freshnessDetail,
      footer: "来源：复盘 / 扫描 / 持仓估值",
      loading: loadingMarketReview || loadingAssetPool || loadingPortfolio,
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

  const toggleObservedTicker = (ticker: string) => {
    setSelectedTickers((current) => {
      if (current.includes(ticker)) {
        return current.length === 1 ? current : current.filter((value) => value !== ticker)
      }
      return [...current, ticker]
    })
  }

  const formatObservedPrice = (value?: number | string | null) => {
    const numeric = Number(value ?? 0)
    return Number.isFinite(numeric) ? numeric.toFixed(4) : "—"
  }

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
      <motion.section variants={item}>
        <div className="data-panel rounded-[30px] p-5">
          <div className="section-title">今日状态</div>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((summary) => (
              <div
                key={summary.label}
                className="data-panel-muted flex h-full min-h-[164px] flex-col rounded-[22px] px-4 py-3"
              >
                <div className="data-metric-label">{summary.label}</div>
                {summary.loading ? (
                  <div className="mt-3 space-y-2 flex-1 flex flex-col justify-between">
                    <Skeleton className="h-7 w-3/4 rounded-md" />
                    <Skeleton className="h-4 w-5/6 rounded-md" />
                    <Skeleton className="h-4 w-1/2 rounded-md mt-auto" />
                  </div>
                ) : (
                  <>
                    <div className="mt-2 min-h-[50px] text-[1.28rem] font-semibold tabular-nums tracking-tight text-foreground/92">
                      {summary.value}
                    </div>
                    <div className="data-metric-secondary min-h-[46px]">{summary.detail}</div>
                    <div className="data-metric-secondary mt-auto pt-3">
                      {summary.footer ?? "\u00A0"}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </motion.section>

      <motion.section variants={item}>
        <div className="data-panel rounded-[30px] p-5">
          <div className="section-title">个人收益情况</div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {rangeSummaries.map((range) => {
              const positive = range.value >= 0
              return (
                <div key={range.label} className="data-panel-muted rounded-[22px] px-4 py-3">
                  <div className="data-metric-label">{range.label}</div>
                  {loadingPortfolio ? (
                    <Skeleton className="mt-2 h-6 w-2/3 rounded-md" />
                  ) : (
                    <div
                      className={cn(
                        "mt-2 text-[1.16rem] font-semibold tabular-nums tracking-tight",
                        positive ? "text-tone-cinnabar" : "text-tone-celadon",
                      )}
                    >
                      {positive ? "+" : ""}
                      {formatCurrency(range.value)}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </motion.section>

      <motion.section
        variants={item}
        className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_332px]"
      >
        <div className="data-panel overflow-hidden rounded-[34px] p-6 sm:p-7">
          <div>
            <div>
              <div className="section-title">资产池观察</div>
            </div>
          </div>

          <div className="mt-6 h-[260px] w-full md:h-[280px]">
            {loadingAssetPool ? (
              <div className="data-empty flex h-full items-center justify-center">正在整理资产池数据…</div>
            ) : chartRows.length === 0 ? (
              <div className="data-empty flex h-full items-center justify-center">暂未取到可展示的价格序列。</div>
            ) : selectedTickers.length === 1 ? (
              <MeasuredChart height={280}>
                {(width, height) => (
                <AreaChart width={width} height={height} data={chartRows} margin={{ top: 10, right: 6, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="workspaceChartFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="rgb(var(--rgb-celadon))" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="rgb(var(--rgb-celadon))" stopOpacity={0.01} />
                    </linearGradient>
                    <filter id="glow-area" x="-20%" y="-20%" width="140%" height="140%">
                      <feGaussianBlur stdDeviation="3.5" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>
                  <CartesianGrid vertical={false} stroke={SONG_COLORS.grid} strokeDasharray="4 6" opacity={0.6} />
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
                    labelFormatter={(value) => formatDateInBeijing(value, {}, String(value))}
                    formatter={(value?: number | string) => [
                      formatObservedPrice(value),
                      assetLabelMap[selectedTickers[0]] || selectedTickers[0],
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey={selectedTickers[0]}
                    stroke="rgb(var(--rgb-celadon))"
                    strokeWidth={2.2}
                    filter="url(#glow-area)"
                    fill="url(#workspaceChartFill)"
                    activeDot={{ r: 5, strokeWidth: 0, fill: "rgb(var(--rgb-celadon))" }}
                  />
                </AreaChart>
                )}
              </MeasuredChart>
            ) : (
              <MeasuredChart height={280}>
                {(width, height) => (
                <LineChart width={width} height={height} data={chartRows} margin={{ top: 10, right: 6, left: -18, bottom: 0 }}>
                  <defs>
                    <filter id="glow-line" x="-20%" y="-20%" width="140%" height="140%">
                      <feGaussianBlur stdDeviation="3" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>
                  <CartesianGrid vertical={false} stroke={SONG_COLORS.grid} strokeDasharray="4 6" opacity={0.6} />
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
                    labelFormatter={(value) => formatDateInBeijing(value, {}, String(value))}
                    formatter={(value?: number | string, ticker?: string) => [
                      formatObservedPrice(value),
                      assetLabelMap[String(ticker)] || String(ticker),
                    ]}
                  />
                  {selectedTickers.map((ticker, index) => (
                    <Line
                      key={ticker}
                      type="monotone"
                      dataKey={ticker}
                      stroke={chartPalette[index % chartPalette.length]}
                      strokeWidth={2}
                      filter="url(#glow-line)"
                      dot={false}
                      activeDot={{ r: 5, strokeWidth: 0 }}
                      connectNulls
                    />
                  ))}
                </LineChart>
                )}
              </MeasuredChart>
            )}
          </div>
        </div>

        <div className="data-panel rounded-[34px] p-5">
          <div className="section-title">资产池列表</div>

          <div className="mt-5 divide-y divide-black/[0.06] space-y-3">
            {loadingAssetPool ? (
              <div className="space-y-3 py-2">
                <Skeleton className="h-[62px] w-full rounded-[20px]" />
                <Skeleton className="h-[62px] w-full rounded-[20px]" />
                <Skeleton className="h-[62px] w-full rounded-[20px]" />
              </div>
            ) : watchRows.length === 0 ? (
              <div className="py-6 text-sm text-foreground/68">资产池为空时，这里会显示最近关注的标的。</div>
            ) : (
              watchRows.map((asset) => (
                <button
                  key={asset.ticker}
                  type="button"
                  onClick={() => toggleObservedTicker(asset.ticker)}
                  className={cn(
                    "grid w-full grid-cols-[minmax(0,1fr)_112px] items-center gap-3 rounded-[20px] border px-3 py-3 text-left transition-colors",
                    selectedTickers.includes(asset.ticker)
                      ? "border-[rgba(var(--rgb-ochre),0.34)] bg-[rgba(var(--rgb-ochre),0.16)] text-[rgb(var(--rgb-ink))] shadow-[0_8px_18px_rgba(41,33,25,0.04)]"
                      : "border-[rgba(var(--rgb-ink),0.06)] bg-[rgba(var(--rgb-xuan),0.78)] text-foreground/78 hover:bg-[rgba(var(--rgb-xuan),0.94)] hover:text-foreground/92"
                  )}
                >
                  <div className="min-w-0">
                    <div className="truncate text-[0.95rem] font-medium">
                      {asset.alias || asset.name || asset.ticker}
                    </div>
                    <div className="mt-1 text-[0.82rem] tabular-nums text-foreground/66">{asset.ticker}</div>
                  </div>
                  <div className="min-w-[112px] text-right">
                    <div className="text-sm tabular-nums font-medium">{asset.current > 0 ? formatCurrency(asset.current) : "—"}</div>
                    <div
                      className={cn(
                        "mt-1 text-[0.84rem] tabular-nums font-medium",
                        asset.change >= 0 ? "text-tone-cinnabar" : "text-tone-celadon"
                      )}
                    >
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
