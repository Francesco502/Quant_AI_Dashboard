"use client"

import { ChevronDown, ListFilter } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { type Asset } from "@/lib/api"
import { cn } from "@/lib/utils"

type MultiAssetPickerProps = {
  assets: Asset[]
  selected: string[]
  onChange: (tickers: string[]) => void
  placeholder?: string
  className?: string
  maxPreview?: number
}

function assetLabel(asset: Asset) {
  return asset.alias || asset.name || asset.ticker
}

export function MultiAssetPicker({
  assets,
  selected,
  onChange,
  placeholder = "请选择标的",
  className,
  maxPreview = 2,
}: MultiAssetPickerProps) {
  const normalizedSelected = selected.map((item) => item.trim().toUpperCase())
  const selectedAssets = assets.filter((asset) => normalizedSelected.includes(asset.ticker.trim().toUpperCase()))
  const previewText =
    selectedAssets.length === 0
      ? placeholder
      : selectedAssets.length <= maxPreview
        ? selectedAssets.map(assetLabel).join(" / ")
        : `${selectedAssets.slice(0, maxPreview).map(assetLabel).join(" / ")} +${selectedAssets.length - maxPreview}`

  const toggleTicker = (ticker: string, checked: boolean) => {
    const normalizedTicker = ticker.trim().toUpperCase()
    const next = checked
      ? Array.from(new Set([...normalizedSelected, normalizedTicker]))
      : normalizedSelected.filter((item) => item !== normalizedTicker)
    onChange(next)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "h-10 w-full justify-between rounded-2xl border-black/[0.07] bg-white/55 px-3 text-left text-sm",
            className,
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            <ListFilter className="h-4 w-4 shrink-0 text-foreground/45" />
            <span className="truncate text-foreground/80">{previewText}</span>
          </span>
          <span className="ml-3 flex shrink-0 items-center gap-2">
            <Badge variant="outline" className="rounded-full border-black/[0.07] bg-white/70 px-2 py-0.5 text-[11px]">
              {selectedAssets.length}
            </Badge>
            <ChevronDown className="h-4 w-4 text-foreground/40" />
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="glass-dropdown w-[320px] rounded-2xl p-2">
        <DropdownMenuLabel className="px-2 py-2 text-xs font-medium text-foreground/55">
          从资产池中选择要分析的标的
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="max-h-72 overflow-y-auto">
          {assets.map((asset) => {
            const checked = normalizedSelected.includes(asset.ticker.trim().toUpperCase())
            return (
              <DropdownMenuCheckboxItem
                key={asset.ticker}
                checked={checked}
                onCheckedChange={(value) => toggleTicker(asset.ticker, Boolean(value))}
                className="rounded-xl px-3 py-2.5"
              >
                <div className="flex min-w-0 flex-col">
                  <span className="truncate text-sm text-foreground/85">{assetLabel(asset)}</span>
                  <span className="text-[11px] text-muted-foreground">{asset.ticker}</span>
                </div>
              </DropdownMenuCheckboxItem>
            )
          })}
        </div>
        <DropdownMenuSeparator />
        <button
          type="button"
          onClick={() => onChange([])}
          className="w-full rounded-xl px-3 py-2 text-left text-xs text-muted-foreground transition hover:bg-black/[0.03] hover:text-foreground/75"
        >
          清空选择
        </button>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
