"use client"

import { useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  BrainCircuit,
  CheckCircle2,
  Link2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  WandSparkles,
} from "lucide-react"

import { MultiAssetPicker } from "@/components/shared/multi-asset-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  api,
  type Asset,
  type LlmDecisionItem,
  type LlmDashboardSummary,
  type LlmInterfaceType,
  type MarketReviewResponse,
} from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { cn, formatCurrency } from "@/lib/utils"

type LlmConfigState = {
  configured: boolean
  available: boolean
  provider: string | null
  model: string | null
  base_url?: string
  error?: string
  message?: string
  selection_mode?: string
}

type HealthState = {
  status: string
  provider: string
  model?: string | null
  base_url?: string | null
  response_preview: string
} | null

type RuntimePreset = {
  id: "volcengine" | "custom"
  label: string
  providerType: LlmInterfaceType
  baseUrl: string
  model: string
  description: string
}

const DEFAULT_PRESET = {
  providerType: "openai_compat" as const,
  baseUrl: "https://ark.cn-beijing.volces.com/api/coding/v3",
  model: "doubao-seed-1-6-thinking",
}

const RUNTIME_PRESETS: RuntimePreset[] = [
  {
    id: "volcengine",
    label: "火山 Coding Plan",
    providerType: "openai_compat",
    baseUrl: DEFAULT_PRESET.baseUrl,
    model: DEFAULT_PRESET.model,
    description: "默认推荐。适合火山方舟 OpenAI 兼容接口，也是当前项目建议的系统默认链路。",
  },
  {
    id: "custom",
    label: "自定义接口",
    providerType: "openai_compat",
    baseUrl: "",
    model: "",
    description: "仅在需要临时试验 URL 与 model 时使用，不改变系统默认配置。",
  },
]

const INFO_LINES = [
  "系统默认配置应写在 .env 中，页面里的 URL 与模型只用于本次调用的临时覆盖。",
  "推荐把 LLM_PROVIDER 明确设为 openai_compat，再通过 OPENAI_BASE_URL 与 OPENAI_MODEL 固定火山默认接口。",
  "评估标的默认取资产池与个人资产的前 2 个，可在下拉中多选扩展。",
]

function getActionMeta(action?: string) {
  switch ((action || "").toUpperCase()) {
    case "BUY":
    case "买入":
      return { label: "偏买入", color: SONG_COLORS.positive, bg: "rgba(77, 115, 88, 0.10)" }
    case "SELL":
    case "卖出":
      return { label: "偏减仓", color: SONG_COLORS.negative, bg: "rgba(182, 69, 60, 0.10)" }
    default:
      return { label: "偏观察", color: SONG_COLORS.ochre, bg: "rgba(176, 142, 97, 0.12)" }
  }
}

function inferPresetId(provider: string | null | undefined, baseUrl?: string | null): RuntimePreset["id"] {
  const normalizedProvider = (provider || "").trim().toLowerCase()
  const normalizedBaseUrl = (baseUrl || "").trim().toLowerCase()

  if (normalizedProvider !== "openai_compat") {
    return "custom"
  }
  if (normalizedBaseUrl.includes("volces.com")) {
    return "volcengine"
  }
  return "custom"
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
  const color =
    tone === "positive"
      ? SONG_COLORS.positive
      : tone === "negative"
        ? SONG_COLORS.negative
        : tone === "accent"
          ? SONG_COLORS.indigo
          : SONG_COLORS.ink

  return (
    <div className="rounded-[22px] border border-black/[0.05] bg-white/55 p-4">
      <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold tracking-[-0.03em]" style={{ color }}>
        {value}
      </div>
    </div>
  )
}

