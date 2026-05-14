"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { CardSkeleton } from "@/components/ui/skeleton"
import { api, type DataFreshnessItem, type SelectorConfig } from "@/lib/api"
import { getTodayInBeijing } from "@/lib/time"
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
  const [freshnessMap, setFreshnessMap] = useState<Record<string, DataFreshnessItem>>({})

  useEffect(() => {
    setTradeDate(getTodayInBeijing())
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
      if (scanMode === "universe") {
        const pool = await api.stz.getAssetPool().catch(() => [])
        const poolTickers = Array.from(new Set((pool || []).map((asset) => asset.ticker).filter(Boolean)))
        if (poolTickers.length > 0) {
          const freshness = await api.dataFreshness.getPrices(poolTickers, 5)
          const nextFreshnessMap = Object.fromEntries(freshness.items.map((item) => [item.ticker, item]))
          setFreshnessMap(nextFreshnessMap)
          const blockingItems = freshness.items.filter((item) => item.should_block)
          if (blockingItems.length > 0) {
            const sample = blockingItems.slice(0, 4).map((item) => item.ticker).join("、")
            await api.audit
              .recordEvent({
                action: "SCAN_BLOCKED_STALE_DATA",
                resource: "asset-pool",
                resource_type: "scan",
                success: false,
                details: { tickers: blockingItems.map((item) => item.ticker), trade_date: tradeDate },
                error_message: "资产池存在过期或缺失价格数据",
              })
              .catch(() => undefined)
            setMessage(`已阻止扫描：${blockingItems.length} 个资产数据过期或缺失（${sample}），请先更新数据源。`)
            return
          }
        }
      } else {
        setFreshnessMap({})
      }

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
      if (nextRows.length > 0) {
        const resultFreshness = await api.dataFreshness
          .getPrices(Array.from(new Set(nextRows.map((row) => row.ticker))), 5)
          .catch(() => null)
        if (resultFreshness) {
          setFreshnessMap((previous) => ({
            ...previous,
            ...Object.fromEntries(resultFreshness.items.map((item) => [item.ticker, item])),
          }))
        }
      }
      await api.audit
        .recordEvent({
          action: "SCAN_RUN",
          resource: scanMode,
          resource_type: "scan",
          details: {
            trade_date: tradeDate,
            market: scanMarket,
            strategy: scanStrategy,
            result_count: nextRows.length,
          },
        })
        .catch(() => undefined)
      setMessage(response.message || `已返回 ${nextRows.length} 条结果`)
    } catch (requestError) {
      await api.audit
        .recordEvent({
          action: "SCAN_RUN",
          resource: scanMode,
          resource_type: "scan",
          success: false,
          details: { trade_date: tradeDate, market: scanMarket, strategy: scanStrategy },
          error_message: requestError instanceof Error ? requestError.message : "扫描失败",
        })
        .catch(() => undefined)
      setMessage(requestError instanceof Error ? requestError.message : "扫描失败")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8 md:space-y-12 p-6 md:p-10">
      <div className="space-y-2">
        <h1 className="page-title">市场扫描</h1>
        <p className="page-subtitle">按交易日、市场与策略范围执行扫描，统一查看候选结果与评分。</p>
      </div>

      <div className="grid grid-cols-1 gap-8 md:gap-12 lg:grid-cols-3">
        <GlassCard className="space-y-6 p-6 md:p-8 border-white/40 bg-[rgba(250,246,239,0.30)] backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
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
              {strategyLoading ? <p className="text-xs text-muted-foreground">正在加载策略…</p> : null}
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
            {loading ? "扫描中…" : "执行扫描"}
          </Button>
        </GlassCard>

        <GlassCard className="space-y-6 p-6 md:p-10 lg:col-span-2 border-white/40 bg-[rgba(250,246,239,0.30)] backdrop-blur-2xl shadow-[0_8px_32px_rgba(142,115,77,0.04)]">
          <div className="flex items-center justify-between">
            <h2 className="section-title">结果</h2>
            <Badge variant="outline">{rows.length} 条</Badge>
          </div>
          {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}

          {loading ? (
            <CardSkeleton rows={5} />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无结果。</p>
          ) : (
            <>
              <div className="space-y-3 lg:hidden">
                {rows.map((row) => (
                  <div key={`${row.ticker}-${row.selector_alias}-mobile`} className="rounded-[24px] border border-border/60 bg-background/72 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">{row.ticker}</div>
                        <div className="mt-1 truncate text-sm text-muted-foreground">{row.name || "-"}</div>
                      </div>
                      <Badge variant="outline">{row.action || "HOLD"}</Badge>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                      <div className="rounded-2xl bg-background/70 px-3 py-2">
                        <div className="text-xs text-muted-foreground">策略</div>
                        <div className="mt-1 truncate font-medium">{row.selector_alias || "-"}</div>
                      </div>
                      <div className="rounded-2xl bg-background/70 px-3 py-2">
                        <div className="text-xs text-muted-foreground">收盘价</div>
                        <div className="mt-1 font-medium tabular-nums">{Number(row.last_close).toFixed(2)}</div>
                      </div>
                      <div className="rounded-2xl bg-background/70 px-3 py-2">
                        <div className="text-xs text-muted-foreground">分数</div>
                        <div className="mt-1 font-medium tabular-nums">{row.score?.toFixed(2) ?? "-"}</div>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button asChild size="sm" variant="outline">
                        <Link href={`/predictions?ticker=${encodeURIComponent(row.ticker)}`}>查看预测</Link>
                      </Button>
                      <Button asChild size="sm" variant="outline">
                        <Link href={`/backtest?mode=classic&ticker=${encodeURIComponent(row.ticker)}`}>进入回测</Link>
                      </Button>
                      <Button asChild size="sm">
                        <Link href={`/trading?symbol=${encodeURIComponent(row.ticker)}`}>生成纸面单</Link>
                      </Button>
                    </div>
                    {freshnessMap[row.ticker] ? (
                      <div className="mt-3 rounded-2xl border border-border/60 bg-background/70 px-3 py-2 text-xs leading-5 text-muted-foreground">
                        数据源 {freshnessMap[row.ticker].source}，最后更新 {freshnessMap[row.ticker].last_date ?? "-"}。
                        {freshnessMap[row.ticker].message}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
              <div className="hidden max-h-[560px] overflow-auto rounded-[24px] border border-border/60 bg-background/45 lg:block">
                <Table>
                  <TableHeader className="sticky top-0 z-10 bg-background/95 backdrop-blur">
                    <TableRow>
                      <TableHead>代码</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead>策略</TableHead>
                      <TableHead className="text-right">收盘价</TableHead>
                      <TableHead className="text-right">分数</TableHead>
                      <TableHead>数据状态</TableHead>
                      <TableHead>动作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={`${row.ticker}-${row.selector_alias}`} className="hover:bg-[rgba(var(--rgb-ochre),0.05)]">
                        <TableCell className="font-mono font-semibold">{row.ticker}</TableCell>
                        <TableCell>{row.name || "-"}</TableCell>
                        <TableCell className="text-foreground/72">{row.selector_alias || "-"}</TableCell>
                        <TableCell className="text-right tabular-nums">{Number(row.last_close).toFixed(2)}</TableCell>
                        <TableCell className="text-right tabular-nums">{row.score?.toFixed(2) ?? "-"}</TableCell>
                        <TableCell>
                          {freshnessMap[row.ticker] ? (
                            <Badge variant={freshnessMap[row.ticker].is_stale ? "destructive" : "success"}>
                              {freshnessMap[row.ticker].is_stale ? "过期" : "可用"}
                            </Badge>
                          ) : (
                            <Badge variant="outline">未检查</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline" className="rounded-full px-2.5 py-1">
                              {row.action || "HOLD"}
                            </Badge>
                            <Button asChild size="sm" variant="outline">
                              <Link href={`/predictions?ticker=${encodeURIComponent(row.ticker)}`}>预测</Link>
                            </Button>
                            <Button asChild size="sm" variant="outline">
                              <Link href={`/backtest?mode=classic&ticker=${encodeURIComponent(row.ticker)}`}>回测</Link>
                            </Button>
                            <Button asChild size="sm">
                              <Link href={`/trading?symbol=${encodeURIComponent(row.ticker)}`}>纸面单</Link>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
