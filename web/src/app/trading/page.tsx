"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts"
import {
  Activity,
  Bot,
  ChartNoAxesColumn,
  Clock3,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Wallet,
  Workflow,
} from "lucide-react"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { MetricCard } from "@/components/data/metric-card"
import { StatusPill } from "@/components/data/status-pill"
import { MultiAssetPicker } from "@/components/shared/multi-asset-picker"
import { OrderForm, type OrderRequest } from "@/components/trading/OrderForm"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import {
  api,
  type Asset,
  type AutoTradingAccountSnapshot,
  type AutoTradingConfig,
  type AutoTradingStatusResponse,
  type EquityCurve,
  type PaperAccountInfo,
  type PerformanceMetrics,
  type TradeHistoryRecord,
  type UnknownRecord,
} from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { formatDateTimeInBeijing } from "@/lib/time"
import { cn, formatCurrency } from "@/lib/utils"

type WorkspaceTab = "overview" | "automation" | "manual"
type NoticeState = { tone: "success" | "error"; text: string } | null
type RecentOrderRow = {
  order_id: string
  symbol: string
  side: string
  order_type: string
  quantity: number
  status: string
  created_at?: string | null
  avg_fill_price?: number | null
}

const ORDER_TYPE_TEXT: Record<string, string> = {
  MARKET: "市价",
  LIMIT: "限价",
  STOP: "止损",
  STOP_LIMIT: "止损限价",
}

const FALLBACK_AUTO_CONFIG: AutoTradingConfig = {
  enabled: true,
  interval_minutes: 60,
  username: "admin",
  account_name: "全市场自动模拟交易",
  initial_capital: 100000,
  strategy_ids: [
    "sma_crossover",
    "ema_crossover",
    "mean_reversion",
    "rsi_reversion",
    "macd_trend",
    "breakout_momentum",
    "donchian_breakout",
    "momentum_rotation",
  ],
  universe_mode: "cn_a_share",
  universe: [],
  universe_limit: 0,
  max_positions: 3,
  evaluation_days: 180,
  min_total_return: 0,
  min_sharpe_ratio: 0,
  max_drawdown: 0.35,
  top_n_strategies: 3,
}

function normalizeAutoConfig(config?: Partial<AutoTradingConfig> | null): AutoTradingConfig {
  const universeMode =
    config?.universe_mode === "asset_pool" || config?.universe_mode === "cn_a_share" || config?.universe_mode === "manual"
      ? config.universe_mode
      : FALLBACK_AUTO_CONFIG.universe_mode
  return {
    ...FALLBACK_AUTO_CONFIG,
    ...config,
    universe_mode: universeMode,
    strategy_ids: Array.isArray(config?.strategy_ids) ? config?.strategy_ids : FALLBACK_AUTO_CONFIG.strategy_ids,
    universe: Array.isArray(config?.universe) ? config?.universe : FALLBACK_AUTO_CONFIG.universe,
    universe_limit: typeof config?.universe_limit === "number" ? config.universe_limit : FALLBACK_AUTO_CONFIG.universe_limit,
  }
}

function buildAccountFromSnapshot(snapshot: AutoTradingAccountSnapshot | null): PaperAccountInfo | null {
  if (!snapshot?.found || !snapshot.account_id) return null
  const positions = snapshot.portfolio?.positions ?? snapshot.positions ?? []
  const totalAssets =
    snapshot.portfolio?.total_assets ??
    ((snapshot.balance ?? 0) + (snapshot.portfolio?.market_value ?? 0))
  return {
    status: "success",
    account_id: snapshot.account_id,
    account_name: snapshot.account_name,
    currency: "CNY",
    portfolio: {
      total_assets: totalAssets,
      cash: snapshot.portfolio?.cash ?? snapshot.balance ?? 0,
      market_value: snapshot.portfolio?.market_value ?? 0,
      positions,
    },
  }
}

function mergeAssetChoices(
  pool: Asset[],
  personalAssets: Array<{ ticker: string; asset_name?: string | null }>,
  pinnedTickers: string[],
): Asset[] {
  const registry = new Map<string, Asset>()

  const upsert = (asset: Asset) => {
    const ticker = asset.ticker.trim().toUpperCase()
    if (!ticker) return
    const current = registry.get(ticker)
    registry.set(ticker, {
      ticker,
      name: asset.name || current?.name || ticker,
      alias: asset.alias || current?.alias,
      last_price: asset.last_price ?? current?.last_price,
    })
  }

  for (const asset of pool) upsert(asset)
  for (const asset of personalAssets) {
    upsert({
      ticker: asset.ticker,
      name: asset.asset_name || asset.ticker,
    })
  }
  for (const ticker of pinnedTickers) {
    upsert({ ticker, name: ticker })
  }

  return Array.from(registry.values()).sort((left, right) => left.ticker.localeCompare(right.ticker))
}

function normalizeRecentOrders(rows: UnknownRecord[] | undefined): RecentOrderRow[] {
  if (!Array.isArray(rows)) return []
  return rows.flatMap((row) => {
    const record = row as Record<string, unknown>
    const orderId = typeof record.order_id === "string" ? record.order_id : ""
    const symbol = typeof record.symbol === "string" ? record.symbol : ""
    if (!orderId || !symbol) return []
    return [
      {
        order_id: orderId,
        symbol,
        side: typeof record.side === "string" ? record.side : "-",
        order_type: typeof record.order_type === "string" ? record.order_type : "-",
        quantity: typeof record.quantity === "number" ? record.quantity : Number(record.quantity ?? 0),
        status: typeof record.status === "string" ? record.status : "-",
        created_at: typeof record.created_at === "string" ? record.created_at : null,
        avg_fill_price:
          typeof record.avg_fill_price === "number" ? record.avg_fill_price : Number(record.avg_fill_price ?? 0),
      },
    ]
  })
}

function formatDateTime(value?: string | null) {
  return formatDateTimeInBeijing(value, {}, "暂未记录")
}

function formatSignedCurrency(value: number) {
  const sign = value > 0 ? "+" : value < 0 ? "-" : ""
  return `${sign}${formatCurrency(Math.abs(value))}`
}

function formatSignedPercent(value: number) {
  const sign = value > 0 ? "+" : value < 0 ? "" : ""
  return `${sign}${value.toFixed(2)}%`
}

function toneClass(value: number) {
  if (value > 0) return "text-tone-positive"
  if (value < 0) return "text-tone-negative"
  return "text-foreground/85"
}

