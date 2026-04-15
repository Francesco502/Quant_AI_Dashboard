"use client"

import { useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  BrainCircuit,
  CheckCircle2,
  CircuitBoard,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react"

import { MetricCard } from "@/components/data/metric-card"
import { StatusPill } from "@/components/data/status-pill"
import { StatusNotice } from "@/components/data/status-notice"
import { CheckboxField, FormField } from "@/components/form/form-field"
import { MultiAssetPicker } from "@/components/shared/multi-asset-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  api,
  type AgentResearchResponse,
  type Asset,
  type LlmDecisionItem,
  type LlmDashboardSummary,
  type MarketReviewResponse,
} from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { formatCurrency } from "@/lib/utils"

type WorkspaceTab = "decision" | "agent"

type LlmConfigState = {
  configured: boolean
  available: boolean
  provider: string | null
  model: string | null
  base_url?: string
  error?: string
  message?: string
}

type HealthState = {
  status: string
  provider: string
  model?: string | null
  response_preview: string
} | null

const MODES: Array<{
  id: WorkspaceTab
  title: string
  description: string
  icon: typeof BrainCircuit
  accent: string
  glow: string
}> = [
  {
    id: "decision",
    title: "结构化决策",
    description: "统一输出评分、结论、买点和风险，适合多标的快速比较。",
    icon: Target,
    accent: SONG_COLORS.indigo,
    glow: "rgba(var(--rgb-indigo),0.14)",
  },
  {
    id: "agent",
    title: "Agent 研究",
    description: "适合开放式问题、多步推理和工具调用。",
    icon: BrainCircuit,
    accent: SONG_COLORS.ochre,
    glow: "rgba(var(--rgb-ochre),0.16)",
  },
]

function normalizeWorkspaceTab(value: string | null): WorkspaceTab {
  return value === "agent" ? "agent" : "decision"
}

function getActionMeta(action?: string) {
  switch ((action || "").toUpperCase()) {
    case "BUY":
    case "买入":
      return { label: "偏买入", className: "surface-tone-celadon" }
    case "SELL":
    case "卖出":
      return { label: "偏减仓", className: "surface-tone-cinnabar" }
    default:
      return { label: "偏观察", className: "surface-tone-ochre" }
  }
}

function formatDurationLabel(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safeSeconds / 60)
  const remainSeconds = safeSeconds % 60
  return minutes <= 0 ? `${safeSeconds} 秒` : `${minutes} 分 ${remainSeconds} 秒`
}

function getBusyHint(mode: "health" | "decision" | "agent", elapsed: number) {
  if (mode === "health") {
    return elapsed < 20 ? "正在测试接口连通性与鉴权。" : "若超过 45 秒无返回，请检查模型网关。"
  }
  if (mode === "decision") {
    return elapsed < 20 ? "正在收集标的和市场上下文。" : "正在请求模型生成结构化结论。"
  }
  return elapsed < 20 ? "正在规划研究步骤。" : "Agent 可能正在串行调用多个工具。"
}

function StatusMetric({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string
  tone?: "default" | "positive" | "negative" | "accent"
}) {
  return <MetricCard label={label} value={value} tone={tone} />
}

function ErrorNotice({ message }: { message: string }) {
  return <StatusNotice tone="error">{message}</StatusNotice>
}

type ToolSummaryEntry = {
  label: string
  value: string
}

function formatToolSummaryLabel(key: string) {
  return key.replaceAll("_", " ")
}

function formatToolSummaryValue(value: unknown) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4)
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否"
  }
  return String(value)
}

function buildToolSummaryEntries(data: unknown): ToolSummaryEntry[] {
  if (!data || typeof data !== "object" || Array.isArray(data)) return []

  const entries: ToolSummaryEntry[] = []
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    if (entries.length >= 6) break
    if (value == null) continue

    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      entries.push({
        label: formatToolSummaryLabel(key),
        value: formatToolSummaryValue(value),
      })
      continue
    }

    if (Array.isArray(value)) {
      entries.push({
        label: formatToolSummaryLabel(key),
        value: `${value.length} 项`,
      })
      continue
    }

    if (typeof value === "object") {
      entries.push({
        label: formatToolSummaryLabel(key),
        value: `${Object.keys(value as Record<string, unknown>).length} 个字段`,
      })
    }
  }

  return entries
}

