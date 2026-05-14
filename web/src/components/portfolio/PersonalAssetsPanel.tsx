"use client"

import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, CheckCircle, PencilLine, Plus, RefreshCcw, Trash2, Upload } from "lucide-react"

import {
  AssetSearchResult,
  UserAssetDcaRule,
  UserAssetOverview,
  UserAssetPendingDca,
  UserAssetRow,
  UserAssetTransaction,
  UserAssetUpsertRequest,
  api as apiClient,
} from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { cn, formatCurrency } from "@/lib/utils"
import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AssetSearchPicker } from "@/components/shared/asset-search-picker"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { getTodayInBeijing } from "@/lib/time"

const MotionTableRow = motion.create(TableRow)

type AssetType = "fund" | "etf" | "stock" | "other"

type FormState = {
  ticker: string
  asset_name: string
  asset_type: AssetType | ""
  avg_cost: string
  units: string
  dca_enabled: boolean
  dca_rule: UserAssetDcaRule
}

const today = getTodayInBeijing()

const weeklyOptions = [
  { value: "0", label: "周一" },
  { value: "1", label: "周二" },
  { value: "2", label: "周三" },
  { value: "3", label: "周四" },
  { value: "4", label: "周五" },
]

const assetTypeOptions: Array<{
  value: AssetType
  label: string
  hint: string
}> = [
  { value: "fund", label: "场外基金", hint: "优先按基金净值估值，适合联接基金、债券基金、货币基金等。" },
  { value: "etf", label: "场内 ETF / LOF", hint: "优先按场内交易价格估值，适合 ETF、LOF 等交易型资产。" },
  { value: "stock", label: "股票", hint: "优先按股票行情估值，适合 A 股、港股、美股等个股。" },
  { value: "other", label: "其他", hint: "保留给暂时无法明确归类的资产，系统会尽量匹配可用数据源。" },
]

function createDefaultDcaRule(): UserAssetDcaRule {
  return {
    enabled: false,
    frequency: "weekly",
    weekday: 3,
    monthday: 15,
    amount: 100,
    start_date: today,
    end_date: undefined,
    shift_to_next_trading_day: true,
    last_run_date: null,
  }
}

const OVERVIEW_CACHE_PREFIX = "user-assets-overview:"
const OVERVIEW_CACHE_VERSION = 4
const OVERVIEW_CACHE_TTL_MS = 12 * 60 * 60 * 1000

type OverviewCachePayload = {
  version: number
  cachedAt: number
  overview: UserAssetOverview
}

function getOverviewCacheKey(username?: string | null): string | null {
  if (typeof window === "undefined") return null
  const resolvedUsername = username || window.localStorage.getItem("user")
  return resolvedUsername ? `${OVERVIEW_CACHE_PREFIX}${resolvedUsername}` : null
}

function readCachedOverview(username?: string | null): UserAssetOverview | null {
  if (typeof window === "undefined") return null
  const key = getOverviewCacheKey(username)
  if (!key) return null

  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<OverviewCachePayload>
    if (
      !parsed ||
      parsed.version !== OVERVIEW_CACHE_VERSION ||
      typeof parsed.cachedAt !== "number" ||
      !parsed.overview ||
      !parsed.overview.summary ||
      !Array.isArray(parsed.overview.assets)
    ) {
      window.localStorage.removeItem(key)
      return null
    }
    if (Date.now() - parsed.cachedAt > OVERVIEW_CACHE_TTL_MS) {
      window.localStorage.removeItem(key)
      return null
    }
    return parsed.overview
  } catch {
    return null
  }
}

function writeCachedOverview(overview: UserAssetOverview, username?: string | null) {
  if (typeof window === "undefined") return
  const key = getOverviewCacheKey(username)
  if (!key) return

  try {
    const payload: OverviewCachePayload = {
      version: OVERVIEW_CACHE_VERSION,
      cachedAt: Date.now(),
      overview,
    }
    window.localStorage.setItem(key, JSON.stringify(payload))
  } catch {
    // Ignore storage failures and keep runtime state authoritative.
  }
}

function inferAssetType(ticker: string, assetName?: string | null, current?: string | null): AssetType {
  const normalized = String(current || "").trim().toLowerCase()
  const currentType =
    normalized === "fund" || normalized === "etf" || normalized === "stock" || normalized === "other"
      ? normalized
      : null

  const code = ticker.trim().toUpperCase()
  const name = String(assetName || "")
  const upperName = name.toUpperCase()
  if ((upperName.includes("ETF") || upperName.includes("LOF")) && !name.includes("联接")) {
    return "etf"
  }
  if (code.startsWith("15") || code.startsWith("50") || code.startsWith("51") || code.startsWith("56") || code.startsWith("58")) {
    return "etf"
  }
  if (
    name.includes("基金") ||
    name.includes("联接") ||
    name.includes("债") ||
    name.includes("货币") ||
    name.includes("滚动持有") ||
    name.includes("中短债") ||
    (code.length === 6 && /[A-Z]$/.test(upperName) && !upperName.includes("ETF") && !upperName.includes("LOF"))
  ) {
    return "fund"
  }
  if (currentType && currentType !== "other") {
    return currentType
  }
  if (code.endsWith(".HK") || code.endsWith(".US") || /^[A-Z]+$/.test(code)) {
    return "stock"
  }
  return currentType || "other"
}

function createEmptyForm(): FormState {
  return {
    ticker: "",
    asset_name: "",
    asset_type: "fund",
    avg_cost: "",
    units: "",
    dca_enabled: false,
    dca_rule: createDefaultDcaRule(),
  }
}

function createFormFromAsset(asset: UserAssetRow): FormState {
  return {
    ticker: asset.ticker,
    asset_name: asset.asset_name || asset.ticker,
    asset_type: inferAssetType(asset.ticker, asset.asset_name, asset.asset_type),
    avg_cost: String(asset.avg_cost ?? ""),
    units: String(asset.units ?? ""),
    dca_enabled: Boolean(asset.dca_rule?.enabled),
    dca_rule: asset.dca_rule ?? createDefaultDcaRule(),
  }
}

function assetTypeLabel(assetType?: string | null) {
  return assetTypeOptions.find((item) => item.value === assetType)?.label || "其他"
}

function valuationHint(assetType?: string | null) {
  const normalized = inferAssetType("", undefined, assetType)
  if (normalized === "fund") return "基金净值估值"
  if (normalized === "etf") return "场内交易价格估值"
  if (normalized === "stock") return "行情价格估值"
  return "自动匹配估值方式"
}