function inferPermissionError(message: string) {
  const normalized = message.toLowerCase()
  return (
    normalized.includes("permission") ||
    normalized.includes("forbidden") ||
    normalized.includes("admin") ||
    normalized.includes("not enough") ||
    message.includes("权限")
  )
}

function SummaryMetric({
  label,
  value,
  help,
  accent = SONG_COLORS.ink,
  secondary,
}: {
  label: string
  value: string
  help?: string
  accent?: string
  secondary?: string
}) {
  return (
    <MetricCard
      label={label}
      value={value}
      secondary={secondary}
      help={help}
      accentColor={accent}
      compact
      surface="muted"
      className="h-full rounded-[24px]"
      valueClassName="mt-2 text-[1.42rem] font-semibold tracking-[-0.03em]"
    />
  )
}

function StatusBanner({ notice }: { notice: NoticeState }) {
  if (!notice) return null
  const isSuccess = notice.tone === "success"
  return (
    <div
      className={cn(
        "rounded-[24px] border px-4 py-3 text-sm leading-7",
        isSuccess
          ? "surface-tone-celadon text-tone-negative"
          : "surface-tone-cinnabar text-tone-cinnabar",
      )}
    >
      {notice.text}
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-black/[0.08] px-4 py-10 text-center text-sm text-muted-foreground">
      {text}
    </div>
  )
}

function toUiNotice(error: unknown, fallback: string) {
  const raw = error instanceof Error ? error.message : fallback
  const normalized = raw.toLowerCase()

  if (
    normalized.includes("failed to fetch") ||
    normalized.includes("cannot reach api service") ||
    normalized.includes("networkerror")
  ) {
    return "当前无法连接后端服务，请确认 8685 后端已启动，且前端地址已被后端允许。"
  }

  return raw
}

function withTimeout<T>(promise: Promise<T>, fallback: T, timeoutMs: number) {
  return Promise.race([
    promise,
    new Promise<T>((resolve) => {
      window.setTimeout(() => resolve(fallback), timeoutMs)
    }),
  ])
}

