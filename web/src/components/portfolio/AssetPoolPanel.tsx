"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, Check, CheckCircle, Edit2, Plus, RefreshCcw, Trash2, X } from "lucide-react"
import { toast } from "sonner"

import { Asset, AssetSearchResult, api as apiClient } from "@/lib/api"
import { AssetSearchPicker } from "@/components/shared/asset-search-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

function assetTypeLabel(assetType?: string | null) {
  switch (assetType) {
    case "fund":
      return "场外基金"
    case "etf":
      return "场内 ETF"
    case "stock":
      return "股票"
    default:
      return "其他"
  }
}

function priceSourceLabel(source?: string | null) {
  switch (source) {
    case "fund_nav":
      return "基金净值"
    case "sina_realtime":
      return "实时行情"
    case "price_history":
      return "历史价格"
    default:
      return "自动匹配"
  }
}

export function AssetPoolPanel() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editingTicker, setEditingTicker] = useState<string | null>(null)
  const [editAlias, setEditAlias] = useState("")
  const [assetPendingDelete, setAssetPendingDelete] = useState<Asset | null>(null)

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<AssetSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState<AssetSearchResult | null>(null)
  const [newAlias, setNewAlias] = useState("")
  const [adding, setAdding] = useState(false)

  const pushMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text })
    window.setTimeout(() => setMessage(null), 3200)
  }

  const fetchAssetPool = useCallback(async (forceRefresh = false) => {
    setLoading(true)
    try {
      const res = await apiClient.stz.getAssetPool(forceRefresh)
      setAssets(res ?? [])
    } catch (error) {
      console.error(error)
      pushMessage("error", `获取资产池失败: ${String(error)}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchAssetPool()
  }, [fetchAssetPool])

  useEffect(() => {
    if (!isAddDialogOpen) return
    const query = searchQuery.trim()
    if (!query) {
      setSearchResults([])
      setSelectedAsset(null)
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
        toast.error("搜索资产失败")
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

  const openAddDialog = () => {
    setSearchQuery("")
    setSearchResults([])
    setSelectedAsset(null)
    setNewAlias("")
    setIsAddDialogOpen(true)
  }

  const handleAddAsset = async () => {
    if (!selectedAsset) {
      pushMessage("error", "请先从搜索结果里确认要添加的资产")
      return
    }

    setAdding(true)
    try {
      const res = await apiClient.stz.addAsset({
        ticker: selectedAsset.ticker,
        asset_name: selectedAsset.name,
        asset_type: selectedAsset.asset_type,
        alias: newAlias.trim() || undefined,
      })
      setAssets(res.pool ?? [])
      setIsAddDialogOpen(false)
      pushMessage("success", res.message || "资产已加入资产池")
    } catch (error) {
      console.error(error)
      pushMessage("error", `添加资产失败: ${String(error)}`)
    } finally {
      setAdding(false)
    }
  }

  const handleDeleteAsset = async () => {
    if (!assetPendingDelete) return
    const ticker = assetPendingDelete.ticker

    try {
      const res = await apiClient.stz.deleteAsset(ticker)
      setAssets(res.pool ?? [])
      pushMessage("success", res.message || "资产已移除")
      setAssetPendingDelete(null)
    } catch (error) {
      console.error(error)
      pushMessage("error", `移除资产失败: ${String(error)}`)
    }
  }

  const saveAlias = async (ticker: string) => {
    try {
      const res = await apiClient.stz.updateAssetAlias(ticker, editAlias)
      setAssets(res.pool ?? [])
      pushMessage("success", "别名已更新")
    } catch (error) {
      console.error(error)
      pushMessage("error", `更新别名失败: ${String(error)}`)
    } finally {
      setEditingTicker(null)
      setEditAlias("")
    }
  }

  const selectedSummary = useMemo(() => {
    if (!selectedAsset) return null
    return `${selectedAsset.ticker} · ${assetTypeLabel(selectedAsset.asset_type)}`
  }, [selectedAsset])

  return (
    <div className="grid gap-6">
      <GlassCard>
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <h2 className="section-title flex items-center gap-2">
              资产池
              <Badge variant="secondary">{assets.length}</Badge>
            </h2>
            <p className="text-sm text-muted-foreground">
              管理策略扫描、回测和自动交易候选标的。价格会按资产类型自动匹配基金净值或场内行情。
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => void fetchAssetPool(true)}
              disabled={loading}
              aria-label="刷新资产池"
              title="刷新资产池"
            >
              <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
            <Button onClick={openAddDialog}>
              <Plus className="mr-2 h-4 w-4" />
              添加资产
            </Button>
          </div>
        </div>

        {message ? (
          <div
            className={`mb-4 flex items-center gap-2 rounded-lg border p-3 text-sm ${
              message.type === "success"
                ? "border-market-down-soft bg-market-down-soft text-market-down"
                : "border-market-up-soft bg-market-up-soft text-market-up"
            }`}
          >
            {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {message.text}
          </div>
        ) : null}

        <div className="space-y-3 lg:hidden">
          {loading ? (
            <div className="data-panel-muted rounded-[28px] px-5 py-8 text-center text-sm text-muted-foreground">
              正在读取资产池与最新价格…
            </div>
          ) : assets.length === 0 ? (
            <div className="data-panel-muted rounded-[28px] px-5 py-8 text-center">
              <p className="text-sm leading-7 text-muted-foreground">资产池为空。先搜索并添加你想跟踪的基金、ETF 或股票。</p>
              <Button className="mt-4" onClick={openAddDialog}>
                <Plus className="mr-2 h-4 w-4" />
                添加资产
              </Button>
            </div>
          ) : (
            assets.map((asset) => {
              const editing = editingTicker === asset.ticker
              return (
                <div
                  key={`${asset.ticker}-card`}
                  className="rounded-[28px] border border-[rgba(var(--rgb-ink),0.08)] bg-[rgba(var(--rgb-xuan),0.88)] p-4 shadow-[0_14px_34px_rgba(41,33,25,0.06)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-base font-medium text-foreground">{asset.name || asset.ticker}</div>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>{asset.ticker}</span>
                        <Badge variant="outline">{assetTypeLabel(asset.asset_type)}</Badge>
                      </div>
                    </div>
                    <Badge variant="secondary" className="shrink-0">
                      {priceSourceLabel(asset.price_source)}
                    </Badge>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-3">
                      <div className="text-[0.72rem] uppercase tracking-[0.18em] text-foreground/48">最新价格</div>
                      <div className="mt-2 font-mono text-sm tabular-nums text-foreground">
                        {typeof asset.last_price === "number" ? asset.last_price.toFixed(4) : "-"}
                      </div>
                    </div>
                    <div className="rounded-2xl bg-[rgba(var(--rgb-xuan),0.72)] px-3 py-3">
                      <div className="text-[0.72rem] uppercase tracking-[0.18em] text-foreground/48">数据日期</div>
                      <div className="mt-2 text-sm text-foreground">{asset.last_price_date || "暂无日期"}</div>
                    </div>
                  </div>

                  <div className="mt-4 rounded-[22px] border border-[rgba(var(--rgb-ink),0.08)] bg-[rgba(var(--rgb-xuan),0.7)] px-3 py-3">
                    <div className="mb-2 text-sm font-medium text-foreground">资产别名</div>
                    {editing ? (
                      <div className="space-y-2">
                        <Input
                          value={editAlias}
                          onChange={(event) => setEditAlias(event.target.value)}
                          autoFocus
                          onKeyDown={(event) => {
                            if (event.key === "Enter") saveAlias(asset.ticker)
                            if (event.key === "Escape") {
                              setEditingTicker(null)
                              setEditAlias("")
                            }
                          }}
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <Button size="sm" onClick={() => saveAlias(asset.ticker)}>
                            <Check className="mr-2 h-4 w-4" />
                            保存
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingTicker(null)
                              setEditAlias("")
                            }}
                          >
                            <X className="mr-2 h-4 w-4" />
                            取消
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-foreground/76">{asset.alias || "未设置"}</span>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingTicker(asset.ticker)
                            setEditAlias(asset.alias || "")
                          }}
                        >
                          <Edit2 className="mr-2 h-4 w-4" />
                          修改别名
                        </Button>
                      </div>
                    )}
                  </div>

                  <Button
                    variant="ghost"
                    className="mt-3 h-10 w-full rounded-2xl justify-center text-market-up hover:bg-market-up-soft hover:text-market-up"
                    onClick={() => setAssetPendingDelete(asset)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    从资产池移除
                  </Button>
                </div>
              )
            })
          )}
        </div>

        <div className="data-panel-muted hidden overflow-x-auto rounded-2xl lg:block">
          <Table className="min-w-[920px]">
            <TableHeader>
              <TableRow>
                <TableHead>资产</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>别名</TableHead>
                <TableHead className="text-right">最新价格 / 净值</TableHead>
                <TableHead>数据日期与来源</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-28 text-center text-muted-foreground">
                    正在读取资产池与最新价格…
                  </TableCell>
                </TableRow>
              ) : assets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-28 text-center text-muted-foreground">
                    资产池为空。先搜索并添加你想跟踪的基金、ETF 或股票。
                  </TableCell>
                </TableRow>
              ) : (
                assets.map((asset) => (
                  <TableRow key={asset.ticker} className="transition-colors hover:bg-[rgba(var(--rgb-ink),0.02)]">
                    <TableCell>
                      <div className="space-y-1">
                        <div className="font-medium">{asset.name || asset.ticker}</div>
                        <div className="text-xs text-muted-foreground">{asset.ticker}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{assetTypeLabel(asset.asset_type)}</Badge>
                    </TableCell>
                    <TableCell>
                      {editingTicker === asset.ticker ? (
                        <div className="flex items-center gap-2">
                          <Input
                            value={editAlias}
                            onChange={(event) => setEditAlias(event.target.value)}
                            className="h-8 w-40"
                            autoFocus
                            onKeyDown={(event) => {
                              if (event.key === "Enter") saveAlias(asset.ticker)
                              if (event.key === "Escape") {
                                setEditingTicker(null)
                                setEditAlias("")
                              }
                            }}
                          />
                          <Button size="sm" className="h-8 px-3" onClick={() => saveAlias(asset.ticker)}>
                            保存
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 px-3"
                            onClick={() => {
                              setEditingTicker(null)
                              setEditAlias("")
                            }}
                          >
                            取消
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span>{asset.alias || "-"}</span>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 px-3"
                            onClick={() => {
                              setEditingTicker(asset.ticker)
                              setEditAlias(asset.alias || "")
                            }}
                          >
                            <Edit2 className="mr-2 h-3.5 w-3.5" />
                            修改别名
                          </Button>
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {typeof asset.last_price === "number" ? asset.last_price.toFixed(4) : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1 text-sm">
                        <div>{asset.last_price_date || "暂无日期"}</div>
                        <div className="text-xs text-muted-foreground">{priceSourceLabel(asset.price_source)}</div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-3 text-market-up hover:bg-market-up-soft hover:text-market-up"
                        onClick={() => setAssetPendingDelete(asset)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </Button>
                    </TableCell>
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
            <DialogTitle>移除资产</DialogTitle>
            <DialogDescription>
              这会把 {assetPendingDelete?.name || assetPendingDelete?.ticker || "该资产"} 从资产池中移除，后续策略扫描不会再默认纳入它。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssetPendingDelete(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={() => void handleDeleteAsset()}>
              确认移除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto p-0 sm:max-w-3xl">
          <div className="overflow-hidden rounded-3xl">
            <DialogHeader className="border-b border-border/70 px-6 py-5">
              <DialogTitle>添加资产到资产池</DialogTitle>
            </DialogHeader>

            <div className="space-y-5 px-6 py-5">
              <AssetSearchPicker
                query={searchQuery}
                onQueryChange={(value) => {
                  setSearchQuery(value)
                  setSelectedAsset(null)
                }}
                results={searchResults}
                selectedTicker={selectedAsset?.ticker}
                onSelect={(asset) => setSelectedAsset(asset)}
                loading={searching}
                description="支持用基金代码、股票代码、名称关键词模糊搜索。若有多个候选，请先选中正确的那个。"
                emptyText="没有找到匹配资产。请尝试输入更完整的基金名称、代码或关键词。"
              />

              <div className="data-panel space-y-4 rounded-2xl p-5">
                <div className="space-y-1">
                  <div className="text-sm font-medium text-foreground">可选别名</div>
                </div>

                {selectedSummary ? (
                  <div className="data-panel-muted rounded-2xl px-4 py-3 text-sm text-foreground">
                    已选择 <span className="font-medium">{selectedSummary}</span>
                  </div>
                ) : null}

                <div className="space-y-2">
                  <div className="text-sm font-medium text-foreground">资产别名</div>
                  <Input
                    value={newAlias}
                    onChange={(event) => setNewAlias(event.target.value)}
                    placeholder="例如 黄金、核心宽基、电池主题"
                  />
                </div>
              </div>
            </div>

            <DialogFooter className="border-t border-border/70 px-6 py-5">
              <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={handleAddAsset} disabled={adding || !selectedAsset}>
                {adding ? <RefreshCcw className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                确认添加
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
