"use client"

import { Search } from "lucide-react"

import { AssetSearchResult } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"

type AssetSearchPickerProps = {
  query: string
  onQueryChange: (value: string) => void
  results: AssetSearchResult[]
  selectedTicker?: string | null
  onSelect: (asset: AssetSearchResult) => void
  loading?: boolean
  placeholder?: string
  description?: string
  emptyText?: string
}

function assetTypeLabel(assetType?: string) {
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

export function AssetSearchPicker({
  query,
  onQueryChange,
  results,
  selectedTicker,
  onSelect,
  loading = false,
  placeholder = "输入代码或名称，例如 002611 或 博时黄金",
  description = "先搜索并确认资产，再补充持仓或别名等信息。",
  emptyText = "没有找到匹配资产，请继续输入更完整的代码或名称。",
}: AssetSearchPickerProps) {
  const showResults = query.trim().length > 0

  return (
    <div className="space-y-4 rounded-2xl border border-black/[0.06] bg-white/80 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
      <div className="space-y-1">
        <div className="text-sm font-medium text-foreground">搜索并确认资产</div>
        <p className="text-xs leading-5 text-muted-foreground">{description}</p>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder={placeholder}
          className="pl-9"
        />
      </div>

      {showResults ? (
        <div className="overflow-hidden rounded-2xl border border-black/[0.06] bg-[rgba(248,245,238,0.78)]">
          {loading ? (
            <div className="px-4 py-5 text-sm text-muted-foreground">正在搜索可用资产...</div>
          ) : results.length === 0 ? (
            <div className="px-4 py-5 text-sm text-muted-foreground">{emptyText}</div>
          ) : (
            <div className="max-h-72 overflow-y-auto">
              {results.map((item) => {
                const selected = selectedTicker === item.ticker
                return (
                  <button
                    key={`${item.ticker}-${item.asset_type}`}
                    type="button"
                    onClick={() => onSelect(item)}
                    className={cn(
                      "flex w-full items-start justify-between gap-3 border-b border-black/[0.05] px-4 py-3 text-left transition-colors last:border-b-0",
                      selected ? "bg-black/[0.05]" : "hover:bg-black/[0.03]",
                    )}
                  >
                    <div className="space-y-1">
                      <div className="font-medium text-foreground">{item.name}</div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>{item.ticker}</span>
                        <Badge variant="outline">{assetTypeLabel(item.asset_type)}</Badge>
                        {item.category ? <span>{item.category}</span> : null}
                        {item.source ? <span>来源 {item.source}</span> : null}
                      </div>
                    </div>
                    {selected ? <Badge variant="secondary">已选中</Badge> : null}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-black/[0.08] bg-[rgba(248,245,238,0.6)] px-4 py-3 text-xs leading-5 text-muted-foreground">
          支持输入基金代码、股票代码、ETF 名称或关键词。系统会优先展示最接近的候选资产，避免把同名或联接基金选错。
        </div>
      )}
    </div>
  )
}
