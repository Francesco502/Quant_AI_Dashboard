"use client"

import { useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api, type SelectorConfig } from "@/lib/api"
import { useStrategies } from "@/lib/use-strategies"

type ScanRow = {
  ticker: string
  name: string
  selector_alias: string
  last_close: number | string
  score?: number
  action?: string
}

const normalizeScanRows = (payload: unknown): ScanRow[] => {
  if (!Array.isArray(payload)) return []
  const rows: ScanRow[] = []
  for (const item of payload) {
    if (!item || typeof item !== "object") continue
    const record = item as Record<string, unknown>
    const ticker = typeof record.ticker === "string" ? record.ticker : ""
    if (!ticker) continue
    rows.push({
      ticker,
      name: typeof record.name === "string" ? record.name : "",
      selector_alias: typeof record.selector_alias === "string" ? record.selector_alias : "",
      last_close:
        typeof record.last_close === "number" || typeof record.last_close === "string"
          ? record.last_close
          : 0,
      score: typeof record.score === "number" ? record.score : undefined,
      action: typeof record.action === "string" ? record.action : undefined,
    })
  }
  return rows
}

export default function MarketScannerPage() {
  const { active: activeStrategies, loading: strategyLoading } = useStrategies()
  const [scanMode, setScanMode] = useState<"universe" | "market">("universe")
  const [scanMarket, setScanMarket] = useState<"CN" | "HK">("CN")
  const [scanStrategy, setScanStrategy] = useState<string>("all")
  const [tradeDate, setTradeDate] = useState("")
  const [minScore, setMinScore] = useState<number>(10)
  const [topN, setTopN] = useState<number>(20)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState("")
  const [rows, setRows] = useState<ScanRow[]>([])

  useEffect(() => {
    setTradeDate(new Date().toISOString().slice(0, 10))
  }, [])

  const strategyOptions = useMemo(
    () => activeStrategies.filter((item): item is SelectorConfig => !!item && !!item.class_name),
    [activeStrategies]
  )

  const handleRun = async () => {
    if (!tradeDate) {
      setMessage("请选择交易日期")
      return
    }

    setLoading(true)
    setMessage("")
    setRows([])
    try {
      const selectorNames = scanStrategy === "all" ? undefined : [scanStrategy]
      const response = await api.stz.run({
        trade_date: tradeDate,
        mode: scanMode,
        selector_names: selectorNames,
        market: scanMarket,
        min_score: minScore,
        top_n: topN,
      })
      const nextRows = normalizeScanRows(response.data)
      setRows(nextRows)
      setMessage(response.message || `已返回 ${nextRows.length} 条结果`)
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "扫描失败")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8 md:space-y-12 p-6 md:p-10">
      <div className="space-y-3">
        <h1 className="text-3xl font-medium tracking-wide text-foreground/90">市场扫描</h1>
        <p className="text-base font-light tracking-wide text-foreground/60">独立扫描页面，可直接筛选信号而不是再跳转到交易页。</p>
      </div>

      <div className="grid grid-cols-1 gap-8 md:gap-12 lg:grid-cols-3">
        <GlassCard className="space-y-6 p-6 md:p-8 border-white/40 bg-white/30 backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
          <div className="space-y-2">
            <Label>交易日期</Label>
            <Input type="date" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>扫描模式</Label>
            <Select value={scanMode} onValueChange={(value) => setScanMode(value as "universe" | "market")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="universe">资产池</SelectItem>
                <SelectItem value="market">全市场</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>市场</Label>
            <Select value={scanMarket} onValueChange={(value) => setScanMarket(value as "CN" | "HK")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="CN">A 股</SelectItem>
                <SelectItem value="HK">港股</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>策略</Label>
            <Select value={scanStrategy} onValueChange={setScanStrategy}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部启用策略</SelectItem>
                {strategyOptions.map((strategy) => (
                  <SelectItem key={strategy.class_name} value={strategy.class_name}>
                    {strategy.alias} ({strategy.class_name})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {strategyLoading ? <p className="text-xs text-muted-foreground">正在加载策略...</p> : null}
          </div>

          <div className="space-y-2">
            <Label>最低分数</Label>
            <Input type="number" value={String(minScore)} onChange={(event) => setMinScore(Number(event.target.value) || 0)} />
          </div>

          <div className="space-y-2">
            <Label>Top N</Label>
            <Input type="number" value={String(topN)} onChange={(event) => setTopN(Number(event.target.value) || 0)} />
          </div>

          <Button className="w-full" onClick={() => void handleRun()} disabled={loading || strategyLoading}>
            {loading ? "扫描中..." : "执行扫描"}
          </Button>
        </GlassCard>

        <GlassCard className="space-y-6 p-6 md:p-10 lg:col-span-2 border-white/40 bg-white/30 backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-medium tracking-wide text-foreground/80">结果</h2>
            <Badge variant="outline">{rows.length} 条</Badge>
          </div>
          {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}

          {rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无结果。</p>
          ) : (
            <div className="max-h-[560px] overflow-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-muted/50">
                  <tr>
                    <th className="p-2 text-left">代码</th>
                    <th className="p-2 text-left">名称</th>
                    <th className="p-2 text-left">策略</th>
                    <th className="p-2 text-right">收盘价</th>
                    <th className="p-2 text-right">分数</th>
                    <th className="p-2 text-left">动作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.ticker}-${row.selector_alias}`} className="border-t">
                      <td className="p-2 font-medium">{row.ticker}</td>
                      <td className="p-2">{row.name || "-"}</td>
                      <td className="p-2">{row.selector_alias || "-"}</td>
                      <td className="p-2 text-right">{Number(row.last_close).toFixed(2)}</td>
                      <td className="p-2 text-right">{row.score?.toFixed(2) ?? "-"}</td>
                      <td className="p-2">{row.action || "HOLD"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