export default function DashboardLLMPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedTickers, setSelectedTickers] = useState<string[]>([])
  const [market, setMarket] = useState("cn")
  const [includeMarketReview, setIncludeMarketReview] = useState(true)
  const [useSystemConfig, setUseSystemConfig] = useState(true)
  const [presetId, setPresetId] = useState<RuntimePreset["id"]>("volcengine")
  const [providerType, setProviderType] = useState<LlmInterfaceType>(DEFAULT_PRESET.providerType)
  const [baseUrl, setBaseUrl] = useState(DEFAULT_PRESET.baseUrl)
  const [model, setModel] = useState(DEFAULT_PRESET.model)
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState("")
  const [config, setConfig] = useState<LlmConfigState | null>(null)
  const [health, setHealth] = useState<HealthState>(null)
  const [data, setData] = useState<{
    results: LlmDecisionItem[]
    summary?: LlmDashboardSummary
    market_review?: MarketReviewResponse
    market_review_error?: string
  } | null>(null)

  const selectedPreset = useMemo(
    () => RUNTIME_PRESETS.find((item) => item.id === presetId) ?? RUNTIME_PRESETS[0],
    [presetId],
  )

  const activeTickers = useMemo(() => {
    if (selectedTickers.length > 0) return selectedTickers
    return assets.slice(0, 2).map((asset) => asset.ticker)
  }, [assets, selectedTickers])

  const selectedAssetNames = useMemo(
    () =>
      assets
        .filter((asset) => activeTickers.includes(asset.ticker))
        .map((asset) => asset.alias || asset.name || asset.ticker),
    [activeTickers, assets],
  )

  const loadBaseData = async () => {
    try {
      const [pool, llmConfig, personalAssets] = await Promise.all([
        api.stz.getAssetPool().catch(() => []),
        api.llmAnalysis.getConfig(),
        api.user.assets.getOverview(false).catch(() => ({ assets: [] })),
      ])

      const mergedAssets = new Map<string, Asset>()
      for (const asset of pool || []) {
        mergedAssets.set(asset.ticker, asset)
      }
      for (const asset of personalAssets.assets || []) {
        if (!mergedAssets.has(asset.ticker)) {
          mergedAssets.set(asset.ticker, {
            ticker: asset.ticker,
            name: asset.asset_name || asset.ticker,
          })
        }
      }

      setAssets(Array.from(mergedAssets.values()))
      setConfig(llmConfig)
      setError("")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "读取 LLM 状态失败")
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
    if (!config || !useSystemConfig) return

    if (config.provider === "openai_compat" || config.provider === "anthropic") {
      setProviderType(config.provider)
      setBaseUrl(config.base_url || (config.provider === "openai_compat" ? DEFAULT_PRESET.baseUrl : ""))
      setModel(config.model || (config.provider === "openai_compat" ? DEFAULT_PRESET.model : ""))
      setPresetId(inferPresetId(config.provider, config.base_url))
      return
    }

    setProviderType(DEFAULT_PRESET.providerType)
    setBaseUrl(DEFAULT_PRESET.baseUrl)
    setModel(DEFAULT_PRESET.model)
    setPresetId("volcengine")
  }, [config, useSystemConfig])

  const applyPreset = (preset: RuntimePreset) => {
    setPresetId(preset.id)
    setProviderType(preset.providerType)
    setBaseUrl(preset.baseUrl)
    setModel(preset.model)
  }

  const runtimeOptions = useMemo(() => {
    if (useSystemConfig) {
      return {}
    }
    return {
      provider_type: providerType,
      base_url: baseUrl.trim() || undefined,
      model: model.trim() || undefined,
    }
  }, [baseUrl, model, providerType, useSystemConfig])

  const handleHealthCheck = async () => {
    setChecking(true)
    setError("")
    setHealth(null)
    try {
      const response = await api.llmAnalysis.healthCheck(runtimeOptions)
      setHealth(response)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "接口连通性测试失败")
    } finally {
      setChecking(false)
    }
  }

  const handleRun = async () => {
    setLoading(true)
    setError("")
    setData(null)
    try {
      const response = await api.llmAnalysis.dashboard({
        tickers: activeTickers.length > 0 ? activeTickers : ["013281", "002611"],
        market,
        include_market_review: includeMarketReview,
        ...runtimeOptions,
      })
      setData(response)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "决策分析失败")
    } finally {
      setLoading(false)
    }
  }

  const effectiveProviderLabel = useMemo(() => {
    if (useSystemConfig) {
      return config?.provider || "--"
    }
    return providerType === "anthropic" ? "anthropic" : "openai_compat"
  }, [config?.provider, providerType, useSystemConfig])

  const effectiveModelLabel = useMemo(() => {
    if (useSystemConfig) {
      return config?.model || "--"
    }
    return model.trim() || "--"
  }, [config?.model, model, useSystemConfig])

  const effectiveBaseUrlLabel = useMemo(() => {
    if (useSystemConfig) {
      return config?.base_url || "--"
    }
    return baseUrl.trim() || "--"
  }, [baseUrl, config?.base_url, useSystemConfig])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="space-y-3">
        <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/60 px-3 py-1 text-xs">
          决策仪表盘
        </Badge>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-[-0.04em] text-foreground/90">
            先固化系统默认，再按需临时覆盖的 LLM 研判台
          </h1>
          <p className="max-w-4xl text-sm leading-7 text-muted-foreground">
            这页现在默认跟随后端 .env 中的系统配置。只有你主动关闭“跟随系统默认”时，页面里的
            URL、模型与接口类型才会作为本次调用的临时覆盖，不再反向影响系统默认。
          </p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <GlassCard className="space-y-5 p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <WandSparkles className="h-4 w-4" style={{ color: SONG_COLORS.indigo }} />
                调用方式
              </CardTitle>
              <CardDescription>
                推荐把默认接口固定在 .env 中。页面里的覆盖只用于临时试验模型或网关，不再承担系统配置职责。
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => void loadBaseData()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新资产与配置
            </Button>
          </div>

          <div className="rounded-[24px] border border-black/[0.05] bg-white/55 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="text-sm font-medium text-foreground/85">跟随系统默认配置</div>
                <p className="text-[13px] leading-6 text-muted-foreground">
                  开启时，当前页面将直接使用后端 .env 的默认 provider / base URL / model。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/65 px-2.5 py-1 text-[11px]">
                  {config?.selection_mode === "explicit" ? "显式默认" : "自动识别"}
                </Badge>
                <Checkbox checked={useSystemConfig} onCheckedChange={(value) => setUseSystemConfig(Boolean(value))} />
              </div>
            </div>
          </div>

          {useSystemConfig ? (
            <div className="rounded-[24px] border border-black/[0.05] bg-white/50 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/65 px-2.5 py-1 text-[11px]">
                  当前直接使用系统默认
                </Badge>
                {config?.base_url ? (
                  <span className="text-[12px] text-muted-foreground">默认网关：{config.base_url}</span>
                ) : null}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <StatusMetric label="默认接口" value={config?.provider || "--"} tone="accent" />
                <StatusMetric label="默认模型" value={config?.model || "--"} />
                <StatusMetric
                  label="服务状态"
                  value={config?.available ? "可用" : config?.configured ? "待修复" : "未配置"}
                  tone={config?.available ? "positive" : config?.configured ? "negative" : "default"}
                />
              </div>
            </div>
          ) : (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                {RUNTIME_PRESETS.map((preset) => {
                  const isActive = preset.id === presetId
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => applyPreset(preset)}
                      className={cn(
                        "rounded-[24px] border px-4 py-4 text-left transition-all",
                        isActive
                          ? "border-black/[0.12] bg-white/80 shadow-[0_18px_40px_rgba(0,0,0,0.04)]"
                          : "border-black/[0.05] bg-white/50 hover:border-black/[0.1] hover:bg-white/70",
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-foreground/85">{preset.label}</span>
                        {isActive ? (
                          <span
                            className="inline-flex h-6 items-center rounded-full px-2 text-[11px] font-medium"
                            style={{ color: SONG_COLORS.positive, backgroundColor: "rgba(77, 115, 88, 0.10)" }}
                          >
                            当前
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 text-[12px] leading-6 text-muted-foreground">{preset.description}</p>
                    </button>
                  )
                })}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>接口类型</Label>
                  <Select
                    value={providerType}
                    onValueChange={(value) => {
                      setPresetId("custom")
                      setProviderType(value as LlmInterfaceType)
                    }}
                  >
                    <SelectTrigger className="rounded-2xl border-black/[0.07] bg-white/55">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai_compat">OpenAI 兼容</SelectItem>
                      <SelectItem value="anthropic">Anthropic 兼容</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>调用模型</Label>
                  <Input
                    value={model}
                    onChange={(event) => {
                      setPresetId("custom")
                      setModel(event.target.value)
                    }}
                    placeholder="例如 doubao-seed-1-6-thinking / claude-3-7-sonnet"
                    className="rounded-2xl border-black/[0.07] bg-white/55"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>基础 URL</Label>
                <div className="relative">
                  <Link2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/35" />
                  <Input
                    value={baseUrl}
                    onChange={(event) => {
                      setPresetId("custom")
                      setBaseUrl(event.target.value)
                    }}
                    placeholder="https://example.com/v1"
                    className="rounded-2xl border-black/[0.07] bg-white/55 pl-9"
                  />
                </div>
              </div>
            </>
          )}

          <div className="grid gap-4 md:grid-cols-[1.1fr_0.45fr_0.45fr]">
            <div className="space-y-2">
              <Label>评估标的</Label>
              <MultiAssetPicker
                assets={assets}
                selected={selectedTickers}
                onChange={setSelectedTickers}
                placeholder="默认使用前 2 个资产"
              />
              <p className="text-[12px] leading-6 text-muted-foreground">
                当前将分析：{selectedAssetNames.length ? selectedAssetNames.join("、") : "暂无可用资产"}
              </p>
            </div>
            <div className="space-y-2">
              <Label>市场</Label>
              <Select value={market} onValueChange={setMarket}>
                <SelectTrigger className="rounded-2xl border-black/[0.07] bg-white/55">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cn">A 股 / 基金</SelectItem>
                  <SelectItem value="hk">港股</SelectItem>
                  <SelectItem value="us">美股</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>附加项</Label>
              <div className="flex h-10 items-center rounded-2xl border border-black/[0.07] bg-white/55 px-3">
                <Checkbox
                  id="include-market-review"
                  checked={includeMarketReview}
                  onCheckedChange={(value) => setIncludeMarketReview(Boolean(value))}
                />
                <Label htmlFor="include-market-review" className="ml-3 text-sm font-normal text-foreground/75">
                  附带市场复盘
                </Label>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => void handleHealthCheck()} disabled={checking}>
              {checking ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
              {useSystemConfig ? "测试系统默认配置" : "测试临时覆盖配置"}
            </Button>
            <Button onClick={() => void handleRun()} disabled={loading}>
              {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <BrainCircuit className="mr-2 h-4 w-4" />}
              开始评估
            </Button>
          </div>
        </GlassCard>

        <GlassCard className="space-y-5 p-6">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" style={{ color: SONG_COLORS.positive }} />
              当前调用摘要
            </CardTitle>
            <CardDescription>
              这里把系统默认与本次调用方式分开显示，避免“页面改了参数，到底有没有改后端默认”这类混淆。
            </CardDescription>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <StatusMetric label="生效接口" value={effectiveProviderLabel} tone="accent" />
            <StatusMetric label="生效模型" value={effectiveModelLabel} />
            <StatusMetric label="调用方式" value={useSystemConfig ? "系统默认" : "临时覆盖"} tone={useSystemConfig ? "positive" : "accent"} />
          </div>

          <div className="rounded-[24px] border border-black/[0.05] bg-white/55 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/65 px-2.5 py-1 text-[11px]">
                {useSystemConfig ? "跟随 .env 默认" : selectedPreset.label}
              </Badge>
              <span className="text-[12px] text-muted-foreground">当前网关：{effectiveBaseUrlLabel}</span>
            </div>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              {config?.message ||
                "页面默认只跟随系统配置；只有关闭“跟随系统默认”后，URL 与模型才会作为临时覆盖参与调用。"}
            </p>
            {config?.error ? (
              <p
                className="mt-3 rounded-2xl px-3 py-2 text-sm"
                style={{ color: SONG_COLORS.negative, backgroundColor: "rgba(182, 69, 60, 0.08)" }}
              >
                {config.error}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            {INFO_LINES.map((line) => (
              <div
                key={line}
                className="rounded-2xl border border-black/[0.05] bg-white/45 px-4 py-3 text-[13px] leading-6 text-muted-foreground"
              >
                {line}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {health ? (
        <GlassCard className="p-5">
          <div className="flex flex-wrap items-center gap-3">
            <div
              className="inline-flex h-10 w-10 items-center justify-center rounded-2xl"
              style={{ backgroundColor: "rgba(77, 115, 88, 0.10)", color: SONG_COLORS.positive }}
            >
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <div className="text-sm font-medium text-foreground/85">接口连通性已确认</div>
              <p className="text-[13px] text-muted-foreground">
                {health.provider} / {health.model || effectiveModelLabel} / {health.base_url || effectiveBaseUrlLabel}
              </p>
            </div>
          </div>
          <p className="mt-4 rounded-2xl border border-black/[0.05] bg-white/55 px-4 py-3 text-sm leading-7 text-foreground/80">
            返回预览：{health.response_preview}
          </p>
        </GlassCard>
      ) : null}

      {error ? (
        <div
          className="rounded-[26px] border px-4 py-4 text-sm leading-7"
          style={{
            borderColor: "rgba(182, 69, 60, 0.18)",
            color: SONG_COLORS.negative,
            backgroundColor: "rgba(182, 69, 60, 0.08)",
          }}
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      ) : null}

      {data?.summary ? (
        <div className="grid gap-4 md:grid-cols-5">
          <StatusMetric label="分析标的" value={String(data.summary.total)} />
          <StatusMetric label="偏买入" value={String(data.summary.buy)} tone="positive" />
          <StatusMetric label="偏观察" value={String(data.summary.watch)} tone="accent" />
          <StatusMetric label="偏减仓" value={String(data.summary.sell)} tone="negative" />
          <StatusMetric label="平均评分" value={data.summary.avg_score?.toFixed(1) ?? "--"} />
        </div>
      ) : null}

      {data?.results?.length ? (
        <div className="grid gap-5 xl:grid-cols-2">
          {data.results.map((item) => {
            const actionMeta = getActionMeta(item.decision?.action)
            return (
              <GlassCard key={item.ticker} className="space-y-5 p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <CardTitle>{item.name || item.ticker}</CardTitle>
                    <p className="text-[13px] text-muted-foreground">{item.ticker}</p>
                  </div>
                  <span
                    className="inline-flex rounded-full px-3 py-1 text-xs font-medium"
                    style={{ color: actionMeta.color, backgroundColor: actionMeta.bg }}
                  >
                    {actionMeta.label}
                  </span>
                </div>

                <p className="rounded-[24px] border border-black/[0.05] bg-white/55 px-4 py-4 text-sm leading-7 text-foreground/80">
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
                        <li key={highlight} className="rounded-2xl border border-black/[0.05] bg-white/45 px-4 py-2">
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
                        <li
                          key={risk}
                          className="rounded-2xl border px-4 py-2"
                          style={{
                            borderColor: "rgba(182, 69, 60, 0.14)",
                            backgroundColor: "rgba(182, 69, 60, 0.05)",
                          }}
                        >
                          {risk}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {item.decision?.checklist?.length ? (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-foreground/85">检查清单</div>
                    <div className="space-y-2">
                      {item.decision.checklist.map((row, index) => (
                        <div
                          key={`${row.condition || row.item || "check"}-${index}`}
                          className="grid gap-2 rounded-2xl border border-black/[0.05] bg-white/45 px-4 py-3 sm:grid-cols-[1fr_auto_auto]"
                        >
                          <div className="text-sm text-foreground/78">{row.condition || row.item || "检查项"}</div>
                          <div className="text-sm text-muted-foreground">{row.value || "--"}</div>
                          <div
                            className="text-sm font-medium"
                            style={{ color: row.status === "PASS" ? SONG_COLORS.positive : SONG_COLORS.ochre }}
                          >
                            {row.status}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </GlassCard>
            )
          })}
        </div>
      ) : null}

      {data?.market_review ? (
        <GlassCard className="space-y-4 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <Target className="h-4 w-4" style={{ color: SONG_COLORS.indigo }} />
                附带市场复盘
              </CardTitle>
              <CardDescription>把同一市场的背景情绪一起带入判断，避免只看单个资产。</CardDescription>
            </div>
            <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/65 px-3 py-1 text-xs">
              {data.market_review.date}
            </Badge>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {data.market_review.indices?.map((index) => (
              <div key={index.name} className="rounded-[22px] border border-black/[0.05] bg-white/55 p-4">
                <div className="text-[13px] text-muted-foreground">{index.name}</div>
                <div className="mt-2 text-xl font-semibold tracking-[-0.03em] text-foreground/90">{index.value.toFixed(2)}</div>
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

          {data.market_review.northbound?.description ? (
            <div className="rounded-[22px] border border-black/[0.05] bg-white/55 px-4 py-4 text-sm leading-7 text-muted-foreground">
              {data.market_review.northbound.description}
            </div>
          ) : null}
        </GlassCard>
      ) : null}

      {!data && !loading ? (
        <GlassCard className="p-6">
          <div className="flex items-start gap-4">
            <div
              className="inline-flex h-11 w-11 items-center justify-center rounded-2xl"
              style={{ backgroundColor: "rgba(111, 124, 142, 0.12)", color: SONG_COLORS.indigo }}
            >
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="space-y-2">
              <CardTitle>从默认的 2 个资产开始即可</CardTitle>
              <p className="text-sm leading-7 text-muted-foreground">
                页面会默认带上资产池与个人资产里的前 2 个资产。若要扩展分析范围，只需在“评估标的”里多选，不必再手动拼接代码。
              </p>
            </div>
          </div>
        </GlassCard>
      ) : null}
    </div>
  )
}