function ModeCard({
  active,
  title,
  description,
  icon: Icon,
  accent,
  glow,
  onClick,
}: {
  active: boolean
  title: string
  description: string
  icon: typeof BrainCircuit
  accent: string
  glow: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="rounded-[28px] border p-4 text-left transition-[background-color,border-color,color,box-shadow,transform]"
      style={{
        borderColor: active ? accent : "rgba(var(--rgb-ink),0.08)",
        background: active
          ? `linear-gradient(180deg, ${glow} 0%, rgba(var(--rgb-xuan),0.9) 100%)`
          : "rgba(var(--rgb-xuan),0.62)",
        boxShadow: active ? `0 10px 28px -22px ${accent}` : "none",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div
            className="inline-flex h-10 w-10 items-center justify-center rounded-2xl"
            style={{ backgroundColor: active ? glow : "rgba(var(--rgb-ink),0.05)", color: accent }}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div className="section-title">{title}</div>
        </div>
        <div
          className="rounded-full px-2.5 py-1 text-[11px] font-medium"
          style={{
            color: active ? accent : SONG_COLORS.axis,
            backgroundColor: active ? "rgba(var(--rgb-xuan),0.76)" : "rgba(var(--rgb-ink),0.05)",
          }}
        >
          {active ? "当前模式" : "切换"}
        </div>
      </div>
      <p className="mt-4 text-sm leading-7 text-muted-foreground">{description}</p>
    </button>
  )
}

export default function LlmResearchWorkspace() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const tabFromUrl = normalizeWorkspaceTab(searchParams.get("tab"))

  const [activeTab, setActiveTab] = useState<WorkspaceTab>(tabFromUrl)
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [market, setMarket] = useState("cn")
  const [includeMarketReview, setIncludeMarketReview] = useState(true)

  const [config, setConfig] = useState<LlmConfigState | null>(null)
  const [systemError, setSystemError] = useState("")
  const [checking, setChecking] = useState(false)
  const [decisionLoading, setDecisionLoading] = useState(false)
  const [decisionError, setDecisionError] = useState("")
  const [health, setHealth] = useState<HealthState>(null)
  const [decisionData, setDecisionData] = useState<{
    results: LlmDecisionItem[]
    summary?: LlmDashboardSummary
    market_review?: MarketReviewResponse
  } | null>(null)

  const [agentQuery, setAgentQuery] = useState("比较 600519 和 000858 的价格趋势、市场环境与估值差异。")
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState("")
  const [agentResult, setAgentResult] = useState<AgentResearchResponse | null>(null)

  const [busyStartedAt, setBusyStartedAt] = useState<number | null>(null)
  const [busySeconds, setBusySeconds] = useState(0)

  const activeTickers = useMemo(
    () => (selectedTickers.length > 0 ? selectedTickers : assets.slice(0, 2).map((asset) => asset.ticker)),
    [assets, selectedTickers],
  )
  const selectedAssetNames = useMemo(
    () =>
      assets
        .filter((asset) => activeTickers.includes(asset.ticker))
        .map((asset) => asset.alias || asset.name || asset.ticker),
    [activeTickers, assets],
  )
  const busyMode = agentLoading ? "agent" : decisionLoading ? "decision" : checking ? "health" : null
  const isBusy = busyMode !== null

  useEffect(() => {
    setActiveTab(tabFromUrl)
  }, [tabFromUrl])

  const syncTabToUrl = (nextTab: WorkspaceTab) => {
    setActiveTab(nextTab)
    router.replace(nextTab === "agent" ? `${pathname}?tab=agent` : pathname, { scroll: false })
  }

  const loadBaseData = async () => {
    try {
      const [pool, llmConfig, personalAssets] = await Promise.all([
        api.stz.getAssetPool().catch(() => []),
        api.llmAnalysis.getConfig(),
        api.user.assets.getOverview(false).catch(() => ({ assets: [] })),
      ])

      const merged = new Map<string, Asset>()
      for (const asset of pool || []) {
        merged.set(asset.ticker, asset)
      }
      for (const asset of personalAssets.assets || []) {
        if (!merged.has(asset.ticker)) {
          merged.set(asset.ticker, {
            ticker: asset.ticker,
            name: asset.asset_name || asset.ticker,
          })
        }
      }

      setAssets(Array.from(merged.values()))
      setConfig(llmConfig)
      setSystemError("")
    } catch (error) {
      setSystemError(error instanceof Error ? error.message : "读取 LLM 状态失败")
    }
  }

  useEffect(() => {
    void loadBaseData()
  }, [])

  useEffect(() => {
    if (assets.length === 0 || selectedTickers.length > 0) return
    setSelectedTickers(assets.slice(0, 2).map((asset) => asset.ticker))
  }, [assets, selectedTickers.length])

  useEffect(() => {
    if (!busyMode) {
      setBusyStartedAt(null)
      setBusySeconds(0)
      return
    }

    const startedAt = busyStartedAt ?? Date.now()
    if (busyStartedAt == null) {
      setBusyStartedAt(startedAt)
    }

    const updateElapsed = () => {
      setBusySeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    }

    updateElapsed()
    const timer = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(timer)
  }, [busyMode, busyStartedAt])

  const handleHealthCheck = async () => {
    setChecking(true)
    setBusyStartedAt(Date.now())
    setBusySeconds(0)
    setDecisionError("")
    setHealth(null)
    try {
      setHealth(await api.llmAnalysis.healthCheck())
    } catch (error) {
      setDecisionError(error instanceof Error ? error.message : "接口连通性测试失败")
    } finally {
      setChecking(false)
    }
  }

  const handleDecisionRun = async () => {
    setDecisionLoading(true)
    setBusyStartedAt(Date.now())
    setBusySeconds(0)
    setDecisionError("")
    setDecisionData(null)
    try {
      setDecisionData(
        await api.llmAnalysis.dashboard({
          tickers: activeTickers.length > 0 ? activeTickers : ["013281", "002611"],
          market,
          include_market_review: includeMarketReview,
        }),
      )
    } catch (error) {
      setDecisionError(error instanceof Error ? error.message : "决策分析失败")
    } finally {
      setDecisionLoading(false)
    }
  }

  const handleAgentRun = async () => {
    if (!config?.configured) return
    setAgentLoading(true)
    setBusyStartedAt(Date.now())
    setBusySeconds(0)
    setAgentError("")
    setAgentResult(null)
    try {
      setAgentResult(await api.agent.research({ query: agentQuery }))
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Agent 研究失败")
    } finally {
      setAgentLoading(false)
    }
  }

  const effectiveModelLabel = config?.model || "检测中"
  const serviceStatusLabel = config?.available ? "可用" : config?.configured ? "已配置但不可用" : "未配置"
  const serviceStatusPillTone = config?.available ? "celadon" : config?.configured ? "ochre" : "ink"

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-2">
            <h1 className="page-title">决策与 Agent 研究</h1>
            <p className="page-subtitle">
              把结构化决策与开放式研究收在同一处，先判断结论是否可执行，再继续展开深挖，不再在两套页面之间来回切换。
            </p>
          </div>

          <div className="data-panel-muted min-w-[280px] rounded-[24px] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="text-[0.9rem] font-medium text-foreground/84">当前模型状态</div>
                <p className="text-[0.84rem] leading-6 text-foreground/64">模型与服务状态集中放在右侧，不再与模式选择抢首屏注意力。</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => void loadBaseData()} disabled={isBusy}>
                <RefreshCw className="mr-2 h-4 w-4" />
                刷新
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <StatusPill label="调用模型" value={effectiveModelLabel} icon={CircuitBoard} tone="indigo" />
              <StatusPill label="服务状态" value={serviceStatusLabel} icon={CheckCircle2} tone={serviceStatusPillTone} />
            </div>

            {config?.error ? (
              <StatusNotice className="mt-4" tone="error">
                {config.error}
              </StatusNotice>
            ) : null}
          </div>
        </div>
      </section>

      <Tabs value={activeTab} className="space-y-6">
        <GlassCard className="p-3">
          <div className="grid gap-3 md:grid-cols-2">
            {MODES.map((mode) => (
              <ModeCard
                key={mode.id}
                active={activeTab === mode.id}
                title={mode.title}
                description={mode.description}
                icon={mode.icon}
                accent={mode.accent}
                glow={mode.glow}
                onClick={() => syncTabToUrl(mode.id)}
              />
            ))}
          </div>
        </GlassCard>

        {systemError ? <ErrorNotice message={systemError} /> : null}

        <TabsContent value="decision" className="space-y-6">
          <GlassCard className="space-y-5 p-6">
            <div className="space-y-1">
              <CardTitle>结构化决策</CardTitle>
              <CardDescription>选择标的后生成统一格式的结论、评分、风险和附带市场复盘。</CardDescription>
            </div>

            <div className="grid gap-4 md:grid-cols-[1.1fr_0.45fr_0.45fr]">
              <FormField
                label="评估标的"
                description={`当前将分析：${selectedAssetNames.length ? selectedAssetNames.join("、") : "暂无可用资产"}`}
              >
                <MultiAssetPicker
                  assets={assets}
                  selected={selectedTickers}
                  onChange={setSelectedTickers}
                  placeholder="选择评估标的"
                />
              </FormField>

              <FormField label="市场">
                <Select value={market} onValueChange={setMarket}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cn">A 股 / 基金</SelectItem>
                    <SelectItem value="hk">港股</SelectItem>
                    <SelectItem value="us">美股</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>

              <FormField label="附加项">
                <CheckboxField
                  id="include-market-review"
                  checked={includeMarketReview}
                  onCheckedChange={setIncludeMarketReview}
                  label="附带市场复盘"
                  description="评估时会把同日市场背景、指数表现和资金情绪一并纳入判断。"
                />
              </FormField>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button variant="outline" onClick={() => void handleHealthCheck()} disabled={isBusy}>
                {checking ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                测试当前配置
              </Button>
              <Button onClick={() => void handleDecisionRun()} disabled={isBusy}>
                {decisionLoading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <BrainCircuit className="mr-2 h-4 w-4" />}
                开始评估
              </Button>
            </div>
          </GlassCard>

          {busyMode === "health" || busyMode === "decision" ? (
            <GlassCard className="space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle>{busyMode === "health" ? "正在测试配置" : "正在执行评估"}</CardTitle>
                  <CardDescription>{getBusyHint(busyMode, busySeconds)}</CardDescription>
                </div>
                <Badge variant="outline" className="surface-tone-ochre rounded-full px-3 py-1 text-xs">
                  已耗时 {formatDurationLabel(busySeconds)}
                </Badge>
              </div>
            </GlassCard>
          ) : null}

          {health ? (
            <GlassCard className="p-5">
              <div className="flex flex-wrap items-center gap-3">
                <div className="surface-tone-celadon inline-flex h-10 w-10 items-center justify-center rounded-2xl">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <div className="text-sm font-medium text-foreground/85">接口连通性已确认</div>
                  <p className="text-[13px] text-muted-foreground">模型：{health.model || effectiveModelLabel}</p>
                </div>
              </div>
              <p className="data-panel-muted mt-4 rounded-2xl px-4 py-3 text-sm leading-7 text-foreground/82">
                响应预览：{health.response_preview}
              </p>
            </GlassCard>
          ) : null}

          {decisionError ? <ErrorNotice message={decisionError} /> : null}

          {decisionData?.summary ? (
            <div className="grid gap-4 md:grid-cols-5">
              <StatusMetric label="分析标的" value={String(decisionData.summary.total)} />
              <StatusMetric label="偏买入" value={String(decisionData.summary.buy)} tone="positive" />
              <StatusMetric label="偏观察" value={String(decisionData.summary.watch)} tone="accent" />
              <StatusMetric label="偏减仓" value={String(decisionData.summary.sell)} tone="negative" />
              <StatusMetric label="平均评分" value={decisionData.summary.avg_score?.toFixed(1) ?? "--"} />
            </div>
          ) : null}

          {decisionData?.results?.length ? (
            <div className="grid gap-5 xl:grid-cols-2">
              {decisionData.results.map((item) => {
                const actionMeta = getActionMeta(item.decision?.action)
                return (
                  <GlassCard key={item.ticker} className="space-y-5 p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1">
                        <CardTitle>{item.name || item.ticker}</CardTitle>
                        <p className="text-[13px] text-muted-foreground">{item.ticker}</p>
                      </div>
                      <span
                        className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${actionMeta.className}`}
                      >
                        {actionMeta.label}
                      </span>
                    </div>

                    <p className="data-panel-muted rounded-[24px] px-4 py-4 text-sm leading-7 text-foreground/82">
                      {item.decision?.conclusion || "暂无结论。"}
                    </p>

                    <div className="grid gap-3 sm:grid-cols-4">
                      <StatusMetric label="评分" value={String(item.decision?.score ?? "--")} tone="accent" />
                      <StatusMetric
                        label="最新价格"
                        value={item.decision?.latest_price != null ? formatCurrency(item.decision.latest_price) : "--"}
                      />
                      <StatusMetric
                        label="参考买点"
                        value={item.decision?.buy_price != null ? formatCurrency(item.decision.buy_price) : "--"}
                        tone="positive"
                      />
                      <StatusMetric
                        label="目标价"
                        value={item.decision?.target_price != null ? formatCurrency(item.decision.target_price) : "--"}
                        tone="negative"
                      />
                    </div>

                    {item.decision?.highlights?.length ? (
                      <div className="space-y-2">
                        <div className="text-sm font-medium text-foreground/85">核心亮点</div>
                        <ul className="space-y-2 text-sm leading-7 text-muted-foreground">
                          {item.decision.highlights.map((highlight) => (
                            <li key={highlight} className="data-panel-muted rounded-2xl px-4 py-2">
                              {highlight}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {item.decision?.risks?.length ? (
                      <div className="space-y-2">
                        <div className="text-sm font-medium text-foreground/85">主要风险</div>
                        <ul className="space-y-2 text-sm leading-7 text-muted-foreground">
                          {item.decision.risks.map((risk) => (
                            <li key={risk} className="surface-tone-cinnabar rounded-2xl px-4 py-2">
                              {risk}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </GlassCard>
                )
              })}
            </div>
          ) : null}

          {decisionData?.market_review ? (
            <GlassCard className="space-y-4 p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-4 w-4" style={{ color: SONG_COLORS.indigo }} />
                    附带市场复盘
                  </CardTitle>
                  <CardDescription>把同一市场的背景情绪一起带入判断。</CardDescription>
                </div>
                <Badge variant="outline" className="surface-tone-indigo rounded-full px-3 py-1 text-xs">
                  {decisionData.market_review.date}
                </Badge>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {decisionData.market_review.indices?.map((index) => (
                  <div key={index.name} className="data-panel-muted rounded-[22px] p-4">
                    <div className="text-[13px] text-muted-foreground">{index.name}</div>
                    <div className="mt-2 text-xl font-semibold tracking-[-0.03em] text-foreground/90">
                      {index.value.toFixed(2)}
                    </div>
                    <div
                      className="mt-2 text-sm font-medium"
                      style={{ color: index.pct_change >= 0 ? SONG_COLORS.positive : SONG_COLORS.negative }}
                    >
                      {index.pct_change >= 0 ? "+" : ""}
                      {index.pct_change.toFixed(2)}%
                    </div>
                  </div>
                ))}
              </div>

              {decisionData.market_review.northbound?.description ? (
                <div className="data-panel-muted rounded-[22px] px-4 py-4 text-sm leading-7 text-muted-foreground">
                  {decisionData.market_review.northbound.description}
                </div>
              ) : null}
            </GlassCard>
          ) : null}

          {!decisionData && !decisionLoading ? (
            <GlassCard className="p-6">
              <div className="flex items-start gap-4">
                <div className="surface-tone-indigo inline-flex h-11 w-11 items-center justify-center rounded-2xl">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="space-y-2">
                  <CardTitle>等待评估</CardTitle>
                  <p className="text-sm leading-7 text-muted-foreground">选择标的后点击“开始评估”。</p>
                </div>
              </div>
            </GlassCard>
          ) : null}
        </TabsContent>

        <TabsContent value="agent" className="space-y-6">
          <GlassCard className="space-y-5 p-6">
            <div className="space-y-1">
              <CardTitle>Agent 研究</CardTitle>
              <CardDescription>输入开放式问题，让 Agent 做多步整理、工具调用和自由回答。</CardDescription>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={config?.configured ? "default" : "secondary"}>
                {config?.configured ? "已配置" : "未配置"}
              </Badge>
              <span className="text-sm text-muted-foreground">当前模型：{effectiveModelLabel}</span>
            </div>

            {!config?.configured ? <StatusNotice tone="warning">当前未配置可用模型。</StatusNotice> : null}

            <FormField label="研究问题" description="适合开放式问题、多标的比较和需要调用工具的研究任务。">
              <Textarea
                value={agentQuery}
                onChange={(event) => setAgentQuery(event.target.value)}
                className="min-h-40"
                placeholder="输入你的研究问题"
              />
            </FormField>

            <Button onClick={() => void handleAgentRun()} disabled={isBusy || !config?.configured}>
              {agentLoading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <BrainCircuit className="mr-2 h-4 w-4" />}
              开始研究
            </Button>
          </GlassCard>

          {busyMode === "agent" ? (
            <GlassCard className="space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle>正在进行 Agent 研究</CardTitle>
                  <CardDescription>{getBusyHint("agent", busySeconds)}</CardDescription>
                </div>
                <Badge variant="outline" className="surface-tone-ochre rounded-full px-3 py-1 text-xs">
                  已耗时 {formatDurationLabel(busySeconds)}
                </Badge>
              </div>
            </GlassCard>
          ) : null}

          {agentError ? <ErrorNotice message={agentError} /> : null}

          {agentResult ? (
            <GlassCard className="space-y-4 p-5">
              <div className="grid gap-3 md:grid-cols-3">
                <StatusMetric label="迭代次数" value={String(agentResult.iterations)} />
                <StatusMetric label="工具调用" value={String(agentResult.tools_used.length)} tone="accent" />
                <StatusMetric label="当前模型" value={effectiveModelLabel} />
              </div>

              <div className="data-panel-muted rounded-[24px] p-4 text-sm leading-7 whitespace-pre-wrap text-foreground/85">
                {agentResult.answer}
              </div>

              {agentResult.tool_results.length ? (
                <div className="space-y-3">
                  <CardTitle>工具结果</CardTitle>
                  {agentResult.tool_results.map((tool, index) => (
                    <ToolResultCard key={`${tool.name}-${index}`} name={tool.name} data={tool.data} />
                  ))}
                </div>
              ) : null}
            </GlassCard>
          ) : (
            <GlassCard className="p-6">
              <div className="flex items-start gap-4">
                <div className="surface-tone-ochre inline-flex h-11 w-11 items-center justify-center rounded-2xl">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="space-y-2">
                  <CardTitle>等待研究</CardTitle>
                  <p className="text-sm leading-7 text-muted-foreground">输入研究问题后点击“开始研究”。</p>
                </div>
              </div>
            </GlassCard>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ToolResultCard({ name, data }: { name: string; data: unknown }) {
  const summaryEntries = buildToolSummaryEntries(data)
  const toolError =
    data && typeof data === "object" && !Array.isArray(data)
      ? (data as Record<string, unknown>).error
      : null
  const rawPayload = JSON.stringify(data, null, 2)

  return (
    <div className="data-panel-muted space-y-4 rounded-[24px] p-4">
      <div className="space-y-1">
        <div className="text-sm font-medium text-foreground/85">{name}</div>
        <div className="text-xs leading-6 text-muted-foreground">
          {summaryEntries.length > 0 ? "已整理工具返回要点" : "查看本次工具返回详情"}
        </div>
      </div>

      {toolError ? <StatusNotice tone="error">{String(toolError)}</StatusNotice> : null}

      {summaryEntries.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {summaryEntries.map((entry) => (
            <div
              key={`${name}-${entry.label}`}
              className="data-panel rounded-[20px] px-4 py-3"
            >
              <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{entry.label}</div>
              <div className="mt-2 text-sm font-medium leading-6 text-foreground/86">{entry.value}</div>
            </div>
          ))}
        </div>
      ) : null}

      <details className="data-panel rounded-[20px] px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium text-foreground/80">查看原始返回</summary>
        <pre className="mt-3 overflow-x-auto text-xs leading-6 text-muted-foreground">{rawPayload}</pre>
      </details>
    </div>
  )
}