function buildDcaRuleForSubmit(form: FormState): UserAssetDcaRule {
  const base = form.dca_rule ?? createDefaultDcaRule()
  const frequency = base.frequency === "monthly" ? "monthly" : "weekly"

  return {
    ...base,
    enabled: form.dca_enabled,
    frequency,
    weekday: frequency === "weekly" ? base.weekday ?? 3 : undefined,
    monthday: frequency === "monthly" ? base.monthday ?? 15 : undefined,
    amount: Number(base.amount || 0),
    start_date: base.start_date || today,
    shift_to_next_trading_day: base.shift_to_next_trading_day !== false,
  }
}

function buildPayload(form: FormState): UserAssetUpsertRequest {
  return {
    ticker: form.ticker.trim().toUpperCase(),
    asset_name: form.asset_name.trim() || undefined,
    asset_type: form.asset_type || undefined,
    units: Number(form.units || 0),
    avg_cost: Number(form.avg_cost || 0),
    dca_rule: buildDcaRuleForSubmit(form),
  }
}

function validateForm(form: FormState) {
  if (!form.ticker.trim()) return "资产代码不能为空"
  if (!form.asset_name.trim()) return "资产名称不能为空"
  if (!form.asset_type) return "请选择资产类型"
  if (Number(form.avg_cost || 0) <= 0) return "请填写有效的当前持仓成本价"
  if (Number(form.units || 0) <= 0) return "请填写有效的当前持有数量 / 份额"
  if (form.dca_enabled && Number(form.dca_rule.amount || 0) <= 0) return "启用定投时，每次定投金额必须大于 0"
  return null
}

function signedClass(value: number) {
  if (value > 0) return "text-tone-cinnabar"
  if (value < 0) return "text-tone-celadon"
  return "text-foreground/66"
}

function formatSignedCurrency(value: number) {
  const prefix = value > 0 ? "+" : ""
  return `${prefix}${formatCurrency(value)}`
}

function formatQuantity(value: number) {
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatPendingQuantity(value?: number | null) {
  if (value === null || value === undefined) return "-"
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  })
}

function describeDca(rule?: UserAssetDcaRule | null) {
  if (!rule?.enabled) return "未启用"

  if (rule.frequency === "monthly") {
    return `每月 ${rule.monthday || 15} 日 · ${formatCurrency(rule.amount || 0)}`
  }

  const weekday = weeklyOptions.find((item) => item.value === String(rule.weekday ?? 3))?.label || "周四"
  return `${weekday} / ${formatCurrency(rule.amount || 0)}`
}

function renderPendingDcaDescription(pending?: UserAssetPendingDca | null) {
  if (!pending) return null

  const estimateReady =
    typeof pending.estimated_price === "number" &&
    pending.estimated_price > 0 &&
    typeof pending.estimated_units === "number" &&
    pending.estimated_units > 0

  if (!estimateReady) {
    return `已于 ${pending.execution_date} 发起，预计 ${pending.confirmation_date} 确认，${pending.price_basis_date} 净值待公布，确认后再开始计算收益。`
  }

  return `已于 ${pending.execution_date} 发起，预计 ${pending.confirmation_date} 确认，按 ${pending.price_basis_date} 净值 ${pending.estimated_price!.toFixed(4)} 预计确认 ${formatPendingQuantity(pending.estimated_units)} 份，收益从确认后开始计算。`
}