export default function TradingPage() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview")
  const [notice, setNotice] = useState<NoticeState>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [autoBusy, setAutoBusy] = useState<"save" | "run" | "reset" | "create" | null>(null)

  const [account, setAccount] = useState<PaperAccountInfo | null>(null)
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null)
  const [equityCurve, setEquityCurve] = useState<EquityCurve | null>(null)
  const [tradeHistory, setTradeHistory] = useState<TradeHistoryRecord[]>([])
  const [recentOrders, setRecentOrders] = useState<RecentOrderRow[]>([])

  const [assetOptions, setAssetOptions] = useState<Asset[]>([])
  const [autoStatus, setAutoStatus] = useState<AutoTradingStatusResponse | null>(null)
  const [autoAccessDenied, setAutoAccessDenied] = useState(false)
  const [configDraft, setConfigDraft] = useState<AutoTradingConfig>(FALLBACK_AUTO_CONFIG)

  const [manualTicker, setManualTicker] = useState("")
  const [latestPrice, setLatestPrice] = useState(0)
  const [quoteLoading, setQuoteLoading] = useState(false)

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 4200)
    return () => window.clearTimeout(timer)
  }, [notice])

  const loadWorkspace = useCallback(async (silent: boolean = false) => {
    if (silent) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    try {
      const autoStatusPromise = api.trading.auto
        .getStatus()
        .then(async (status) => {
          setAutoStatus(status)
          setAutoAccessDenied(false)
          setConfigDraft(normalizeAutoConfig(status.config))

          const snapshot = status.account?.found ? status.account : null
          const snapshotAccount = buildAccountFromSnapshot(snapshot)
          if (!snapshotAccount?.account_id) return null

          setAccount(snapshotAccount)
          setTradeHistory(snapshot?.recent_trades || [])
          setRecentOrders(snapshot ? normalizeRecentOrders(snapshot.recent_orders) : [])

          if (!snapshotAccount.account_id) return
          const [perfResult, curveResult] = await Promise.allSettled([
            api.trading.paper.getPerformance(snapshotAccount.account_id),
            api.trading.paper.getEquityCurve(snapshotAccount.account_id, 90),
          ])
          if (perfResult.status === "fulfilled") setPerformance(perfResult.value)
          if (curveResult.status === "fulfilled") setEquityCurve(curveResult.value)
          return snapshotAccount.account_id
        })
        .catch((error) => {
          const message = error instanceof Error ? error.message : "读取自动交易状态失败"
          const permissionDenied = inferPermissionError(message)
          setAutoAccessDenied(permissionDenied)
          if (!permissionDenied) {
            setNotice({ tone: "error", text: toUiNotice(new Error(message), "读取自动交易状态失败") })
          }
          return null
        })

      const [pool, personalOverview, preferredAccountId] = await Promise.all([
        withTimeout(api.stz.getAssetPool().catch(() => []), [], 1500),
        withTimeout(
          api.user.assets.getOverview(false).catch(() => ({ assets: [] })),
          { assets: [] },
          1500,
        ),
        withTimeout(autoStatusPromise, null, 2000),
      ])

      const mergedAssets = mergeAssetChoices(
        pool || [],
        personalOverview.assets || [],
        FALLBACK_AUTO_CONFIG.universe,
      )
      setAssetOptions(mergedAssets)

      if (!preferredAccountId) {
        setTradeHistory([])
        setRecentOrders([])
      }
      setManualTicker((current) => current || mergedAssets[0]?.ticker || "")

      void api.trading.paper
        .getAccount(preferredAccountId ?? undefined)
        .then(async (resolvedAccount) => {
          setAccount(resolvedAccount)
          const nextAccountId = resolvedAccount?.account_id

          if (!resolvedAccount || !nextAccountId) {
            setPerformance(null)
            setEquityCurve(null)
            return
          }

          setManualTicker((current) => current || resolvedAccount.portfolio.positions[0]?.ticker || mergedAssets[0]?.ticker || "")
          setTradeHistory(await api.trading.paper.getHistory(nextAccountId, 12).catch(() => []))

          if (!preferredAccountId) {
            const [perfResult, curveResult] = await Promise.allSettled([
              api.trading.paper.getPerformance(nextAccountId),
              api.trading.paper.getEquityCurve(nextAccountId, 90),
            ])

            if (perfResult.status === "fulfilled") setPerformance(perfResult.value)
            if (curveResult.status === "fulfilled") setEquityCurve(curveResult.value)
          }
        })
        .catch(() => {
          setAccount(null)
          setPerformance(null)
          setEquityCurve(null)
        })
    } catch (error) {
      setNotice({ tone: "error", text: toUiNotice(error, "读取模拟交易工作台失败") })
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadWorkspace()
  }, [loadWorkspace])

  const normalizedTicker = manualTicker.trim().toUpperCase()
  const positions = account?.portfolio.positions || []
  const selectedPosition = positions.find((position) => position.ticker.trim().toUpperCase() === normalizedTicker)
  const effectivePrice = latestPrice || selectedPosition?.current_price || selectedPosition?.avg_cost || 0
  const accountId = account?.account_id

  useEffect(() => {
    if (!normalizedTicker) {
      setLatestPrice(0)
      return
    }

    let cancelled = false
    setQuoteLoading(true)

    void api.data
      .getPrices([normalizedTicker], 90)
      .then((response) => {
        if (cancelled) return
        const series = response.data?.[normalizedTicker] || []
        const latest = series.at(-1)
        setLatestPrice(latest?.price || 0)
      })
      .catch(() => {
        if (!cancelled) setLatestPrice(0)
      })
      .finally(() => {
        if (!cancelled) setQuoteLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [normalizedTicker])

  const availableStrategies = autoStatus?.available_strategies || []
  const lastRunRecord = (autoStatus?.run_result || autoStatus?.daemon?.last_trading_result || {}) as Record<string, unknown>
  const latestValidatedStrategies = Array.isArray(lastRunRecord.validated_strategies)
    ? lastRunRecord.validated_strategies.filter((item): item is string => typeof item === "string")
    : []
  const latestPlacedOrders = Array.isArray(lastRunRecord.orders) ? lastRunRecord.orders.length : 0
  const latestPositions = Array.isArray(lastRunRecord.positions) ? lastRunRecord.positions.length : positions.length
  const equityPoints = equityCurve?.data || []
  const equityValues = equityPoints.map((point) => point.equity)
  const equityMin = equityValues.length > 0 ? Math.min(...equityValues) : 0
  const equityMax = equityValues.length > 0 ? Math.max(...equityValues) : 0
  const equityPad = equityValues.length > 0 ? Math.max((equityMax - equityMin) * 0.12, equityMax * 0.015, 200) : 0
  const autoRunState = autoStatus?.daemon?.trading_run_state ?? "idle"
  const autoActionLocked = autoBusy !== null || autoRunState === "running"

  const pollAutoTradingStatus = useCallback(
    async (attempt: number = 0) => {
      try {
        const status = await api.trading.auto.getStatus()
        setAutoStatus(status)
        setConfigDraft(normalizeAutoConfig(status.config))

        if (status.daemon?.trading_run_state === "running" && attempt < 40) {
          window.setTimeout(() => {
            void pollAutoTradingStatus(attempt + 1)
          }, 5000)
          return
        }

        await loadWorkspace(true)
      } catch {
        if (attempt < 12) {
          window.setTimeout(() => {
            void pollAutoTradingStatus(attempt + 1)
          }, 5000)
        }
      }
    },
    [loadWorkspace],
  )

  const handleRefresh = async () => {
    await loadWorkspace(true)
  }

  const persistAutoConfig = async () => {
    setAutoBusy("save")
    try {
      const response = await api.trading.auto.updateConfig(configDraft)
      setAutoStatus(response)
      setConfigDraft(normalizeAutoConfig(response.config))
      setNotice({ tone: "success", text: "自动交易配置已保存。" })
      await loadWorkspace(true)
    } catch (error) {
      setNotice({ tone: "error", text: toUiNotice(error, "保存自动交易配置失败") })
    } finally {
      setAutoBusy(null)
    }
  }

  const handleRunNow = async (resetFirst: boolean) => {
    setAutoBusy("run")
    try {
      const saved = await api.trading.auto.updateConfig(configDraft)
      const response = await api.trading.auto.runNow({
        reset_account: resetFirst,
        initial_balance: resetFirst ? configDraft.initial_capital : undefined,
      })
      setAutoStatus(response)
      setConfigDraft(normalizeAutoConfig(saved.config))
      setNotice({
        tone: "success",
        text: response.message || (resetFirst ? "已受理重置并执行自动交易任务。" : "已受理自动交易任务。"),
      })
      setActiveTab("overview")
      void pollAutoTradingStatus()
    } catch (error) {
      setNotice({ tone: "error", text: toUiNotice(error, "执行自动交易失败") })
    } finally {
      setAutoBusy(null)
    }
  }

  const handleResetAccount = async () => {
    if (!accountId) return
    if (!window.confirm("这会清空当前模拟账户的持仓与历史成交，并将资金重置为设定值。是否继续？")) return

    setAutoBusy("reset")
    try {
      await api.trading.paper.resetAccount(accountId, {
        initial_balance: configDraft.initial_capital,
        account_name: configDraft.account_name,
      })
      setNotice({ tone: "success", text: `模拟账户已重置为 ${formatCurrency(configDraft.initial_capital)}。` })
      await loadWorkspace(true)
    } catch (error) {
      setNotice({ tone: "error", text: toUiNotice(error, "重置模拟账户失败") })
    } finally {
      setAutoBusy(null)
    }
  }

  const handleCreateAccount = async () => {
    setAutoBusy("create")
    try {
      await api.trading.paper.createAccount({
        name: configDraft.account_name,
        initial_balance: configDraft.initial_capital,
      })
      setNotice({ tone: "success", text: "模拟账户已创建。" })
      await loadWorkspace(true)
    } catch (error) {
      setNotice({ tone: "error", text: toUiNotice(error, "创建模拟账户失败") })
    } finally {
      setAutoBusy(null)
    }
  }

  const handleSubmitOrder = async (order: OrderRequest) => {
    if (!accountId) {
      setNotice({ tone: "error", text: "当前没有可用的模拟账户。" })
      return
    }
    setAutoBusy("run")
    try {
      await api.trading.paper.placeOrder({
        account_id: accountId,
        ticker: order.ticker,
        action: order.side,
        shares: order.quantity,
        order_type: order.order_type,
        price: order.price,
        stop_price: order.stop_price,
      })
      setNotice({ tone: "success", text: `${order.side === "BUY" ? "买入" : "卖出"}订单已提交。` })
      await loadWorkspace(true)
      setActiveTab("overview")
    } catch (error) {
      setNotice({ tone: "error", text: toUiNotice(error, "提交手动订单失败") })
    } finally {
      setAutoBusy(null)
    }
  }

  const universeSummary = autoStatus?.universe_summary
  const selectedUniverseCount =
    configDraft.universe_mode === "manual"
      ? configDraft.universe.length
      : universeSummary?.ticker_count || 0
  const strategyCount = configDraft.strategy_ids.length
  const referenceInitialCapital =
    performance?.initial_capital ??
    autoStatus?.account?.initial_capital ??
    configDraft.initial_capital
  const effectiveTotalAssets = performance?.total_assets ?? account?.portfolio.total_assets ?? 0
  const cumulativeProfit = effectiveTotalAssets - referenceInitialCapital
  const cumulativeReturnPct = referenceInitialCapital > 0 ? (cumulativeProfit / referenceInitialCapital) * 100 : 0
  const performanceTone =
    cumulativeReturnPct > 0
      ? SONG_COLORS.celadon
      : cumulativeReturnPct < 0
        ? SONG_COLORS.cinnabar
        : SONG_COLORS.ink
  const daemonAccent = autoStatus?.daemon?.daemon_running ? SONG_COLORS.celadon : SONG_COLORS.ochre
  const evaluationAccent = latestValidatedStrategies.length > 0 ? SONG_COLORS.celadon : SONG_COLORS.ink
  const latestExecutionSummary = autoStatus?.daemon?.last_trading_run
    ? `最近 ${formatDateTime(autoStatus.daemon.last_trading_run)}`
    : !autoAccessDenied
      ? "当前页可直接重跑"
      : "当前账户无自动交易权限"

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-10">
      <section className="overflow-hidden rounded-[32px] border border-white/40 bg-white/30 p-7 shadow-[0_8px_32px_rgba(142,115,77,0.04)] backdrop-blur-2xl md:p-9">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <div className="space-y-3">
              <h1 className="page-title">模拟交易工作台</h1>
              <p className="page-subtitle max-w-3xl">
                在同一页查看账户净值、自动交易状态、执行记录与手动下单，先判断账户状态，再决定是否继续操作。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <StatusPill label="账户" value={account?.account_name || configDraft.account_name} icon={Wallet} tone="ink" />
              <StatusPill
                label="自动交易"
                value={configDraft.enabled ? "已启用" : "已暂停"}
                icon={Bot}
                tone={configDraft.enabled ? "ochre" : "ink"}
              />
              <span className="text-[0.88rem] leading-6 text-foreground/62">评估频率每 {configDraft.interval_minutes} 分钟</span>
            </div>
          </div>

          <div className="flex flex-col items-start gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing || loading}>
                <RefreshCw className={cn("mr-2 h-4 w-4", (refreshing || loading) && "animate-spin")} />
                刷新
              </Button>
              {!autoAccessDenied ? (
                <Button size="sm" onClick={() => void handleRunNow(false)} disabled={autoActionLocked}>
                  <PlayCircle className="mr-2 h-4 w-4" />
                  立即执行
                </Button>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[0.88rem] text-foreground/62">
              <Link className="transition-colors duration-200 hover:text-foreground" href="/strategies">
                查看策略库
              </Link>
              <Link className="transition-colors duration-200 hover:text-foreground" href="/backtest">
                进入回测中心
              </Link>
            </div>
          </div>
        </div>
      </section>

      <StatusBanner notice={notice} />

      {loading ? (
        <GlassCard className="p-10 text-center text-sm text-muted-foreground">正在读取模拟交易工作台，请稍候。</GlassCard>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SummaryMetric
              label="总资产"
              value={formatCurrency(account?.portfolio.total_assets || 0)}
              secondary={`基准资金 ${formatCurrency(referenceInitialCapital)}`}
              help="现金与持仓市值之和。"
            />
            <SummaryMetric
              label="累计收益"
              value={formatSignedCurrency(cumulativeProfit)}
              accent={performanceTone}
              secondary="对比账户基准资金的累计变化。"
              help="当前总资产减去账户初始资金。"
            />
            <SummaryMetric
              label="收益率"
              value={formatSignedPercent(cumulativeReturnPct)}
              accent={performanceTone}
              secondary={`可用资金 ${formatCurrency(account?.portfolio.cash || 0)}`}
              help="累计收益 ÷ 初始资金。"
            />
            <SummaryMetric
              label="自动策略"
              value={`${strategyCount} 个`}
              help="当前纳入自动评估与执行的策略数量。"
              accent={SONG_COLORS.indigo}
              secondary={`${autoStatus?.daemon?.daemon_running ? "守护进程运行中" : "守护进程未运行"} · ${latestExecutionSummary}`}
            />
          </div>

          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as WorkspaceTab)} className="space-y-8">
            <TabsList className="inline-flex h-auto w-auto max-w-full justify-start gap-1.5 overflow-x-auto rounded-[22px] border border-black/[0.05] bg-[rgba(249,245,239,0.78)] p-1.5 shadow-none">
              <TabsTrigger value="overview" className="rounded-xl px-4 py-2">
                账户总览
              </TabsTrigger>
              <TabsTrigger value="automation" className="rounded-xl px-4 py-2">
                自动交易
              </TabsTrigger>
              <TabsTrigger value="manual" className="rounded-xl px-4 py-2">
                手动交易
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-6">
              <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                <GlassCard className="space-y-4 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <CardTitle>账户权益曲线</CardTitle>
                      <CardDescription>统一观察模拟账户的权益变化，而不是分别去翻交易流水与账户快照。</CardDescription>
                    </div>
                    <Badge variant="outline" className="rounded-full border-black/[0.08] bg-white/70 px-3 py-1">
                      {equityPoints.length} 个观测点
                    </Badge>
                  </div>

                  {equityPoints.length > 0 ? (
                    <div className="h-[320px]">
                      <MeasuredChart height={320}>
                        {(width, height) => (
                          <AreaChart width={width} height={height} data={equityPoints}>
                            <defs>
                              <linearGradient id="trading-equity-fill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={SONG_COLORS.indigo} stopOpacity={0.24} />
                                <stop offset="100%" stopColor={SONG_COLORS.indigo} stopOpacity={0.02} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid stroke={SONG_COLORS.grid} vertical={false} strokeDasharray="3 3" />
                            <XAxis dataKey="date" tickLine={false} axisLine={false} stroke={SONG_COLORS.axis} minTickGap={34} />
                            <YAxis
                              tickLine={false}
                              axisLine={false}
                              stroke={SONG_COLORS.axis}
                              domain={[Math.max(0, equityMin - equityPad), equityMax + equityPad]}
                              tickFormatter={(value) => `¥${(Number(value) / 1000).toFixed(0)}k`}
                            />
                            <Tooltip
                              formatter={(value) => [formatCurrency(Number(value)), "权益"]}
                              labelFormatter={(label) => `日期：${label}`}
                              contentStyle={{
                                borderRadius: 18,
                                border: "1px solid rgba(0,0,0,0.06)",
                                backgroundColor: "rgba(255,255,255,0.95)",
                              }}
                            />
                            <Area
                              type="monotone"
                              dataKey="equity"
                              stroke={SONG_COLORS.indigo}
                              strokeWidth={2.2}
                              fill="url(#trading-equity-fill)"
                            />
                          </AreaChart>
                        )}
                      </MeasuredChart>
                    </div>
                  ) : (
                    <EmptyState text="当前还没有可展示的权益曲线数据。" />
                  )}
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                  <div className="space-y-1">
                    <CardTitle>自动执行状态</CardTitle>
                    <CardDescription>先看守护进程与最近执行，再决定是否进入自动交易配置。</CardDescription>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <SummaryMetric
                      label="守护进程"
                      value={autoStatus?.daemon?.daemon_running ? "运行中" : "未运行"}
                      accent={daemonAccent}
                      secondary={autoStatus?.daemon?.last_started_at ? `最近启动 ${formatDateTime(autoStatus?.daemon?.last_started_at)}` : "尚未启动"}
                    />
                    <SummaryMetric
                      label="最近执行"
                      value={
                        autoStatus?.daemon?.last_trading_run
                          ? formatDateTime(autoStatus?.daemon?.last_trading_run)
                          : "暂未执行"
                      }
                      accent={SONG_COLORS.indigo}
                      secondary={`${latestValidatedStrategies.length} 个策略通过 · ${latestPlacedOrders} 笔下单`}
                    />
                  </div>

                  <div className="rounded-[22px] border border-black/[0.05] bg-white/60 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground/80">
                      <Workflow className="h-4 w-4" />
                      评估与执行摘要
                    </div>
                    {latestValidatedStrategies.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {latestValidatedStrategies.map((strategyId) => (
                          <Badge key={strategyId} variant="outline" className="rounded-full border-black/[0.08] bg-white/70 px-3 py-1">
                            {strategyId}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">最近一次执行暂时没有通过策略，或尚未运行。</p>
                    )}
                    <div className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground">
                      <p>当前启用了 {configDraft.strategy_ids.length} 个策略，实际采用数量仍会受收益、夏普与回撤阈值约束。</p>
                      {typeof lastRunRecord.message === "string" ? <p>{lastRunRecord.message}</p> : null}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-3">
                    {!account ? (
                      <Button onClick={() => void handleCreateAccount()} disabled={autoActionLocked}>
                        <Wallet className="mr-2 h-4 w-4" />
                        创建模拟账户
                      </Button>
                    ) : (
                      <Button variant="outline" onClick={() => void handleResetAccount()} disabled={autoActionLocked}>
                        <RotateCcw className="mr-2 h-4 w-4" />
                        重置到账户初始资金
                      </Button>
                    )}
                    {!autoAccessDenied ? (
                      <Button variant="outline" onClick={() => void handleRunNow(false)} disabled={autoActionLocked}>
                        <PlayCircle className="mr-2 h-4 w-4" />
                        立即执行一次
                      </Button>
                    ) : null}
                  </div>
                </GlassCard>
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <GlassCard className="space-y-4 p-5">
                  <div className="flex items-center gap-2">
                    <ChartNoAxesColumn className="h-5 w-5" />
                    <div>
                      <CardTitle>当前持仓</CardTitle>
                      <CardDescription>用于确认自动交易当前持有的标的与浮动盈亏。</CardDescription>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px] text-sm">
                      <thead>
                        <tr className="border-b border-black/[0.06] text-left text-muted-foreground">
                          <th className="py-2">代码</th>
                          <th className="py-2 text-right">持仓</th>
                          <th className="py-2 text-right">成本</th>
                          <th className="py-2 text-right">现价</th>
                          <th className="py-2 text-right">市值</th>
                          <th className="py-2 text-right">浮盈亏</th>
                        </tr>
                      </thead>
                      <tbody>
                        {positions.length > 0 ? (
                          positions.map((position) => (
                            <tr key={position.ticker} className="border-b border-black/[0.05] last:border-b-0">
                              <td className="py-3 font-medium">{position.ticker}</td>
                              <td className="py-3 text-right">{position.shares}</td>
                              <td className="py-3 text-right">{formatCurrency(position.avg_cost)}</td>
                              <td className="py-3 text-right">{formatCurrency(position.current_price || position.avg_cost)}</td>
                              <td className="py-3 text-right">{formatCurrency(position.market_value || 0)}</td>
                              <td className={cn("py-3 text-right font-medium", toneClass(position.unrealized_pnl || 0))}>
                                {formatSignedCurrency(position.unrealized_pnl || 0)}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={6} className="py-8 text-center text-muted-foreground">
                              当前暂无持仓。
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                  <div className="flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    <div>
                      <CardTitle>最近成交</CardTitle>
                      <CardDescription>自动执行与手动下单都会在这里留下成交记录。</CardDescription>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px] text-sm">
                      <thead>
                        <tr className="border-b border-black/[0.06] text-left text-muted-foreground">
                          <th className="py-2">时间</th>
                          <th className="py-2">代码</th>
                          <th className="py-2">方向</th>
                          <th className="py-2 text-right">价格</th>
                          <th className="py-2 text-right">数量</th>
                          <th className="py-2 text-right">费用</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tradeHistory.length > 0 ? (
                          tradeHistory.map((trade, index) => (
                            <tr key={`${trade.ticker}-${trade.trade_time}-${index}`} className="border-b border-black/[0.05] last:border-b-0">
                              <td className="py-3">{formatDateTime(trade.trade_time)}</td>
                              <td className="py-3 font-medium">{trade.ticker}</td>
                              <td className={cn("py-3 font-medium", trade.action.toUpperCase() === "BUY" ? "text-tone-positive" : "text-tone-negative")}>
                                {trade.action.toUpperCase() === "BUY" ? "买入" : "卖出"}
                              </td>
                              <td className="py-3 text-right">{formatCurrency(trade.price)}</td>
                              <td className="py-3 text-right">{trade.shares}</td>
                              <td className="py-3 text-right">{formatCurrency(trade.fee || 0)}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={6} className="py-8 text-center text-muted-foreground">
                              还没有成交记录。
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </GlassCard>
              </div>
            </TabsContent>

            <TabsContent value="automation" className="space-y-6">
              {autoAccessDenied ? (
                <GlassCard className="space-y-3 p-5">
                  <CardTitle>自动交易配置仅管理员可用</CardTitle>
                  <CardDescription>当前账号可以查看模拟账户，但不能修改自动交易策略与守护进程配置。</CardDescription>
                </GlassCard>
              ) : (
                <>
                  <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
                    <GlassCard className="space-y-5 p-5">
                      <div className="space-y-1">
                        <CardTitle>自动交易配置</CardTitle>
                        <CardDescription>在这里决定是否自动执行、多久执行一次、评估哪些标的以及通过哪些策略筛选。</CardDescription>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="flex items-center gap-3 rounded-[22px] border border-black/[0.05] bg-white/60 px-4 py-3">
                          <Checkbox
                            checked={configDraft.enabled}
                            onCheckedChange={(checked) =>
                              setConfigDraft((current) => ({ ...current, enabled: Boolean(checked) }))
                            }
                          />
                          <div>
                            <div className="text-sm font-medium text-foreground/85">开启自动交易</div>
                            <div className="text-xs text-muted-foreground">关闭后只保留账户展示与手动下单。</div>
                          </div>
                        </label>

                        <div className="rounded-[22px] border border-black/[0.05] bg-white/60 px-4 py-3">
                          <div className="flex items-center gap-1 text-sm font-medium text-foreground/85">
                            守护进程状态
                            <HelpTooltip content="守护进程负责按设定频率评估策略并自动下单。" />
                          </div>
                          <div className="mt-2 flex items-center gap-2 text-sm">
                            <span
                              className="inline-flex h-2.5 w-2.5 rounded-full"
                              style={{
                                backgroundColor: daemonAccent,
                              }}
                            />
                            <span className="text-foreground/80">{autoStatus?.daemon?.daemon_running ? "运行中" : "未运行"}</span>
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label>执行账户用户名</Label>
                          <Input
                            value={configDraft.username}
                            onChange={(event) =>
                              setConfigDraft((current) => ({ ...current, username: event.target.value }))
                            }
                            placeholder="admin"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>模拟账户名称</Label>
                          <Input
                            value={configDraft.account_name}
                            onChange={(event) =>
                              setConfigDraft((current) => ({ ...current, account_name: event.target.value }))
                            }
                            placeholder="全市场自动模拟交易"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>初始资金</Label>
                          <Input
                            type="number"
                            value={String(configDraft.initial_capital)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                initial_capital: Number(event.target.value) || 100000,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>执行频率（分钟）</Label>
                          <Input
                            type="number"
                            min={5}
                            value={String(configDraft.interval_minutes)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                interval_minutes: Number(event.target.value) || 60,
                              }))
                            }
                          />
                        </div>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <div className="space-y-2">
                          <Label>
                            评估窗口
                            <HelpTooltip content="用于回看策略最近多少交易日的表现，时间太短会放大噪音，太长会降低响应速度。" />
                          </Label>
                          <Input
                            type="number"
                            min={30}
                            value={String(configDraft.evaluation_days)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                evaluation_days: Number(event.target.value) || 180,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>
                            最多持仓
                            <HelpTooltip content="自动交易单轮最多持有的标的数量，用于控制分散度与交易频率。" />
                          </Label>
                          <Input
                            type="number"
                            min={1}
                            value={String(configDraft.max_positions)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                max_positions: Number(event.target.value) || 3,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>
                            最低总收益
                            <HelpTooltip content="策略评估期累计收益阈值，0.03 表示至少 3% 才允许进入候选池。" />
                          </Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={String(configDraft.min_total_return)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                min_total_return: Number(event.target.value) || 0,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>
                            最低夏普
                            <HelpTooltip content="策略评估期的风险收益要求，数值越高越强调稳定性。" />
                          </Label>
                          <Input
                            type="number"
                            step="0.1"
                            value={String(configDraft.min_sharpe_ratio)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                min_sharpe_ratio: Number(event.target.value) || 0,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>
                            最大回撤
                            <HelpTooltip content="允许策略在评估期内承受的最大回撤比例，0.20 表示回撤超过 20% 会被淘汰。" />
                          </Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={String(configDraft.max_drawdown)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                max_drawdown: Number(event.target.value) || 0,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>
                            采用策略数
                            <HelpTooltip content="单轮执行后最多采用前几名策略，避免策略过多导致信号冲突。" />
                          </Label>
                          <Input
                            type="number"
                            min={1}
                            value={String(configDraft.top_n_strategies)}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                top_n_strategies: Number(event.target.value) || 1,
                              }))
                            }
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>
                          自动交易范围
                          <HelpTooltip content="可选手动标的池、资产池或 A 股全市场。若选择 A 股全市场，系统会对全市场股票做自动评估与模拟下单，而不是只盯住资产池。" />
                        </Label>
                        <div className="grid gap-2 md:grid-cols-3">
                          {[
                            { id: "cn_a_share", label: "A股全市场", note: "面向全市场自动选股与交易" },
                            { id: "asset_pool", label: "资产池", note: "仅在资产池中轮询与执行" },
                            { id: "manual", label: "手动标的池", note: "由你手动指定自动交易标的" },
                          ].map((option) => {
                            const active = configDraft.universe_mode === option.id
                            return (
                              <button
                                key={option.id}
                                type="button"
                                onClick={() =>
                                  setConfigDraft((current) => ({
                                    ...current,
                                    universe_mode: option.id as AutoTradingConfig["universe_mode"],
                                  }))
                                }
                                className={cn(
                                  "rounded-[22px] border px-4 py-3 text-left transition",
                                  active
                                    ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.07)] shadow-[0_10px_24px_rgba(142,115,77,0.06)]"
                                    : "border-black/[0.06] bg-white/60 hover:bg-white/80",
                                )}
                              >
                                <div className="text-sm font-medium text-foreground/85">{option.label}</div>
                                <div className="mt-1 text-xs leading-6 text-muted-foreground">{option.note}</div>
                              </button>
                            )
                          })}
                        </div>

                        {configDraft.universe_mode === "manual" ? (
                          <div className="space-y-2">
                            <MultiAssetPicker
                              assets={assetOptions}
                              selected={configDraft.universe}
                              onChange={(tickers) =>
                                setConfigDraft((current) => ({
                                  ...current,
                                  universe: tickers,
                                }))
                              }
                              placeholder="选择自动评估的手动标的池"
                              maxPreview={3}
                            />
                            <p className="text-xs text-muted-foreground">
                              当前手动纳入 {selectedUniverseCount} 个标的，建议保持在 5 至 20 个之间，既能分散又不会明显稀释信号质量。
                            </p>
                          </div>
                        ) : configDraft.universe_mode === "asset_pool" ? (
                          <div className="rounded-[22px] border border-black/[0.05] bg-white/60 px-4 py-3 text-sm text-muted-foreground">
                            将直接读取当前资产池作为自动交易范围。
                            {universeSummary?.ticker_count ? ` 当前资产池共 ${universeSummary.ticker_count} 个标的。` : ""}
                            {Array.isArray(universeSummary?.preview) && universeSummary.preview.length > 0
                              ? ` 示例：${universeSummary.preview.slice(0, 6).join(" / ")}`
                              : ""}
                          </div>
                        ) : (
                          <div className="space-y-3 rounded-[22px] border border-black/[0.05] bg-white/60 px-4 py-4">
                            <div className="text-sm text-muted-foreground">
                              当前将覆盖 A 股全市场进行策略评估和模拟下单。
                              {universeSummary?.ticker_count ? ` 当前可用标的约 ${universeSummary.ticker_count} 只。` : ""}
                            </div>
                            <div className="grid gap-3 md:grid-cols-[1fr_140px]">
                              <div className="text-xs leading-6 text-muted-foreground">
                                全市场模式会明显增加评估范围。首次运行可能较慢，后续会优先复用本地价格缓存。
                                {Array.isArray(universeSummary?.preview) && universeSummary.preview.length > 0
                                  ? ` 当前预览：${universeSummary.preview.slice(0, 8).join(" / ")}`
                                  : ""}
                              </div>
                              <div className="space-y-2">
                                <Label>
                                  范围上限
                                  <HelpTooltip content="0 表示不限制，直接使用全市场。若你希望加快评估，可临时限制候选数量，例如 800 或 1200。" />
                                </Label>
                                <Input
                                  type="number"
                                  min={0}
                                  step="100"
                                  value={String(configDraft.universe_limit)}
                                  onChange={(event) =>
                                    setConfigDraft((current) => ({
                                      ...current,
                                      universe_limit: Math.max(0, Number(event.target.value) || 0),
                                    }))
                                  }
                                />
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-3">
                        <Button onClick={() => void persistAutoConfig()} disabled={autoActionLocked}>
                          <Settings2 className="mr-2 h-4 w-4" />
                          保存配置
                        </Button>
                        <Button variant="outline" onClick={() => void handleRunNow(false)} disabled={autoActionLocked}>
                          <PlayCircle className="mr-2 h-4 w-4" />
                          保存并执行
                        </Button>
                        <Button variant="outline" onClick={() => void handleRunNow(true)} disabled={autoActionLocked}>
                          <RotateCcw className="mr-2 h-4 w-4" />
                          重置后执行
                        </Button>
                      </div>
                    </GlassCard>

                    <GlassCard className="space-y-5 p-5">
                      <div className="space-y-1">
                        <CardTitle>当前自动交易状态</CardTitle>
                        <CardDescription>这里强调“现在会怎么跑”，而不是把配置和状态分散在多个页面。</CardDescription>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SummaryMetric label="守护进程" value={autoStatus?.daemon?.daemon_running ? "运行中" : "未运行"} accent={daemonAccent} />
                        <SummaryMetric label="最近启动" value={autoStatus?.daemon?.last_started_at ? formatDateTime(autoStatus?.daemon?.last_started_at) : "暂无"} accent={SONG_COLORS.indigo} />
                        <SummaryMetric label="本轮持仓" value={`${latestPositions} 个`} accent={SONG_COLORS.ink} />
                        <SummaryMetric label="选中策略" value={`${latestValidatedStrategies.length} 个`} accent={evaluationAccent} />
                      </div>

                      <div className="rounded-[22px] border border-black/[0.05] bg-white/60 p-4">
                        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/80">
                          <ShieldCheck className="h-4 w-4" />
                          策略评估摘要
                        </div>
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <p>当前启用了 {configDraft.strategy_ids.length} 个策略，实际采用数量受收益、夏普与回撤阈值约束。</p>
                          <p>如果守护进程关闭或没有策略通过筛选，系统不会下单，只会保留状态更新。</p>
                        </div>
                        {latestValidatedStrategies.length > 0 ? (
                          <div className="mt-4 flex flex-wrap gap-2">
                            {latestValidatedStrategies.map((strategyId) => (
                              <Badge key={strategyId} variant="outline" className="rounded-full border-black/[0.08] bg-white/70 px-3 py-1">
                                {strategyId}
                              </Badge>
                            ))}
                          </div>
                        ) : null}
                      </div>

                      <div className="rounded-[22px] border border-black/[0.05] bg-white/60 p-4">
                        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/80">
                          <Clock3 className="h-4 w-4" />
                          最近一次执行
                        </div>
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <p>执行时间：{autoStatus?.daemon?.last_trading_run ? formatDateTime(autoStatus?.daemon?.last_trading_run) : "暂未执行"}</p>
                          <p>下单笔数：{latestPlacedOrders} 笔</p>
                          {typeof lastRunRecord.message === "string" ? <p>{lastRunRecord.message}</p> : null}
                        </div>
                      </div>
                    </GlassCard>
                  </div>

                  <GlassCard className="space-y-4 p-5">
                    <div className="space-y-1">
                      <CardTitle>自动交易策略池</CardTitle>
                      <CardDescription>把可用策略明确列出来，避免“系统到底启用了什么策略”不透明。</CardDescription>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {availableStrategies.map((strategy) => {
                        const checked = configDraft.strategy_ids.includes(strategy.id)
                        return (
                          <label
                            key={strategy.id}
                            className={cn(
                              "flex cursor-pointer items-start gap-3 rounded-[24px] border px-4 py-4 transition",
                              checked
                                ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.07)]"
                                : "border-black/[0.06] bg-white/60 hover:bg-white/80",
                            )}
                          >
                            <Checkbox
                              checked={checked}
                              onCheckedChange={(value) =>
                                setConfigDraft((current) => {
                                  const next = Boolean(value)
                                    ? Array.from(new Set([...current.strategy_ids, strategy.id]))
                                    : current.strategy_ids.filter((item) => item !== strategy.id)
                                  return {
                                    ...current,
                                    strategy_ids: next.length > 0 ? next : current.strategy_ids,
                                  }
                                })
                              }
                            />
                            <div className="min-w-0 space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <div className="text-sm font-medium text-foreground/85">{strategy.name}</div>
                                {strategy.category ? (
                                  <Badge variant="outline" className="rounded-full border-black/[0.08] bg-white/70 px-2 py-0.5 text-[0.76rem]">
                                    {strategy.category === "stz" ? "扫描" : "经典"}
                                  </Badge>
                                ) : null}
                              </div>
                              <p className="text-xs leading-6 text-muted-foreground">{strategy.description}</p>
                              {strategy.default_params && Object.keys(strategy.default_params).length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                  {Object.entries(strategy.default_params).slice(0, 3).map(([key, value]) => (
                                    <span key={key} className="rounded-full bg-black/[0.04] px-2.5 py-1 text-[11px] text-foreground/60">
                                      {key}: {String(value)}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          </label>
                        )
                      })}
                    </div>
                  </GlassCard>
                </>
              )}
            </TabsContent>

            <TabsContent value="manual" className="space-y-6">
              <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                <GlassCard className="space-y-4 p-5">
                  <div className="space-y-1">
                    <CardTitle>手动订单面板</CardTitle>
                    <CardDescription>在自动交易之外，也可以直接对当前模拟账户发起手动订单。</CardDescription>
                  </div>

                  <div className="space-y-2">
                    <Label>标的代码</Label>
                    <Input
                      value={manualTicker}
                      onChange={(event) => setManualTicker(event.target.value)}
                      placeholder="例如 510300 或 000333"
                    />
                    <div className="text-xs text-muted-foreground">
                      {quoteLoading
                        ? "正在读取最新参考价格..."
                        : effectivePrice > 0
                          ? `参考价格 ${formatCurrency(effectivePrice)}，当前持仓 ${selectedPosition?.shares || 0}`
                          : "输入代码后会自动读取最新可用价格。"}
                    </div>
                  </div>

                  {normalizedTicker && effectivePrice > 0 && account ? (
                    <OrderForm
                      ticker={normalizedTicker}
                      current_price={effectivePrice}
                      balance={account.portfolio.cash}
                      position={selectedPosition?.shares || 0}
                      onSubmit={(order) => void handleSubmitOrder(order)}
                    />
                  ) : (
                    <EmptyState text={account ? "请输入可交易代码后创建订单。" : "请先创建或恢复模拟账户。"} />
                  )}
                </GlassCard>

                <div className="space-y-6">
                  <GlassCard className="space-y-4 p-5">
                    <div className="space-y-1">
                      <CardTitle>订单上下文</CardTitle>
                      <CardDescription>展示当前账户的现金、持仓与最近订单，方便在下单前确认上下文。</CardDescription>
                    </div>

                    <div className="grid gap-3 md:grid-cols-3">
                      <SummaryMetric label="可用资金" value={formatCurrency(account?.portfolio.cash || 0)} />
                      <SummaryMetric label="持仓数量" value={`${positions.length} 个`} accent={SONG_COLORS.indigo} />
                      <SummaryMetric label="参考现价" value={effectivePrice > 0 ? formatCurrency(effectivePrice) : "--"} accent={SONG_COLORS.ink} />
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {positions.slice(0, 8).map((position) => (
                        <button
                          key={position.ticker}
                          type="button"
                          onClick={() => setManualTicker(position.ticker)}
                          className="rounded-full border border-black/[0.08] bg-white/70 px-3 py-1 text-xs text-foreground/75 transition hover:border-black/[0.14] hover:bg-white"
                        >
                          {position.ticker}
                        </button>
                      ))}
                    </div>
                  </GlassCard>

                  <GlassCard className="space-y-4 p-5">
                    <div className="space-y-1">
                      <CardTitle>最近订单</CardTitle>
                      <CardDescription>用于核对自动交易或手动交易最近发出的委托。</CardDescription>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[620px] text-sm">
                        <thead>
                          <tr className="border-b border-black/[0.06] text-left text-muted-foreground">
                            <th className="py-2">时间</th>
                            <th className="py-2">代码</th>
                            <th className="py-2">方向</th>
                            <th className="py-2">类型</th>
                            <th className="py-2 text-right">数量</th>
                            <th className="py-2 text-right">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recentOrders.length > 0 ? (
                            recentOrders.map((order) => (
                              <tr key={order.order_id} className="border-b border-black/[0.05] last:border-b-0">
                                <td className="py-3">{formatDateTime(order.created_at)}</td>
                                <td className="py-3 font-medium">{order.symbol}</td>
                                <td className={cn("py-3 font-medium", order.side.toUpperCase() === "BUY" ? "text-tone-positive" : "text-tone-negative")}>
                                  {order.side.toUpperCase() === "BUY" ? "买入" : "卖出"}
                                </td>
                                <td className="py-3">{ORDER_TYPE_TEXT[order.order_type.toUpperCase()] ?? order.order_type}</td>
                                <td className="py-3 text-right">{order.quantity}</td>
                                <td className="py-3 text-right">{order.status}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={6} className="py-8 text-center text-muted-foreground">
                                暂无最近订单记录。
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </GlassCard>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <GlassCard className="space-y-2 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground/80">
                <Bot className="h-4 w-4" />
                自动交易说明
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                系统会按你设定的频率评估策略，筛掉不达标策略，再把通过的信号自动下到模拟账户中。
              </p>
            </GlassCard>
            <GlassCard className="space-y-2 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground/80">
                <Workflow className="h-4 w-4" />
                标的池
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                标的池不是越大越好。先用核心 ETF、宽基或高流动性股票，保证价格质量与执行稳定性。
              </p>
            </GlassCard>
            <GlassCard className="space-y-2 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground/80">
                <ShieldCheck className="h-4 w-4" />
                风控阈值
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                收益、夏普与回撤阈值共同决定策略能否被采用。阈值越严，交易越少，但通常也更稳。
              </p>
            </GlassCard>
            <GlassCard className="space-y-2 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground/80">
                <ChartNoAxesColumn className="h-4 w-4" />
                回测衔接
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                想调整策略参数或比较不同战法，请先到回测页验证，再把通过验证的策略纳入自动交易。
              </p>
            </GlassCard>
          </div>
        </>
      )}
    </div>
  )
}
