"use client"

import { Fragment, useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, CheckCircle, PencilLine, Plus, RefreshCcw, Trash2 } from "lucide-react"

import {
  AssetSearchResult,
  UserAssetDcaRule,
  UserAssetOverview,
  UserAssetRow,
  UserAssetTransaction,
  UserAssetUpsertRequest,
  api as apiClient,
} from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { cn, formatCurrency } from "@/lib/utils"
import { motion, AnimatePresence } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { GlassCard } from "@/components/ui/card"
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

const today = new Date().toISOString().slice(0, 10)

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
  { value: "fund", label: "场外基金", hint: "优先按基金净值估值，适合联接基金、债券基金、货币基金。" },
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
const OVERVIEW_CACHE_VERSION = 2
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
  if (normalized === "etf") return "场内交易价估值"
  if (normalized === "stock") return "行情价估值"
  return "自动匹配估值"
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
  if (Number(form.units || 0) <= 0) return "请填写有效的当前持有数 / 份额"
  if (form.dca_enabled && Number(form.dca_rule.amount || 0) <= 0) return "启用定投时，每次定投金额必须大于 0"
  return null
}

function signedClass(value: number) {
  if (value > 0) return "text-market-up"
  if (value < 0) return "text-market-down"
  return "text-muted-foreground"
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

function describeDca(rule?: UserAssetDcaRule | null) {
  if (!rule?.enabled) return "未启用"

  if (rule.frequency === "monthly") {
    return `每月 ${rule.monthday || 15} 日 · ${formatCurrency(rule.amount || 0)}`
  }

  const weekday = weeklyOptions.find((item) => item.value === String(rule.weekday ?? 3))?.label || "周四"
  return `${weekday} · ${formatCurrency(rule.amount || 0)}`
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
      <p className="text-xs leading-5 text-muted-foreground">
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
    <div className="space-y-4 rounded-2xl border border-black/[0.06] bg-white/75 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
      <div className="flex flex-col gap-1">
        <div className="text-sm font-medium text-foreground">资产信息</div>
        <p className="text-xs leading-5 text-muted-foreground">
          资产类型会影响估值时优先调用的数据源。场外基金建议选择“场外基金”，ETF 和 LOF 建议选择“场内 ETF / LOF”。
        </p>
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
            placeholder="如 博时黄金ETF联接C"
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
    <div className="space-y-3 rounded-2xl border border-black/[0.06] bg-black/[0.02] p-4">
      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-black/[0.05] bg-white/70 px-4 py-3">
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
          <div className="text-xs leading-5 text-muted-foreground">
            开启后，系统会按设定的频率和金额自动补算；遇到非交易日会顺延到下一个交易日。
          </div>
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
        <div className="rounded-2xl border border-dashed border-black/[0.08] bg-white/50 px-4 py-3 text-xs leading-5 text-muted-foreground">
          当前只会跟踪这笔持仓的收益变化，不会自动生成定投记录。
        </div>
      )}
    </div>
  )
}