function AssetTypeField({
  value,
  onValueChange,
}: {
  value: AssetType | ""
  onValueChange: (value: AssetType) => void
}) {
  const currentOption = assetTypeOptions.find((item) => item.value === value)

  return (
    <div className="space-y-2">
      <Label>资产类型</Label>
      <Select value={value || undefined} onValueChange={(next) => onValueChange(next as AssetType)}>
        <SelectTrigger>
          <SelectValue placeholder="选择资产类型" />
        </SelectTrigger>
        <SelectContent>
          {assetTypeOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-sm leading-7 text-foreground/66">
        {currentOption?.hint || "选择后，系统会按该资产类型优先匹配适合的数据源和估值方式。"}
      </p>
    </div>
  )
}

function AssetIdentityEditor({
  form,
  onChange,
}: {
  form: FormState
  onChange: (updater: (prev: FormState) => FormState) => void
}) {
  return (
    <div className="data-panel space-y-4 rounded-2xl p-5">
      <div className="flex flex-col gap-1">
        <div className="text-sm font-medium text-foreground">资产信息</div>
        <p className="text-sm leading-7 text-foreground/66">
          资产类型会影响估值时优先调用的数据源。场外基金建议选择“场外基金”，ETF 和 LOF 建议选择“场内 ETF / LOF”。</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <Label>资产代码</Label>
          <Input
            placeholder="如 013281"
            value={form.ticker}
            onChange={(event) => onChange((prev) => ({ ...prev, ticker: event.target.value }))}
          />
        </div>

        <div className="space-y-2">
          <Label>资产名称</Label>
          <Input
            placeholder="如 博时黄金 ETF 联接 C"
            value={form.asset_name}
            onChange={(event) => onChange((prev) => ({ ...prev, asset_name: event.target.value }))}
          />
        </div>

        <AssetTypeField
          value={form.asset_type}
          onValueChange={(value) => onChange((prev) => ({ ...prev, asset_type: value }))}
        />
      </div>
    </div>
  )
}

function HoldingEditor({
  form,
  onChange,
  title = "当前持仓",
  description = "修改后会按新的成本和份额重新计算持仓收益，保存前可以在这里一次性确认。",
}: {
  form: FormState
  onChange: (updater: (prev: FormState) => FormState) => void
  title?: string
  description?: string
}) {
  return (
    <div className="data-panel space-y-4 rounded-2xl p-5">
      <div className="flex flex-col gap-1">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <p className="text-sm leading-7 text-foreground/66">{description}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label>当前持仓成本价</Label>
          <Input
            type="number"
            step="0.0001"
            placeholder="1.1326"
            value={form.avg_cost}
            onChange={(event) => onChange((prev) => ({ ...prev, avg_cost: event.target.value }))}
          />
        </div>

        <div className="space-y-2">
          <Label>当前持有数量 / 份额</Label>
          <Input
            type="number"
            step="0.0001"
            placeholder="2648.88"
            value={form.units}
            onChange={(event) => onChange((prev) => ({ ...prev, units: event.target.value }))}
          />
        </div>
      </div>
    </div>
  )
}

function DcaEditor({
  form,
  onChange,
  dense = false,
}: {
  form: FormState
  onChange: (updater: (prev: FormState) => FormState) => void
  dense?: boolean
}) {
  const gridClass = dense ? "grid gap-3 md:grid-cols-3" : "grid gap-4 md:grid-cols-3"

  return (
    <div className="data-panel-muted space-y-3 rounded-2xl p-4">
      <label className="data-panel-muted flex cursor-pointer items-start gap-3 rounded-2xl px-4 py-3">
        <Checkbox
          checked={form.dca_enabled}
          onCheckedChange={(checked) =>
            onChange((prev) => ({
              ...prev,
              dca_enabled: Boolean(checked),
            }))
          }
        />
        <div className="space-y-1">
          <div className="text-sm font-medium text-foreground/80">纳入定投补算</div>
          <div className="text-sm leading-7 text-foreground/66">
            开启后，系统会按设定的频率和金额自动补算；遇到非交易日会顺延到下一个交易日。</div>
        </div>
      </label>

      {form.dca_enabled ? (
        <div className={gridClass}>
          <div className="space-y-2">
            <Label>定投频率</Label>
            <Select
              value={form.dca_rule.frequency}
              onValueChange={(value) =>
                onChange((prev) => ({
                  ...prev,
                  dca_rule: {
                    ...prev.dca_rule,
                    frequency: value as "weekly" | "monthly",
                  },
                }))
              }
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择频率" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">每周</SelectItem>
                  <SelectItem value="monthly">每月</SelectItem>
                </SelectContent>
              </Select>
            </div>

          <div className="space-y-2">
            <Label>{form.dca_rule.frequency === "weekly" ? "执行日" : "每月几号"}</Label>
            {form.dca_rule.frequency === "weekly" ? (
              <Select
                value={String(form.dca_rule.weekday ?? 3)}
                onValueChange={(value) =>
                  onChange((prev) => ({
                    ...prev,
                    dca_rule: {
                      ...prev.dca_rule,
                      weekday: Number(value),
                    },
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择执行日" />
                </SelectTrigger>
                <SelectContent>
                  {weeklyOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                type="number"
                min="1"
                max="31"
                value={String(form.dca_rule.monthday ?? 15)}
                onChange={(event) =>
                  onChange((prev) => ({
                    ...prev,
                    dca_rule: {
                      ...prev.dca_rule,
                      monthday: Math.min(31, Math.max(1, Number(event.target.value || 15))),
                    },
                  }))
                }
              />
            )}
          </div>

          <div className="space-y-2">
            <Label>每次定投金额</Label>
            <Input
              type="number"
              step="0.01"
              min="0"
              placeholder="100"
              value={String(form.dca_rule.amount ?? "")}
              onChange={(event) =>
                onChange((prev) => ({
                  ...prev,
                  dca_rule: {
                    ...prev.dca_rule,
                    amount: Number(event.target.value || 0),
                  },
                }))
              }
            />
          </div>
        </div>
      ) : (
        <div className="data-empty data-empty-compact text-sm leading-7 text-foreground/66">
          当前只会跟踪这笔持仓的收益变化，不会自动生成定投记录。</div>
      )}
    </div>
  )
}

function AssetEditSummary({
  asset,
  form,
}: {
  asset: UserAssetRow
  form: FormState
}) {
  const resolvedType = inferAssetType(form.ticker, form.asset_name, form.asset_type)
  const estimatedPositionCost = Number(form.avg_cost || 0) * Number(form.units || 0)
  const dcaSummary = form.dca_enabled ? describeDca(buildDcaRuleForSubmit(form)) : "未启用"

  return (
    <div className="overflow-hidden rounded-[28px] border border-[rgba(var(--rgb-ink),0.08)] bg-[linear-gradient(135deg,rgba(var(--rgb-ochre),0.14),rgba(var(--rgb-xuan),0.92))] p-5 shadow-[0_16px_34px_rgba(41,33,25,0.08)]">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">修改资产</Badge>
            <Badge variant="outline">{assetTypeLabel(resolvedType)}</Badge>
            <Badge variant="outline">{valuationHint(resolvedType)}</Badge>
          </div>

          <div>
            <div className="text-xl font-semibold tracking-tight text-foreground">
              {form.asset_name.trim() || asset.asset_name || asset.ticker}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-foreground/66">
              <span>{form.ticker.trim() || asset.ticker}</span>
              {asset.pending_dca ? (
                <Badge className="surface-tone-ochre hover:bg-[rgba(var(--rgb-ochre),0.14)]">有待确认定投</Badge>
              ) : null}
            </div>
          </div>

          <p className="max-w-2xl text-sm leading-7 text-foreground/72">
            编辑入口固定在左侧资产信息区域，点击后会在这个弹窗里集中修改资产信息、持仓成本、份额和定投设置，不再需要横向滚动到表格最右侧处理。          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[420px]">
          <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.7)] p-4 backdrop-blur-sm">
            <div className="text-[0.72rem] font-medium uppercase tracking-[0.2em] text-foreground/48">当前市值</div>
            <div className="mt-2 text-lg font-semibold tabular-nums text-foreground">{formatCurrency(asset.market_value)}</div>
            <div className="mt-1 text-xs text-foreground/60">{asset.last_price_date || "等待最新估值"}</div>
          </div>

          <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.7)] p-4 backdrop-blur-sm">
            <div className="text-[0.72rem] font-medium uppercase tracking-[0.2em] text-foreground/48">持仓投入</div>
            <div className="mt-2 text-lg font-semibold tabular-nums text-foreground">
              {estimatedPositionCost > 0 ? formatCurrency(estimatedPositionCost) : "-"}
            </div>
            <div className="mt-1 text-xs text-foreground/60">按当前输入的成本和份额预估</div>
          </div>

          <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.7)] p-4 backdrop-blur-sm">
            <div className="text-[0.72rem] font-medium uppercase tracking-[0.2em] text-foreground/48">定投状态</div>
            <div className="mt-2 text-sm font-medium text-foreground">{dcaSummary}</div>
            <div className={cn("mt-2 text-xs", signedClass(asset.total_return))}>
              当前累计收益 {formatSignedCurrency(asset.total_return)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function PersonalAssetsPanel() {
  const { user } = useAuth()
  const [overview, setOverview] = useState<UserAssetOverview | null>(() => readCachedOverview())
  const [transactions, setTransactions] = useState<UserAssetTransaction[]>([])
  const [loading, setLoading] = useState(true)
  const [reconciling, setReconciling] = useState(false)
  const [importingCsv, setImportingCsv] = useState(false)
  const [savingDialog, setSavingDialog] = useState(false)
  const [savingEditDialog, setSavingEditDialog] = useState(false)
  const [transactionTicker, setTransactionTicker] = useState<string | null>(null)
  const [expandedAssetTicker, setExpandedAssetTicker] = useState<string | null>(null)
  const [showAllMobileTransactions, setShowAllMobileTransactions] = useState(false)
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [dialogForm, setDialogForm] = useState<FormState>(createEmptyForm())
  const [editForm, setEditForm] = useState<FormState>(createEmptyForm())
  const [editingAsset, setEditingAsset] = useState<UserAssetRow | null>(null)
  const [assetPendingDelete, setAssetPendingDelete] = useState<UserAssetRow | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<AssetSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedSearchAsset, setSelectedSearchAsset] = useState<AssetSearchResult | null>(null)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const pushMessage = useCallback((type: "success" | "error", text: string) => {
    setMessage({ type, text })
    window.setTimeout(() => setMessage(null), 3000)
  }, [])

  useEffect(() => {
    const cached = readCachedOverview(user?.username)
    if (!cached) return

    setOverview((current) => current ?? cached)
    setTransactionTicker((current) => current ?? cached.assets[0]?.ticker ?? null)
  }, [user?.username])

  const loadOverview = useCallback(
    async (syncDca = false, signal?: AbortSignal, refreshMarket = false) => {
      setLoading(true)
      try {
        const result = await apiClient.user.assets.getOverview(syncDca, signal ? { signal } : undefined, refreshMarket)
        setOverview(result)
        writeCachedOverview(result, user?.username)
        setTransactionTicker((current) => current ?? result.assets[0]?.ticker ?? null)
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return
        console.error(error)
        pushMessage("error", `加载个人资产失败：${String(error)}`)
      } finally {
        if (!signal?.aborted) {
          setLoading(false)
        }
      }
    },
    [pushMessage, user?.username]
  )

  const loadTransactions = useCallback(
    async (ticker?: string | null, signal?: AbortSignal) => {
      try {
        const result = await apiClient.user.assets.getTransactions(ticker || undefined, signal ? { signal } : undefined)
        setTransactions(result.transactions ?? [])
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return
        console.error(error)
        pushMessage("error", `加载交易流水失败：${String(error)}`)
      }
    },
    [pushMessage]
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadOverview(false, controller.signal)
    return () => controller.abort()
  }, [loadOverview])

  useEffect(() => {
    const controller = new AbortController()
    void loadTransactions(transactionTicker || undefined, controller.signal)
    return () => controller.abort()
  }, [loadTransactions, transactionTicker])

  useEffect(() => {
    if (!isAddDialogOpen) return
    const query = searchQuery.trim()
    if (!query) {
      setSearchResults([])
      setSelectedSearchAsset(null)
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setSearching(true)
      try {
        const results = await apiClient.stz.searchAssets(query, 12, { signal: controller.signal })
        setSearchResults(results)
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return
        console.error(error)
      } finally {
        if (!controller.signal.aborted) {
          setSearching(false)
        }
      }
    }, 240)

    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [isAddDialogOpen, searchQuery])

  const assets = overview?.assets ?? []
  const summary = overview?.summary
  const isInitialLoading = loading && !overview
  const mobileTransactionGroups = useMemo(() => {
    const rows = showAllMobileTransactions ? transactions : transactions.slice(0, 8)
    const groups = new Map<string, UserAssetTransaction[]>()
    for (const item of rows) {
      const key = item.trade_date || "未记录日期"
      groups.set(key, [...(groups.get(key) || []), item])
    }
    return Array.from(groups.entries()).map(([date, rows]) => ({ date, rows }))
  }, [showAllMobileTransactions, transactions])

  const openAddDialog = () => {
    setDialogForm(createEmptyForm())
    setSearchQuery("")
    setSearchResults([])
    setSelectedSearchAsset(null)
    setIsAddDialogOpen(true)
  }

  const closeEditDialog = () => {
    setIsEditDialogOpen(false)
    setEditingAsset(null)
    setEditForm(createEmptyForm())
  }

  const openEditDialog = (asset: UserAssetRow) => {
    setEditingAsset(asset)
    setEditForm(createFormFromAsset(asset))
    setIsEditDialogOpen(true)
  }

  const handleDelete = async (ticker: string) => {
    try {
      await apiClient.user.assets.remove(ticker)
      await loadOverview(false)
      await loadTransactions(transactionTicker === ticker ? undefined : transactionTicker)
      if (transactionTicker === ticker) setTransactionTicker(null)
      if (editingAsset?.ticker === ticker) closeEditDialog()
      setAssetPendingDelete(null)
      pushMessage("success", "个人资产已删除")
    } catch (error) {
      console.error(error)
      pushMessage("error", `删除失败：${String(error)}`)
    }
  }

  const handleReconcile = async () => {
    setReconciling(true)
    try {
      const result = await apiClient.user.assets.reconcile()
      setOverview(result)
      writeCachedOverview(result, user?.username)
      await loadTransactions(transactionTicker)
      pushMessage("success", `已执行定投补算，本次新增 ${result.reconcile.created} 条记录`)
    } catch (error) {
      console.error(error)
      pushMessage("error", `执行定投补算失败：${String(error)}`)
    } finally {
      setReconciling(false)
    }
  }

  const handleImportCsv = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    setImportingCsv(true)
    try {
      const result = await apiClient.user.assets.importCsv(file)
      setOverview(result)
      writeCachedOverview(result, user?.username)
      setTransactionTicker(result.assets[0]?.ticker ?? null)
      await loadTransactions(result.assets[0]?.ticker ?? null)
      const errorText = result.errors.length > 0 ? `，${result.errors.length} 行未导入` : ""
      pushMessage("success", `已从 CSV 导入 ${result.imported_count} 条个人资产${errorText}`)
    } catch (error) {
      console.error(error)
      pushMessage("error", `CSV 导入失败：${String(error)}`)
    } finally {
      setImportingCsv(false)
    }
  }

  const handleAddAsset = async () => {
    if (!selectedSearchAsset) {
      pushMessage("error", "请先从搜索结果里确认要添加的资产")
      return
    }

    const error = validateForm(dialogForm)
    if (error) {
      pushMessage("error", error)
      return
    }

    setSavingDialog(true)
    try {
      const payload = buildPayload(dialogForm)
      const result = await apiClient.user.assets.upsert(payload)
      setOverview(result)
      writeCachedOverview(result, user?.username)
      setTransactionTicker(payload.ticker)
      await loadTransactions(payload.ticker)
      setIsAddDialogOpen(false)
      setDialogForm(createEmptyForm())
      setSearchQuery("")
      setSearchResults([])
      setSelectedSearchAsset(null)
      pushMessage("success", "个人资产已添加")
    } catch (error) {
      console.error(error)
      pushMessage("error", `添加个人资产失败：${String(error)}`)
    } finally {
      setSavingDialog(false)
    }
  }

  const handleSaveEditDialog = async () => {
    if (!editingAsset) return

    const error = validateForm(editForm)
    if (error) {
      pushMessage("error", error)
      return
    }

    setSavingEditDialog(true)
    try {
      const payload = buildPayload(editForm)
      const result = await apiClient.user.assets.update(editingAsset.ticker, payload)
      setOverview(result)
      writeCachedOverview(result, user?.username)
      setTransactionTicker(payload.ticker)
      await loadTransactions(payload.ticker)
      pushMessage("success", "个人资产已更新，并按新数据重新计算")
      closeEditDialog()
    } catch (error) {
      console.error(error)
      pushMessage("error", `更新个人资产失败：${String(error)}`)
    } finally {
      setSavingEditDialog(false)
    }
  }

  const summaryCards = useMemo(
    () => [
      {
        label: "总市值",
        value: summary ? formatCurrency(summary.total_market_value) : "-",
        extra: `资产数 ${summary?.asset_count ?? 0}`,
      },
      {
        label: "总投入",
        value: summary ? formatCurrency(summary.total_invested_amount) : "-",
        extra: summary?.updated_at || "尚未更新",
      },
      {
        label: "累计收益",
        value: summary ? formatSignedCurrency(summary.total_return) : "-",
        extra: summary ? `${summary.total_return_pct.toFixed(2)}%` : "-",
        className: summary ? signedClass(summary.total_return) : "",
      },
      {
        label: "本周变化",
        value: summary ? formatSignedCurrency(summary.week_change) : "-",
        extra: summary
          ? `${summary.week_change_pct.toFixed(2)}% / 日 ${formatSignedCurrency(summary.day_change)}（${summary.day_change_pct.toFixed(2)}%）`
          : "-",
        className: summary ? signedClass(summary.week_change) : "",
      },
    ],
    [summary]
  )

  const selectedSearchSummary = selectedSearchAsset
    ? `${selectedSearchAsset.ticker} / ${assetTypeLabel(selectedSearchAsset.asset_type)}`
    : null

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((item) => (
          <GlassCard key={item.label}>
            <div className="data-metric-label mb-2">{item.label}</div>
            <div className={cn("text-2xl font-semibold tabular-nums tracking-tight", item.className)}>{item.value}</div>
            <div className="mt-1 text-[0.84rem] leading-6 text-foreground/66">{item.extra}</div>
          </GlassCard>
        ))}
      </div>

      {message ? (
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg border p-3 text-sm",
            message.type === "success"
              ? "border-[rgba(var(--rgb-celadon),0.18)] bg-[rgba(var(--rgb-celadon),0.1)] text-tone-celadon"
              : "border-[rgba(var(--rgb-cinnabar),0.16)] bg-[rgba(var(--rgb-cinnabar),0.1)] text-tone-cinnabar"
          )}
        >
          {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {message.text}
        </div>
      ) : null}

      <GlassCard className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-1">
            <h2 className="section-title flex items-center gap-2">
              个人资产
              <Badge variant="secondary">{assets.length}</Badge>
              {loading ? <Badge variant="outline">同步中</Badge> : null}
            </h2>
            <p className="max-w-2xl text-sm leading-7 text-foreground/66">
              编辑入口已经固定到资产信息区，桌面端突出主操作，移动端改成卡片布局，“修改资产”和“查看流水”的优先级也重新梳理过。            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center justify-center rounded-xl border border-[rgba(var(--rgb-ink),0.1)] bg-[rgba(var(--rgb-xuan),0.84)] px-5 py-2 text-sm font-medium tracking-wide text-foreground/80 shadow-sm transition hover:bg-[rgba(var(--rgb-xuan),0.96)]">
              <Upload className="mr-2 h-4 w-4" />
              {importingCsv ? "导入中…" : "CSV 导入"}
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                disabled={importingCsv}
                onChange={(event) => void handleImportCsv(event)}
              />
            </label>
            <Button variant="outline" onClick={() => loadOverview(false, undefined, true)} disabled={loading}>
              <RefreshCcw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
              刷新估值
            </Button>
            <Button variant="outline" onClick={handleReconcile} disabled={reconciling}>
              <RefreshCcw className={cn("mr-2 h-4 w-4", reconciling && "animate-spin")} />
              执行定投补算
            </Button>
            <Button onClick={openAddDialog}>
              <Plus className="mr-2 h-4 w-4" />
              添加资产
            </Button>
          </div>
        </div>

        <div className="space-y-3 lg:hidden">
          {isInitialLoading ? (
            <div className="data-panel-muted rounded-[28px] px-5 py-8 text-center">
              <RefreshCcw className="mx-auto h-5 w-5 animate-spin text-foreground/56" />
              <div className="mt-3 text-sm font-medium text-foreground/80">正在读取已保存的个人资产</div>
              <div className="mt-2 text-sm leading-7 text-foreground/66">系统会按最新净值刷新你的持仓表现。</div>
            </div>
          ) : assets.length === 0 ? (
            <div className="data-panel-muted rounded-[28px] px-5 py-8 text-center">
              <div className="text-sm leading-7 text-foreground/66">还没有个人资产记录，现在可以直接添加第一笔。</div>
              <Button className="mt-4" onClick={openAddDialog}>
                <Plus className="mr-2 h-4 w-4" />
                添加个人资产
              </Button>
            </div>
          ) : (
            assets.map((asset) => {
              const resolvedType = inferAssetType(asset.ticker, asset.asset_name, asset.asset_type)
              const pendingDcaDescription = renderPendingDcaDescription(asset.pending_dca)
              const showingTransactions = transactionTicker === asset.ticker
              const detailsExpanded = expandedAssetTicker === asset.ticker

              return (
                <motion.div
                  key={`${asset.ticker}-card`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: "spring", bounce: 0, duration: 0.28 }}
                  whileHover={{ y: -1 }}
                  className={cn(
                    "group/asset-card relative overflow-hidden rounded-[28px] border p-4 shadow-[0_14px_34px_rgba(41,33,25,0.06)] transition-[transform,border-color,background-color,box-shadow] duration-300",
                    showingTransactions
                      ? "border-[rgba(var(--rgb-ochre),0.24)] bg-[linear-gradient(160deg,rgba(var(--rgb-ochre),0.12),rgba(var(--rgb-xuan),0.96))] shadow-[0_18px_40px_rgba(41,33,25,0.09)]"
                      : "border-[rgba(var(--rgb-ink),0.08)] bg-[rgba(var(--rgb-xuan),0.88)] hover:border-[rgba(var(--rgb-ink),0.14)] hover:bg-[rgba(var(--rgb-xuan),0.96)] hover:shadow-[0_18px_40px_rgba(41,33,25,0.08)]"
                  )}
                >
                  <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-[rgba(var(--rgb-ochre),0.6)] to-transparent opacity-0 transition-opacity duration-300 group-hover/asset-card:opacity-100" />

                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        className="min-w-0 flex-1 text-left transition-colors hover:text-foreground"
                        onClick={() => setTransactionTicker(asset.ticker)}
                      >
                        <div className="truncate text-base font-medium text-foreground">{asset.asset_name || asset.ticker}</div>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-[0.82rem] text-foreground/66">
                          <span>{asset.ticker}</span>
                          <Badge variant="outline">{assetTypeLabel(resolvedType)}</Badge>
                          <span>{valuationHint(resolvedType)}</span>
                          {asset.dca_rule?.enabled ? <Badge variant="secondary">定投中</Badge> : null}
                        </div>
                      </button>
                      <Badge variant={showingTransactions ? "secondary" : "outline"} className="shrink-0">
                        {showingTransactions ? "流水已锁定" : "查看流水"}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-3">
                        <div className="text-[0.72rem] uppercase tracking-[0.18em] text-foreground/48">当前市值</div>
                        <div className="mt-2 text-lg font-semibold tabular-nums text-foreground">{formatCurrency(asset.market_value)}</div>
                        <div className="mt-1 text-xs text-foreground/56">{asset.last_price_date || "等待最新估值"}</div>
                      </div>
                      <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-3">
                        <div className="text-[0.72rem] uppercase tracking-[0.18em] text-foreground/48">累计收益</div>
                        <div className={cn("mt-2 text-lg font-semibold tabular-nums", signedClass(asset.total_return))}>
                          {formatSignedCurrency(asset.total_return)}
                        </div>
                        <div className="mt-1 text-xs text-foreground/56">{asset.total_return_pct.toFixed(2)}%</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.56)] px-3 py-2">
                        <div className="text-xs text-foreground/48">日变化</div>
                        <div className={cn("mt-1 font-semibold tabular-nums", signedClass(asset.day_change))}>
                          {formatSignedCurrency(asset.day_change)}
                        </div>
                      </div>
                      <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.56)] px-3 py-2">
                        <div className="text-xs text-foreground/48">周变化</div>
                        <div className={cn("mt-1 font-semibold tabular-nums", signedClass(asset.week_change))}>
                          {formatSignedCurrency(asset.week_change)}
                        </div>
                      </div>
                    </div>

                    {detailsExpanded ? (
                      <div className="rounded-[24px] border border-[rgba(var(--rgb-ink),0.08)] bg-[rgba(var(--rgb-xuan),0.72)] px-4 py-3">
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>
                            <div className="text-xs text-foreground/48">成本价</div>
                            <div className="mt-1 font-mono tabular-nums">{asset.avg_cost.toFixed(4)}</div>
                          </div>
                          <div>
                            <div className="text-xs text-foreground/48">持有份额</div>
                            <div className="mt-1 font-mono tabular-nums">{formatQuantity(asset.units)}</div>
                          </div>
                          <div>
                            <div className="text-xs text-foreground/48">当前净值</div>
                            <div className="mt-1 font-mono tabular-nums">{asset.current_price > 0 ? asset.current_price.toFixed(4) : "-"}</div>
                          </div>
                          <div>
                            <div className="text-xs text-foreground/48">定投状态</div>
                            <div className="mt-1">{asset.dca_rule?.enabled ? "已启用" : "未启用"}</div>
                          </div>
                        </div>
                        <div className="mt-3 text-sm leading-7 text-foreground/66">{describeDca(asset.dca_rule)}</div>
                        {asset.pending_dca && pendingDcaDescription ? (
                          <div className="surface-tone-ochre mt-3 rounded-2xl px-3 py-2 text-sm leading-7">
                            {pendingDcaDescription}
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="grid grid-cols-2 gap-2">
                      <Button className="h-10 rounded-2xl" onClick={() => openEditDialog(asset)}>
                        <PencilLine className="mr-2 h-4 w-4" />
                        修改资产
                      </Button>
                      <Button
                        variant={showingTransactions ? "secondary" : "outline"}
                        className="h-10 rounded-2xl"
                        onClick={() => setTransactionTicker(asset.ticker)}
                      >
                        {showingTransactions ? "正在查看流水" : "查看流水"}
                      </Button>
                      <Button
                        variant="outline"
                        className="h-10 rounded-2xl"
                        onClick={() =>
                          setExpandedAssetTicker((current) => (current === asset.ticker ? null : asset.ticker))
                        }
                      >
                        {detailsExpanded ? "收起详情" : "更多详情"}
                      </Button>
                      <Button
                        variant="ghost"
                        className="h-10 rounded-2xl justify-center text-tone-cinnabar hover:bg-[rgba(var(--rgb-cinnabar),0.08)] hover:text-tone-cinnabar"
                        onClick={() => setAssetPendingDelete(asset)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除资产
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )
            })
          )}
        </div>

        <div className="data-panel-muted relative hidden overflow-hidden rounded-[28px] lg:block">
          <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-[rgba(var(--rgb-ochre),0.58)] to-transparent" />
          <div className="overflow-x-auto">
            <Table className="min-w-[1320px]">
              <TableHeader>
                <TableRow className="border-b border-[rgba(var(--rgb-ink),0.08)]">
                  <TableHead className="sticky left-0 z-20 bg-background/95 backdrop-blur">资产</TableHead>
                  <TableHead className="text-right">成本价</TableHead>
                  <TableHead className="text-right">持有数 / 份额</TableHead>
                  <TableHead>定投设置</TableHead>
                  <TableHead className="text-right">当前净值 / 价格</TableHead>
                  <TableHead className="text-right">当前市值</TableHead>
                  <TableHead className="text-right">累计收益</TableHead>
                  <TableHead className="text-right">日</TableHead>
                  <TableHead className="text-right">周</TableHead>
                  <TableHead className="text-right">月</TableHead>
                  <TableHead className="text-right">年</TableHead>
                  <TableHead className="text-right">删除</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isInitialLoading ? (
                  <TableRow>
                    <TableCell colSpan={12} className="h-32 text-center">
                      <div className="flex flex-col items-center gap-3 py-4">
                        <RefreshCcw className="h-5 w-5 animate-spin text-foreground/56" />
                        <div className="space-y-1">
                          <div className="text-sm font-medium text-foreground/80">正在读取已保存的个人资产</div>
                          <div className="text-sm leading-7 text-foreground/66">如果你之前已经录入过资产，请稍等片刻，系统会按最新净值重新计算。</div>
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : assets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={12} className="h-32 text-center">
                      <div className="space-y-3 py-4">
                        <div className="text-sm leading-7 text-foreground/66">还没有个人资产记录，现在可以直接添加第一笔。</div>
                        <Button onClick={openAddDialog}>
                          <Plus className="mr-2 h-4 w-4" />
                          添加个人资产
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  assets.map((asset) => {
                    const resolvedType = inferAssetType(asset.ticker, asset.asset_name, asset.asset_type)
                    const pendingDcaDescription = renderPendingDcaDescription(asset.pending_dca)
                    const showingTransactions = transactionTicker === asset.ticker

                    return (
                      <MotionTableRow
                        key={asset.ticker}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                        className={cn(
                          "group/asset-row border-b border-[rgba(var(--rgb-ink),0.05)] transition-colors duration-200 hover:bg-[rgba(var(--rgb-ink),0.02)]",
                          showingTransactions && "bg-[linear-gradient(90deg,rgba(var(--rgb-ochre),0.08),rgba(var(--rgb-xuan),0.26))]"
                        )}
                      >
                        <TableCell className="sticky left-0 z-20 bg-background/92 p-0 align-top backdrop-blur">
                          <div
                            className={cn(
                              "m-2 rounded-[24px] border px-4 py-4 transition-[border-color,background-color,box-shadow] duration-200",
                              showingTransactions
                                ? "border-[rgba(var(--rgb-ochre),0.24)] bg-[linear-gradient(150deg,rgba(var(--rgb-ochre),0.12),rgba(var(--rgb-xuan),0.95))] shadow-[0_16px_34px_rgba(41,33,25,0.08)]"
                                : "border-[rgba(var(--rgb-ink),0.07)] bg-[rgba(var(--rgb-xuan),0.86)] group-hover/asset-row:border-[rgba(var(--rgb-ink),0.12)] group-hover/asset-row:bg-[rgba(var(--rgb-xuan),0.96)]"
                            )}
                          >
                            <button
                              type="button"
                              className="w-full text-left transition-colors hover:text-foreground"
                              onClick={() => setTransactionTicker(asset.ticker)}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="font-medium text-foreground">{asset.asset_name || asset.ticker}</div>
                                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[0.82rem] text-foreground/66">
                                    <span>{asset.ticker}</span>
                                    <Badge variant="outline">{assetTypeLabel(resolvedType)}</Badge>
                                    <span>{valuationHint(resolvedType)}</span>
                                    {asset.dca_rule?.enabled ? <Badge variant="secondary">定投中</Badge> : null}
                                    {asset.pending_dca ? (
                                      <Badge className="surface-tone-ochre hover:bg-[rgba(var(--rgb-ochre),0.14)]">
                                        已定投，份额待确认
                                      </Badge>
                                    ) : null}
                                  </div>
                                </div>
                                <Badge variant={showingTransactions ? "secondary" : "outline"} className="shrink-0">
                                  {showingTransactions ? "流水展开中" : "点击查看流水"}
                                </Badge>
                              </div>
                            </button>

                            <div className="mt-4 flex flex-wrap gap-2">
                              <Button size="sm" className="h-8 px-3.5" onClick={() => openEditDialog(asset)}>
                                <PencilLine className="mr-2 h-3.5 w-3.5" />
                                修改资产
                              </Button>
                              <Button
                                size="sm"
                                variant={showingTransactions ? "secondary" : "outline"}
                                className="h-8 px-3.5"
                                onClick={() => setTransactionTicker(asset.ticker)}
                              >
                                {showingTransactions ? "正在查看流水" : "查看流水"}
                              </Button>
                            </div>
                          </div>
                        </TableCell>

                        <TableCell className="py-5 text-right font-mono tabular-nums">{asset.avg_cost.toFixed(4)}</TableCell>
                        <TableCell className="py-5 text-right font-mono tabular-nums">{formatQuantity(asset.units)}</TableCell>
                        <TableCell className="py-5">
                          <div className="max-w-[240px] space-y-2">
                            <Badge variant={asset.dca_rule?.enabled ? "secondary" : "outline"}>
                              {asset.dca_rule?.enabled ? "定投中" : "未启用"}
                            </Badge>
                            <div className="text-sm leading-7 text-foreground/66">{describeDca(asset.dca_rule)}</div>
                            {asset.pending_dca && pendingDcaDescription ? (
                              <div className="surface-tone-ochre rounded-xl px-3 py-2 text-sm leading-7">
                                {pendingDcaDescription}
                              </div>
                            ) : null}
                          </div>
                        </TableCell>

                        <TableCell className="py-5 text-right font-mono tabular-nums">
                          {asset.current_price > 0 ? asset.current_price.toFixed(4) : "-"}
                          <div className="text-[0.82rem] text-foreground/66">{asset.last_price_date || "暂无估值日"}</div>
                        </TableCell>
                        <TableCell className="py-5 text-right tabular-nums">{formatCurrency(asset.market_value)}</TableCell>
                        <TableCell className={cn("py-5 text-right font-medium tabular-nums", signedClass(asset.total_return))}>
                          {formatSignedCurrency(asset.total_return)}
                          <div className="text-[0.82rem] text-foreground/66">{asset.total_return_pct.toFixed(2)}%</div>
                        </TableCell>
                        <TableCell className={cn("py-5 text-right tabular-nums", signedClass(asset.day_change))}>
                          {formatSignedCurrency(asset.day_change)}
                        </TableCell>
                        <TableCell className={cn("py-5 text-right tabular-nums", signedClass(asset.week_change))}>
                          {formatSignedCurrency(asset.week_change)}
                        </TableCell>
                        <TableCell className={cn("py-5 text-right tabular-nums", signedClass(asset.month_change))}>
                          {formatSignedCurrency(asset.month_change)}
                        </TableCell>
                        <TableCell className={cn("py-5 text-right tabular-nums", signedClass(asset.year_change))}>
                          {formatSignedCurrency(asset.year_change)}
                        </TableCell>

                        <TableCell className="py-5 text-right align-top">
                          <div className="flex justify-end">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 px-3 text-tone-cinnabar hover:bg-[rgba(var(--rgb-cinnabar),0.1)] hover:text-tone-cinnabar"
                              aria-label={`删除 ${asset.ticker}`}
                              title="删除资产"
                              onClick={() => setAssetPendingDelete(asset)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              删除
                            </Button>
                          </div>
                        </TableCell>
                      </MotionTableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>最近交易流水</CardTitle>
            <CardDescription>展示手工录入、手动买卖和自动定投生成的记录。</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant={transactionTicker === null ? "default" : "outline"} size="sm" onClick={() => setTransactionTicker(null)}>
              全部资产
            </Button>
            {assets.map((asset) => (
              <Button
                key={asset.ticker}
                variant={transactionTicker === asset.ticker ? "default" : "outline"}
                size="sm"
                onClick={() => setTransactionTicker(asset.ticker)}
              >
                {asset.ticker}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-3 lg:hidden">
          {isInitialLoading ? (
            <div className="data-panel-muted rounded-[24px] px-5 py-8 text-center text-sm text-foreground/66">
              正在读取最近交易流水...
            </div>
          ) : transactions.length === 0 ? (
            <div className="data-panel-muted rounded-[24px] px-5 py-8 text-center text-sm text-foreground/66">
              暂无交易流水记录。
            </div>
          ) : (
            <>
              {mobileTransactionGroups.map((group) => (
                <div key={`${group.date}-mobile-group`} className="space-y-2">
                  <div className="sticky top-20 z-10 inline-flex rounded-full border border-border/60 bg-background/90 px-3 py-1 text-xs font-medium text-foreground/62 backdrop-blur">
                    {group.date}
                  </div>
                  {group.rows.map((item) => (
                    <div key={`${item.id}-mobile`} className="rounded-[24px] border border-[rgba(var(--rgb-ink),0.08)] bg-[rgba(var(--rgb-xuan),0.78)] p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium text-foreground">{item.ticker}</div>
                          <div className="mt-1 text-xs text-foreground/56">来源 {item.source || "-"}</div>
                        </div>
                        <Badge variant="outline">{item.transaction_type}</Badge>
                      </div>
                      <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                        <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-2">
                          <div className="text-xs text-foreground/48">数量</div>
                          <div className="mt-1 font-mono tabular-nums">{Number(item.quantity || 0).toFixed(2)}</div>
                        </div>
                        <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-2">
                          <div className="text-xs text-foreground/48">价格</div>
                          <div className="mt-1 font-mono tabular-nums">{Number(item.price || 0).toFixed(4)}</div>
                        </div>
                        <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-2">
                          <div className="text-xs text-foreground/48">金额</div>
                          <div className="mt-1 font-medium tabular-nums">{formatCurrency(Number(item.amount || 0))}</div>
                        </div>
                      </div>
                      <div className="mt-3 text-xs leading-6 text-foreground/58">备注 {item.note || "-"}</div>
                    </div>
                  ))}
                </div>
              ))}
              {transactions.length > 8 ? (
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => setShowAllMobileTransactions((current) => !current)}
                >
                  {showAllMobileTransactions ? "收起交易流水" : `展开全部 ${transactions.length} 条流水`}
                </Button>
              ) : null}
            </>
          )}
        </div>

        <div className="data-panel-muted hidden overflow-x-auto rounded-2xl lg:block">
          <Table className="min-w-[760px]">
            <TableHeader>
              <TableRow>
                <TableHead>日期</TableHead>
                <TableHead>代码</TableHead>
                <TableHead>类型</TableHead>
                <TableHead className="text-right">数量</TableHead>
                <TableHead className="text-right">价格</TableHead>
                <TableHead className="text-right">金额</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>备注</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isInitialLoading ? (
                <TableRow>
                  <TableCell colSpan={8} className="h-20 text-center text-foreground/66">
                    正在读取最近交易流水...
                  </TableCell>
                </TableRow>
              ) : transactions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="h-20 text-center text-foreground/66">
                    暂无交易流水记录。
                  </TableCell>
                </TableRow>
              ) : (
                transactions.slice(0, 20).map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.trade_date}</TableCell>
                    <TableCell className="font-medium">{item.ticker}</TableCell>
                    <TableCell>{item.transaction_type}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{Number(item.quantity || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{Number(item.price || 0).toFixed(4)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(Number(item.amount || 0))}</TableCell>
                    <TableCell>{item.source || "-"}</TableCell>
                    <TableCell>{item.note || "-"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </GlassCard>

      <Dialog open={Boolean(assetPendingDelete)} onOpenChange={(open) => !open && setAssetPendingDelete(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>删除个人资产</DialogTitle>
            <DialogDescription>
              确认删除 {assetPendingDelete?.asset_name || assetPendingDelete?.ticker || "该资产"} 的个人资产记录？删除后会同步刷新持仓和交易流水。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssetPendingDelete(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => assetPendingDelete && void handleDelete(assetPendingDelete.ticker)}
            >
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={isEditDialogOpen} onOpenChange={(open) => (!open ? closeEditDialog() : setIsEditDialogOpen(open))}>
        <DialogContent className="max-h-[88vh] overflow-y-auto p-0 sm:max-w-4xl">
          {editingAsset ? (
            <div className="overflow-hidden rounded-3xl">
              <DialogHeader className="border-b border-border/70 px-6 py-5">
                <DialogTitle>修改个人资产</DialogTitle>
                <DialogDescription className="mt-2 text-sm leading-7 text-foreground/66">
                  这次修改会集中调整资产信息、持仓成本、份额和定投设置，保存后系统会重新计算收益表现。
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-5 px-6 py-5">
                <AssetEditSummary asset={editingAsset} form={editForm} />
                <AssetIdentityEditor form={editForm} onChange={(updater) => setEditForm((prev) => updater(prev))} />
                <HoldingEditor form={editForm} onChange={(updater) => setEditForm((prev) => updater(prev))} />
                <DcaEditor form={editForm} onChange={(updater) => setEditForm((prev) => updater(prev))} />
              </div>

              <DialogFooter className="border-t border-border/70 px-6 py-5">
                <Button variant="outline" onClick={closeEditDialog}>
                  取消
                </Button>
                <Button onClick={handleSaveEditDialog} disabled={savingEditDialog}>
                  {savingEditDialog ? (
                    <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <PencilLine className="mr-2 h-4 w-4" />
                  )}
                  保存修改
                </Button>
              </DialogFooter>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto p-0 sm:max-w-4xl">
          <div className="overflow-hidden rounded-3xl">
            <DialogHeader className="border-b border-border/70 px-6 py-5">
              <DialogTitle>添加个人资产</DialogTitle>
              <DialogDescription className="mt-2 text-sm leading-7 text-foreground/66">
                先确认资产，再一次性录入当前持仓成本、份额和定投设置，后续修改也会使用同样的弹窗流程。
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-5 px-6 py-5">
              <AssetSearchPicker
                query={searchQuery}
                onQueryChange={(value) => {
                  setSearchQuery(value)
                  setSelectedSearchAsset(null)
                }}
                results={searchResults}
                selectedTicker={selectedSearchAsset?.ticker}
                onSelect={(asset) => {
                  setSelectedSearchAsset(asset)
                  setDialogForm((prev) => ({
                    ...prev,
                    ticker: asset.ticker,
                    asset_name: asset.name,
                    asset_type: inferAssetType(asset.ticker, asset.name, asset.asset_type),
                  }))
                }}
                loading={searching}
                description="支持输入代码或名称进行模糊搜索。若出现多个候选，请先选中正确的那一个。"
                emptyText="没有找到匹配资产。请尝试输入更完整的代码、基金名称或关键词。"
              />

              <AssetIdentityEditor form={dialogForm} onChange={(updater) => setDialogForm((prev) => updater(prev))} />

              {selectedSearchSummary ? (
                <div className="data-panel-muted rounded-2xl px-4 py-3 text-sm text-foreground">
                  已确认资产 <span className="font-medium">{selectedSearchSummary}</span>
                </div>
              ) : null}

              <HoldingEditor form={dialogForm} onChange={(updater) => setDialogForm((prev) => updater(prev))} />

              <DcaEditor form={dialogForm} onChange={(updater) => setDialogForm((prev) => updater(prev))} />
            </div>

            <DialogFooter className="border-t border-border/70 px-6 py-5">
              <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={handleAddAsset} disabled={savingDialog || !selectedSearchAsset}>
                {savingDialog ? <RefreshCcw className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                确认添加
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
