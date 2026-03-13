"use client"

import { useEffect, useMemo, useState } from "react"
import { api as apiClient, PaperAccountInfo, SelectorConfig } from "@/lib/api"
import { useStrategies } from "@/lib/use-strategies"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"

type TabKey = "paper" | "scanner" | "signals"

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
  return payload
    .map((item) => {
      if (!item || typeof item !== "object") return null
      const rec = item as Record<string, unknown>
      const ticker = typeof rec.ticker === "string" ? rec.ticker : ""
      if (!ticker) return null
      const row: ScanRow = {
        ticker,
        name: typeof rec.name === "string" ? rec.name : "",
        selector_alias: typeof rec.selector_alias === "string" ? rec.selector_alias : "",
        last_close:
          typeof rec.last_close === "number" || typeof rec.last_close === "string"
            ? rec.last_close
            : 0,
      }
      if (typeof rec.score === "number") row.score = rec.score
      if (typeof rec.action === "string") row.action = rec.action
      return row
    })
    .filter((row): row is ScanRow => row !== null)
}

export default function TradingPage() {
  const { active: activeStrategies, loading: strategyLoading } = useStrategies()

  const [activeTab, setActiveTab] = useState<TabKey>("paper")

  const [account, setAccount] = useState<PaperAccountInfo | null>(null)
  const [accountLoading, setAccountLoading] = useState(false)

  const [scanMode, setScanMode] = useState<"universe" | "market">("universe")
  const [scanMarket, setScanMarket] = useState<"CN" | "HK">("CN")
  const [scanStrategy, setScanStrategy] = useState<string>("all")
  const [tradeDate, setTradeDate] = useState<string>("")
  const [minScore, setMinScore] = useState<number>(10)
  const [topN, setTopN] = useState<number>(20)
  const [scanLoading, setScanLoading] = useState(false)
  const [scanMessage, setScanMessage] = useState<string>("")
  const [scanRows, setScanRows] = useState<ScanRow[]>([])

  useEffect(() => {
    if (typeof window === "undefined") return
    const tab = new URLSearchParams(window.location.search).get("tab")
    if (tab === "paper" || tab === "scanner" || tab === "signals") {
      setActiveTab(tab)
    }
  }, [])

  useEffect(() => {
    setTradeDate(new Date().toISOString().slice(0, 10))
  }, [])

  const refreshAccount = async () => {
    setAccountLoading(true)
    try {
      const response = await apiClient.trading.paper.getAccount()
      setAccount(response)
    } catch (error) {
      console.error("Failed to load paper account", error)
      setAccount(null)
    } finally {
      setAccountLoading(false)
    }
  }

  useEffect(() => {
    void refreshAccount()
  }, [])

  const strategyOptions = useMemo(
    () => activeStrategies.filter((item): item is SelectorConfig => !!item && !!item.class_name),
    [activeStrategies]
  )

  const runScan = async () => {
    if (!tradeDate) {
      setScanMessage("请选择交易日期。")
      return
    }

    setScanLoading(true)
    setScanMessage("")
    setScanRows([])

    try {
      const selectorNames = scanStrategy === "all" ? undefined : [scanStrategy]
      const response = await apiClient.stz.run({
        trade_date: tradeDate,
        mode: scanMode,
        selector_names: selectorNames,
        market: scanMarket,
        min_score: minScore,
        top_n: topN,
      })
      const rows = normalizeScanRows(response.data)
      setScanRows(rows)
      setScanMessage(response.message || `已返回 ${rows.length} 条结果。`)
    } catch (error) {
      console.error("Scan run failed", error)
      setScanMessage("扫描请求失败。")
    } finally {
      setScanLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold">交易中心</h1>
        <p className="text-sm text-muted-foreground">仅支持手动执行，不会自动触发实盘交易任务。</p>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as TabKey)} className="space-y-4">
        <TabsList>
          <TabsTrigger value="paper">模拟账户</TabsTrigger>
          <TabsTrigger value="scanner">市场扫描</TabsTrigger>
          <TabsTrigger value="signals">信号面板</TabsTrigger>
        </TabsList>

        <TabsContent value="paper" className="space-y-4">
          <GlassCard className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">模拟账户</h2>
              <Button variant="outline" onClick={() => void refreshAccount()} disabled={accountLoading}>
                {accountLoading ? "刷新中..." : "刷新"}
              </Button>
            </div>

            {!account ? (
              <p className="text-sm text-muted-foreground">暂无账户数据。</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground uppercase">总资产</div>
                  <div className="text-lg font-semibold">{account.portfolio.total_assets.toLocaleString()}</div>
                </GlassCard>
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground uppercase">可用资金</div>
                  <div className="text-lg font-semibold">{account.portfolio.cash.toLocaleString()}</div>
                </GlassCard>
                <GlassCard className="p-3">
                  <div className="text-xs text-muted-foreground uppercase">持仓市值</div>
                  <div className="text-lg font-semibold">{account.portfolio.market_value.toLocaleString()}</div>
                </GlassCard>
              </div>
            )}
          </GlassCard>
        </TabsContent>

        <TabsContent value="scanner" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <GlassCard className="p-5 space-y-4 h-fit">
              <div className="space-y-2">
                <Label>交易日期</Label>
                <Input type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              </div>

              <div className="space-y-2">
                <Label>扫描模式</Label>
                <Select value={scanMode} onValueChange={(value) => setScanMode(value as "universe" | "market")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="universe">资产池</SelectItem>
                    <SelectItem value="market">全市场扫描</SelectItem>
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
                    <SelectItem value="CN">A股（CN）</SelectItem>
                    <SelectItem value="HK">港股（HK）</SelectItem>
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
                {strategyLoading && <p className="text-xs text-muted-foreground">正在加载策略...</p>}
              </div>

              <div className="space-y-2">
                <Label>最低分数</Label>
                <Input
                  type="number"
                  value={String(minScore)}
                  onChange={(e) => setMinScore(Number(e.target.value) || 0)}
                />
              </div>

              <div className="space-y-2">
                <Label>结果数量 Top N</Label>
                <Input
                  type="number"
                  value={String(topN)}
                  onChange={(e) => setTopN(Number(e.target.value) || 0)}
                />
              </div>

              <Button className="w-full" onClick={() => void runScan()} disabled={scanLoading || strategyLoading}>
                {scanLoading ? "扫描中..." : "执行扫描"}
              </Button>
            </GlassCard>

            <GlassCard className="lg:col-span-2 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">扫描结果</h2>
                <Badge variant="outline">{scanRows.length} 条</Badge>
              </div>

              {scanMessage && <p className="text-sm text-muted-foreground">{scanMessage}</p>}

              {scanRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无结果。</p>
              ) : (
                <div className="rounded-md border overflow-auto max-h-[520px]">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="text-left p-2">Ticker</th>
                        <th className="text-left p-2">Name</th>
                        <th className="text-left p-2">Selector</th>
                        <th className="text-right p-2">Last Close</th>
                        <th className="text-right p-2">Score</th>
                        <th className="text-left p-2">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scanRows.map((row, index) => (
                        <tr key={`${row.ticker}-${index}`} className="border-t">
                          <td className="p-2 font-medium">{row.ticker}</td>
                          <td className="p-2">{row.name}</td>
                          <td className="p-2">{row.selector_alias}</td>
                          <td className="p-2 text-right">{Number(row.last_close).toFixed(2)}</td>
                          <td className="p-2 text-right">{row.score?.toFixed(2) ?? "-"}</td>
                          <td className="p-2">{row.action ?? "HOLD"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </GlassCard>
          </div>
        </TabsContent>

        <TabsContent value="signals" className="space-y-4">
          <GlassCard className="p-5 space-y-2">
            <h2 className="text-lg font-semibold">Signal Snapshot</h2>
            <p className="text-sm text-muted-foreground">Latest scanner output can be manually reviewed and then executed in paper account.</p>
            <p className="text-sm text-muted-foreground">Current scanner rows: {scanRows.length}</p>
          </GlassCard>
        </TabsContent>
      </Tabs>
    </div>
  )
}