export function PersonalAssetsPanel() {
  const { user } = useAuth()
  const [overview, setOverview] = useState<UserAssetOverview | null>(() => readCachedOverview())
  const [transactions, setTransactions] = useState<UserAssetTransaction[]>([])
  const [loading, setLoading] = useState(true)
  const [reconciling, setReconciling] = useState(false)
  const [savingDialog, setSavingDialog] = useState(false)
  const [savingInline, setSavingInline] = useState(false)
  const [editingTicker, setEditingTicker] = useState<string | null>(null)
  const [inlineForm, setInlineForm] = useState<FormState | null>(null)
  const [transactionTicker, setTransactionTicker] = useState<string | null>(null)
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [dialogForm, setDialogForm] = useState<FormState>(createEmptyForm())
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
    async (syncDca = true, signal?: AbortSignal) => {
      setLoading(true)
      try {
        const result = await apiClient.user.assets.getOverview(syncDca, signal ? { signal } : undefined)
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

  const isEditing = useCallback(
    (ticker: string) => editingTicker === ticker && inlineForm !== null,
    [editingTicker, inlineForm]
  )

  const startEdit = (asset: UserAssetRow) => {
    setEditingTicker(asset.ticker)
    setInlineForm(createFormFromAsset(asset))
  }

  const cancelEdit = () => {
    setEditingTicker(null)
    setInlineForm(null)
  }

  const openAddDialog = () => {
    setDialogForm(createEmptyForm())
    setSearchQuery("")
    setSearchResults([])
    setSelectedSearchAsset(null)
    setIsAddDialogOpen(true)
  }

  const handleDelete = async (ticker: string) => {
    if (!window.confirm(`确认删除 ${ticker} 的个人资产记录吗？`)) return

    try {
      await apiClient.user.assets.remove(ticker)
      await loadOverview(false)
      await loadTransactions(transactionTicker === ticker ? undefined : transactionTicker)
      if (transactionTicker === ticker) setTransactionTicker(null)
      if (editingTicker === ticker) cancelEdit()
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

  const handleConfirmInlineEdit = async (originalTicker: string) => {
    if (!inlineForm) return

    const error = validateForm(inlineForm)
    if (error) {
      pushMessage("error", error)
      return
    }

    setSavingInline(true)
    try {
      const payload = buildPayload(inlineForm)
      const result = await apiClient.user.assets.update(originalTicker, payload)
      setOverview(result)
      writeCachedOverview(result, user?.username)
      setTransactionTicker(payload.ticker)
      await loadTransactions(payload.ticker)
      pushMessage("success", "个人资产已更新，并按新数据重新计算")
      cancelEdit()
    } catch (error) {
      console.error(error)
      pushMessage("error", `更新个人资产失败：${String(error)}`)
    } finally {
      setSavingInline(false)
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
        extra: summary ? `日 ${formatSignedCurrency(summary.day_change)}` : "-",
        className: summary ? signedClass(summary.week_change) : "",
      },
    ],
    [summary]
  )

  const selectedSearchSummary = selectedSearchAsset
    ? `${selectedSearchAsset.ticker} · ${assetTypeLabel(selectedSearchAsset.asset_type)}`
    : null

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((item) => (
          <GlassCard key={item.label}>
            <div className="mb-2 text-sm text-muted-foreground">{item.label}</div>
            <div className={cn("text-2xl font-semibold tracking-tight", item.className)}>{item.value}</div>
            <div className="mt-1 text-xs text-muted-foreground">{item.extra}</div>
          </GlassCard>
        ))}
      </div>

      {message ? (
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg border p-3 text-sm",
            message.type === "success"
              ? "border-market-down-soft bg-market-down-soft text-market-down"
              : "border-market-up-soft bg-market-up-soft text-market-up"
          )}
        >
          {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {message.text}
        </div>
      ) : null}

      <GlassCard className="space-y-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h2 className="flex items-center gap-2 text-xl font-semibold">
              个人资产
              <Badge variant="secondary">{assets.length}</Badge>
              {loading ? <Badge variant="outline">正在读取</Badge> : null}
            </h2>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => loadOverview(true)} disabled={loading}>
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

        <div className="relative overflow-hidden rounded-2xl border border-black/[0.06] shadow-[inset_-10px_0_10px_-10px_rgba(0,0,0,0.05)]">
          <div className="overflow-x-auto">
            <Table className="min-w-[1260px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="sticky left-0 z-20 bg-background/90 backdrop-blur">资产</TableHead>
                  <TableHead className="text-right">成本价</TableHead>
                <TableHead className="text-right">持有数 / 份额</TableHead>
                <TableHead>定投</TableHead>
                <TableHead className="text-right">当前净值 / 价格</TableHead>
                <TableHead className="text-right">当前市值</TableHead>
                <TableHead className="text-right">累计收益</TableHead>
                <TableHead className="text-right">日</TableHead>
                <TableHead className="text-right">周</TableHead>
                <TableHead className="text-right">月</TableHead>
                <TableHead className="text-right">年</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isInitialLoading ? (
                <TableRow>
                  <TableCell colSpan={12} className="h-32 text-center">
                    <div className="flex flex-col items-center gap-3 py-4">
                      <RefreshCcw className="h-5 w-5 animate-spin text-muted-foreground" />
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-foreground/80">正在读取已保存的个人资产</div>
                        <div className="text-xs text-muted-foreground">如果你之前已经录入过资产，请稍等片刻，系统会按最新净值重新计算。</div>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              ) : assets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={12} className="h-32 text-center">
                    <div className="space-y-3 py-4">
                      <div className="text-sm text-muted-foreground">还没有个人资产记录，现在可以直接添加第一笔。</div>
                      <Button onClick={openAddDialog}>
                        <Plus className="mr-2 h-4 w-4" />
                        添加个人资产
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                <AnimatePresence>
                  {assets.map((asset) => {
                    const editingThisRow = isEditing(asset.ticker)
                    const draft = editingThisRow && inlineForm ? inlineForm : null
                    const resolvedType = inferAssetType(asset.ticker, asset.asset_name, asset.asset_type)

                    return (
                      <Fragment key={asset.ticker}>
                        <MotionTableRow
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, scale: 0.95 }}
                          transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                          className={editingThisRow ? "bg-black/[0.02]" : ""}
                        >
                          <TableCell className="sticky left-0 z-20 bg-background/90 backdrop-blur">
                            <button
                            type="button"
                            className="text-left transition-colors hover:text-foreground"
                            onClick={() => setTransactionTicker(asset.ticker)}
                          >
                            <div className="font-medium">{asset.asset_name || asset.ticker}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              <span>{asset.ticker}</span>
                              <Badge variant="outline">{assetTypeLabel(resolvedType)}</Badge>
                              <span>{valuationHint(resolvedType)}</span>
                              {asset.dca_rule?.enabled ? <Badge variant="secondary">定投中</Badge> : null}
                            </div>
                          </button>
                        </TableCell>

                        <TableCell className="text-right font-mono">
                          {draft ? (
                            <Input
                              type="number"
                              step="0.0001"
                              value={draft.avg_cost}
                              onChange={(event) =>
                                setInlineForm((prev) => (prev ? { ...prev, avg_cost: event.target.value } : prev))
                              }
                              className="ml-auto h-9 w-28 text-right"
                            />
                          ) : (
                            asset.avg_cost.toFixed(4)
                          )}
                        </TableCell>

                        <TableCell className="text-right font-mono">
                          {draft ? (
                            <Input
                              type="number"
                              step="0.0001"
                              value={draft.units}
                              onChange={(event) =>
                                setInlineForm((prev) => (prev ? { ...prev, units: event.target.value } : prev))
                              }
                              className="ml-auto h-9 w-32 text-right"
                            />
                          ) : (
                            formatQuantity(asset.units)
                          )}
                        </TableCell>

                        <TableCell>
                          {draft ? (
                            <div className="space-y-1">
                              <Badge variant={draft.dca_enabled ? "secondary" : "outline"}>
                                {draft.dca_enabled ? "定投已开启" : "未启用"}
                              </Badge>
                              <div className="text-xs text-muted-foreground">
                                {draft.dca_enabled ? describeDca(buildDcaRuleForSubmit(draft)) : "在下方编辑定投设置"}
                              </div>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <Badge variant={asset.dca_rule?.enabled ? "secondary" : "outline"}>
                                {asset.dca_rule?.enabled ? "定投中" : "未启用"}
                              </Badge>
                              <div className="text-xs text-muted-foreground">{describeDca(asset.dca_rule)}</div>
                            </div>
                          )}
                        </TableCell>

                        <TableCell className="text-right font-mono">
                          {asset.current_price > 0 ? asset.current_price.toFixed(4) : "-"}
                          <div className="text-xs text-muted-foreground">{asset.last_price_date || "暂无估值日"}</div>
                        </TableCell>

                        <TableCell className="text-right">{formatCurrency(asset.market_value)}</TableCell>

                        <TableCell className={cn("text-right font-medium", signedClass(asset.total_return))}>
                          {formatSignedCurrency(asset.total_return)}
                          <div className="text-xs text-muted-foreground">{asset.total_return_pct.toFixed(2)}%</div>
                        </TableCell>

                        <TableCell className={cn("text-right", signedClass(asset.day_change))}>
                          {formatSignedCurrency(asset.day_change)}
                        </TableCell>
                        <TableCell className={cn("text-right", signedClass(asset.week_change))}>
                          {formatSignedCurrency(asset.week_change)}
                        </TableCell>
                        <TableCell className={cn("text-right", signedClass(asset.month_change))}>
                          {formatSignedCurrency(asset.month_change)}
                        </TableCell>
                        <TableCell className={cn("text-right", signedClass(asset.year_change))}>
                          {formatSignedCurrency(asset.year_change)}
                        </TableCell>

                        <TableCell className="text-right">
                          {draft ? (
                            <div className="flex justify-end gap-2">
                              <Button variant="ghost" size="sm" onClick={cancelEdit}>
                                取消
                              </Button>
                              <Button size="sm" onClick={() => handleConfirmInlineEdit(asset.ticker)} disabled={savingInline}>
                                {savingInline ? <RefreshCcw className="mr-2 h-4 w-4 animate-spin" /> : null}
                                确认更新
                              </Button>
                            </div>
                          ) : (
                            <div className="flex justify-end gap-1">
                              <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEdit(asset)}>
                                <PencilLine className="h-4 w-4" />
                              </Button>
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-8 w-8 text-market-up hover:bg-market-up-soft hover:text-market-up"
                                onClick={() => handleDelete(asset.ticker)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </MotionTableRow>

                      {draft ? (
                        <MotionTableRow 
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                          className="bg-black/[0.02]"
                        >
                          <TableCell colSpan={12} className="px-5 py-4">
                            <div className="space-y-4 rounded-2xl border border-black/[0.06] bg-white/80 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
                              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                  <div className="text-sm font-medium">编辑资产与定投</div>
                                  <div className="text-xs text-muted-foreground">
                                    资产代码、名称、类型、成本价、持有数和定投规则都可以在这里修改；确认后系统会按新数据重新计算。
                                  </div>
                                </div>
                                <Badge variant="outline">{draft.ticker || asset.ticker}</Badge>
                              </div>

                              <AssetIdentityEditor
                                form={draft}
                                onChange={(updater) => setInlineForm((prev) => (prev ? updater(prev) : prev))}
                              />

                              <DcaEditor
                                form={draft}
                                onChange={(updater) => setInlineForm((prev) => (prev ? updater(prev) : prev))}
                                dense
                              />
                            </div>
                          </TableCell>
                        </MotionTableRow>
                      ) : null}
                    </Fragment>
                  )
                })}
                </AnimatePresence>
              )}
            </TableBody>
          </Table>
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-semibold">最近交易流水</h3>
            <p className="text-xs text-muted-foreground">展示手工重置、手工买卖和自动定投生成的记录。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant={transactionTicker === null ? "default" : "outline"} size="sm" onClick={() => setTransactionTicker(null)}>
              全部
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

        <div className="overflow-x-auto rounded-md border">
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
                  <TableCell colSpan={8} className="h-20 text-center text-muted-foreground">
                    正在读取最近交易流水...
                  </TableCell>
                </TableRow>
              ) : transactions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="h-20 text-center text-muted-foreground">
                    暂无交易流水。
                  </TableCell>
                </TableRow>
              ) : (
                transactions.slice(0, 20).map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.trade_date}</TableCell>
                    <TableCell className="font-medium">{item.ticker}</TableCell>
                    <TableCell>{item.transaction_type}</TableCell>
                    <TableCell className="text-right font-mono">{Number(item.quantity || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono">{Number(item.price || 0).toFixed(4)}</TableCell>
                    <TableCell className="text-right">{formatCurrency(Number(item.amount || 0))}</TableCell>
                    <TableCell>{item.source || "-"}</TableCell>
                    <TableCell>{item.note || "-"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </GlassCard>

      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto border border-[#d8d1c2] bg-[rgba(248,245,238,0.98)] p-0 shadow-[0_28px_80px_rgba(28,24,18,0.22)] backdrop-blur-none sm:max-w-3xl">
          <div className="overflow-hidden rounded-3xl">
            <DialogHeader className="border-b border-black/[0.06] px-6 py-5">
              <DialogTitle>添加个人资产</DialogTitle>
              <DialogDescription className="leading-6">
                先搜索并确认资产，再录入你当前的持仓成本、持有份额和定投规则，避免把同代码或同主题的基金选错。
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
                <div className="rounded-2xl border border-black/[0.06] bg-[rgba(248,245,238,0.8)] px-4 py-3 text-sm text-foreground">
                  已确认资产 <span className="font-medium">{selectedSearchSummary}</span>
                </div>
              ) : null}

              <div className="space-y-4 rounded-2xl border border-black/[0.06] bg-white/75 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                <div className="flex flex-col gap-1">
                  <div className="text-sm font-medium text-foreground">当前持仓</div>
                  <p className="text-xs leading-5 text-muted-foreground">
                    这里填写的是你此刻手上的成本价和持有数量，确认后系统会立刻重新计算当前市值与累计收益。
                  </p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="dialog-asset-cost">当前持仓成本价</Label>
                    <Input
                      id="dialog-asset-cost"
                      type="number"
                      step="0.0001"
                      placeholder="1.1326"
                      value={dialogForm.avg_cost}
                      onChange={(event) => setDialogForm((prev) => ({ ...prev, avg_cost: event.target.value }))}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="dialog-asset-units">当前持有数 / 份额</Label>
                    <Input
                      id="dialog-asset-units"
                      type="number"
                      step="0.0001"
                      placeholder="2648.88"
                      value={dialogForm.units}
                      onChange={(event) => setDialogForm((prev) => ({ ...prev, units: event.target.value }))}
                    />
                  </div>
                </div>
              </div>

              <DcaEditor form={dialogForm} onChange={(updater) => setDialogForm((prev) => updater(prev))} />
            </div>

            <DialogFooter className="border-t border-black/[0.06] px-6 py-5">
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
