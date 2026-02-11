"use client"

import { useState, useEffect, useCallback } from "react"
import { api as apiClient, Signal, PaperAccountInfo, Position, TradeHistoryRecord, ScanResult, SelectorConfig } from "@/lib/api"
import { GlassCard, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Zap, PlayCircle, History, ArrowUpRight, ArrowDownRight, Minus, RefreshCw, Wallet, Search, Filter, Layers, CheckCircle2 } from "lucide-react"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { useStrategies } from "@/lib/use-strategies"

// Simple Badge component inline for now
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
    executed: "bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20",
    expired: "bg-foreground/5 text-foreground/40 hover:bg-foreground/8",
    failed: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors ${styles[status.toLowerCase()] || styles.expired}`}>
      {status}
    </span>
  )
}

function DirectionIcon({ direction }: { direction: number }) {
  if (direction > 0) return <ArrowUpRight className="h-4 w-4 text-red-500" />
  if (direction < 0) return <ArrowDownRight className="h-4 w-4 text-emerald-500" />
  return <Minus className="h-4 w-4 text-gray-500" />
}

// 扫描结果行类型
type ScanResultRow = {
  ticker: string
  name: string
  selector_alias: string
  last_close: number | string
}

export default function TradingPage() {
  const [activeTab, setActiveTab] = useState("paper")
  const [lookbackDays, setLookbackDays] = useState(30)
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(false)
  
  // Paper Trading State
  const [account, setAccount] = useState<PaperAccountInfo | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [tradeHistory, setTradeHistory] = useState<TradeHistoryRecord[]>([])
  const [orderForm, setOrderForm] = useState({ ticker: "", action: "BUY", shares: 100, price: 0 })
  
  // ====== 市场扫描 State（重新设计） ======
  const { strategies: stzStrategies, active: activeStzStrategies, loading: strategiesLoading } = useStrategies()
  const [scanMode, setScanMode] = useState<"universe" | "market">("universe")
  const [scanStrategy, setScanStrategy] = useState<string>("all")
  const [scanDate, setScanDate] = useState<string>(() => new Date().toISOString().split('T')[0])
  const [scanning, setScanning] = useState(false)
  const [scanResults, setScanResults] = useState<ScanResultRow[]>([])
  const [scanMessage, setScanMessage] = useState<string>("")

  // --- Data Fetching ---

  const fetchSignals = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.signals.list({ days: lookbackDays })
      if (res) setSignals(res)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [lookbackDays])

  const fetchAccountInfo = useCallback(async () => {
      try {
          const res = await apiClient.trading.paper.getAccount()
          if (res && res.status === "success") {
              setAccount(res)
              setPositions(res.portfolio.positions)
          } else {
              // Try to create default if not exists
              if (res && (res as any).message === "未找到默认账户") {
                  await apiClient.trading.paper.createAccount({ name: "默认模拟账户" })
                  fetchAccountInfo() // Retry
              }
          }
      } catch (e) {
          console.error("Fetch account failed:", e)
      }
  }, [])
  
  const fetchTradeHistory = useCallback(async () => {
      try {
          const res = await apiClient.trading.paper.getHistory()
          if (res) setTradeHistory(res)
      } catch (e) {
          console.error("Fetch history failed:", e)
      }
  }, [])

  useEffect(() => {
    if (activeTab === "signals") fetchSignals()
    if (activeTab === "paper") {
        fetchAccountInfo()
        fetchTradeHistory()
    }
  }, [activeTab, fetchSignals, fetchAccountInfo, fetchTradeHistory])

  // --- Handlers ---

  const handleExecute = async (signal: Signal) => {
    console.log("Executing signal:", signal)
    try {
        await apiClient.trading.execute({
            signals: [signal],
            strategy_id: "manual_execution",
            tickers: [signal.ticker]
        })
        fetchSignals()
    } catch (e) {
        console.error("Execution failed:", e)
    }
  }
  
  const handlePaperOrder = async () => {
      try {
          await apiClient.trading.paper.placeOrder({
              ticker: orderForm.ticker,
              action: orderForm.action as "BUY" | "SELL",
              shares: Number(orderForm.shares),
              price: Number(orderForm.price) > 0 ? Number(orderForm.price) : undefined
          })
          // Refresh
          fetchAccountInfo()
          fetchTradeHistory()
          // Reset form slightly
          setOrderForm({ ...orderForm, ticker: "" }) 
      } catch (e) {
          alert("下单失败: " + e)
      }
  }

  // ====== 重新设计的扫描逻辑 ======
  const handleScan = async () => {
    setScanning(true)
    setScanResults([])
    setScanMessage("")
    try {
      const selectorNames = scanStrategy === "all" ? undefined : [scanStrategy]
      const res = await apiClient.stz.run({
        trade_date: scanDate,
        mode: scanMode,
        selector_names: selectorNames,
      })
      if (res) {
        const rows = normalizeRows(res.data)
        setScanResults(rows)
        setScanMessage(res.message || `扫描完成，发现 ${res.count || rows.length} 个信号`)
      }
    } catch (e: any) {
      console.error("Scan failed:", e)
      setScanMessage(`扫描失败: ${e?.message || e}`)
    } finally {
      setScanning(false)
    }
  }

  const normalizeRows = (data: unknown): ScanResultRow[] => {
    if (!Array.isArray(data)) return []
    return data.filter((r: any) => r && r.ticker).map((r: any) => ({
      ticker: r.ticker || "",
      name: r.name || "",
      selector_alias: r.selector_alias || "",
      last_close: r.last_close ?? 0,
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">交易中心</h1>
        <p className="text-[13px] text-foreground/40">
          模拟交易账户、智能市场扫描与信号执行
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="paper" className="gap-2"><Wallet className="h-4 w-4"/> 模拟账户</TabsTrigger>
          <TabsTrigger value="scanner" className="gap-2"><Search className="h-4 w-4"/> 市场扫描</TabsTrigger>
          <TabsTrigger value="signals" className="gap-2"><Zap className="h-4 w-4"/> 信号池</TabsTrigger>
        </TabsList>

        {/* --- Tab: Paper Trading --- */}
        <TabsContent value="paper" className="space-y-6">
            {/* Account Summary */}
            <div className="grid gap-4 md:grid-cols-3">
                <GlassCard className="p-6">
                    <CardTitle className="text-sm font-medium text-muted-foreground">总资产</CardTitle>
                    <div className="text-2xl font-bold mt-2">
                        {account ? `¥${account.portfolio.total_assets.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "Loading..."}
                    </div>
                </GlassCard>
                <GlassCard className="p-6">
                    <CardTitle className="text-sm font-medium text-muted-foreground">可用资金</CardTitle>
                    <div className="text-2xl font-bold mt-2 text-emerald-500">
                        {account ? `¥${account.portfolio.cash.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "Loading..."}
                    </div>
                </GlassCard>
                <GlassCard className="p-6">
                    <CardTitle className="text-sm font-medium text-muted-foreground">持仓市值</CardTitle>
                    <div className="text-2xl font-bold mt-2 text-blue-500">
                        {account ? `¥${account.portfolio.market_value.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "Loading..."}
                    </div>
                </GlassCard>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
                {/* Positions Table */}
                <GlassCard className="md:col-span-2 p-0 overflow-hidden">
                    <div className="p-5 border-b border-black/[0.04] flex items-center justify-between">
                        <CardTitle className="flex items-center gap-1">
                            当前持仓
                            <HelpTooltip content="当前持有的所有头寸列表，包括持仓数量、成本价、当前市价和盈亏情况。" />
                        </CardTitle>
                        <Button size="sm" variant="ghost" onClick={fetchAccountInfo}><RefreshCw className="h-4 w-4"/></Button>
                    </div>
                    <div className="max-h-[400px] overflow-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>标的</TableHead>
                                    <TableHead className="text-right">数量</TableHead>
                                    <TableHead className="text-right">成本价</TableHead>
                                    <TableHead className="text-right">现价</TableHead>
                                    <TableHead className="text-right">市值</TableHead>
                                    <TableHead className="text-right">盈亏%</TableHead>
                                    <TableHead className="text-right">操作</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {positions.length === 0 ? (
                                    <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">暂无持仓</TableCell></TableRow>
                                ) : (
                                    positions.map((pos) => (
                                        <TableRow key={pos.ticker}>
                                            <TableCell className="font-medium">{pos.ticker}</TableCell>
                                            <TableCell className="text-right">{pos.shares}</TableCell>
                                            <TableCell className="text-right">{pos.avg_cost.toFixed(2)}</TableCell>
                                            <TableCell className="text-right">{pos.current_price?.toFixed(2) || "-"}</TableCell>
                                            <TableCell className="text-right">{pos.market_value?.toLocaleString() || "-"}</TableCell>
                                            <TableCell className={`text-right ${pos.return_pct && pos.return_pct > 0 ? "text-red-500" : "text-emerald-500"}`}>
                                                {pos.return_pct ? `${pos.return_pct > 0 ? "+" : ""}${pos.return_pct.toFixed(2)}%` : "-"}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button size="sm" variant="outline" className="h-7 text-xs" 
                                                    onClick={() => setOrderForm({...orderForm, ticker: pos.ticker, action: "SELL", shares: pos.shares})}
                                                >
                                                    卖出
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </div>
                </GlassCard>

                {/* Order Form */}
                <GlassCard className="p-6">
                    <CardTitle className="mb-4">快速下单</CardTitle>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label>代码</Label>
                            <Input placeholder="如 600000" value={orderForm.ticker} onChange={e => setOrderForm({...orderForm, ticker: e.target.value})} />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>方向</Label>
                                <Select value={orderForm.action} onValueChange={v => setOrderForm({...orderForm, action: v})}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="BUY">买入</SelectItem>
                                        <SelectItem value="SELL">卖出</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>数量</Label>
                                <Input type="number" value={orderForm.shares} onChange={e => setOrderForm({...orderForm, shares: Number(e.target.value)})} />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>价格 (留空=市价)</Label>
                            <Input type="number" placeholder="市价单留空" value={orderForm.price || ""} onChange={e => setOrderForm({...orderForm, price: Number(e.target.value)})} />
                        </div>
                        <Button className="w-full mt-2" onClick={handlePaperOrder}>
                            {orderForm.action === "BUY" ? "买入下单" : "卖出下单"}
                        </Button>
                    </div>
                </GlassCard>
            </div>
            
            {/* Trade History */}
            <GlassCard className="p-0 overflow-hidden">
                <div className="p-5 border-b border-black/[0.04]">
                    <CardTitle>交易记录</CardTitle>
                </div>
                <div className="max-h-[300px] overflow-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>时间</TableHead>
                                <TableHead>代码</TableHead>
                                <TableHead>方向</TableHead>
                                <TableHead className="text-right">价格</TableHead>
                                <TableHead className="text-right">数量</TableHead>
                                <TableHead className="text-right">费用</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {tradeHistory.length === 0 ? (
                                <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">暂无交易记录</TableCell></TableRow>
                            ) : (
                                tradeHistory.map((trade, i) => (
                                    <TableRow key={i}>
                                        <TableCell className="text-muted-foreground text-xs">{new Date(trade.trade_time).toLocaleString()}</TableCell>
                                        <TableCell>{trade.ticker}</TableCell>
                                        <TableCell>
                                            <span className={trade.action === "BUY" ? "text-red-500" : "text-emerald-500"}>{trade.action === "BUY" ? "买入" : "卖出"}</span>
                                        </TableCell>
                                        <TableCell className="text-right">{trade.price.toFixed(2)}</TableCell>
                                        <TableCell className="text-right">{trade.shares}</TableCell>
                                        <TableCell className="text-right text-xs text-muted-foreground">{trade.fee.toFixed(2)}</TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </GlassCard>
        </TabsContent>

        {/* ====== Tab: 市场扫描（重新设计） ====== */}
        <TabsContent value="scanner" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-4">
            {/* 扫描配置面板 */}
            <GlassCard className="md:col-span-1 h-fit space-y-5">
              <div className="space-y-1">
                <h3 className="font-semibold text-base flex items-center gap-2">
                  <Filter className="h-4 w-4 text-blue-500" />
                  扫描配置
                </h3>
                <p className="text-xs text-muted-foreground">选择扫描范围和策略</p>
              </div>

              {/* 扫描模式 */}
              <div className="space-y-2">
                <Label className="text-sm flex items-center gap-1">
                  扫描范围
                  <HelpTooltip content="资产池扫描：仅扫描您关注的资产（快速）；全市场扫描：扫描A股所有标的（耗时较长）。" />
                </Label>
                <Select value={scanMode} onValueChange={(v) => setScanMode(v as "universe" | "market")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="universe">
                      <span className="flex items-center gap-2">资产池扫描</span>
                    </SelectItem>
                    <SelectItem value="market">
                      <span className="flex items-center gap-2">全市场扫描 (A股)</span>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* 策略选择 */}
              <div className="space-y-2">
                <Label className="text-sm flex items-center gap-1">
                  选择策略
                  <HelpTooltip content="选择一个或全部策略进行扫描。策略列表来自量化战法配置，修改后全局生效。" />
                </Label>
                <Select value={scanStrategy} onValueChange={setScanStrategy}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      <span className="flex items-center gap-2">
                        <Layers className="h-3.5 w-3.5" />
                        全部激活策略
                      </span>
                    </SelectItem>
                    {activeStzStrategies.map(s => (
                      <SelectItem key={s.class_name} value={s.class_name}>
                        {s.alias}
                        <span className="text-muted-foreground ml-1 text-xs">({s.class_name})</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 扫描日期 */}
              <div className="space-y-2">
                <Label className="text-sm flex items-center gap-1">
                  交易日期
                  <HelpTooltip content="选择扫描的基准日期，通常为最近一个交易日。" />
                </Label>
                <Input 
                  type="date" 
                  value={scanDate}
                  onChange={(e) => setScanDate(e.target.value)}
                />
              </div>

              {/* 当前策略概览 */}
              <div className="rounded-lg bg-muted/30 p-3 space-y-2">
                <p className="text-xs font-medium text-muted-foreground">当前可用策略</p>
                <div className="flex flex-wrap gap-1.5">
                  {strategiesLoading ? (
                    <span className="text-xs text-muted-foreground">加载中...</span>
                  ) : (
                    activeStzStrategies.map(s => (
                      <Badge key={s.class_name} variant="secondary" className="text-xs">
                        {s.alias}
                      </Badge>
                    ))
                  )}
                </div>
              </div>

              {/* 扫描按钮 */}
              <Button className="w-full gap-2" onClick={handleScan} disabled={scanning}>
                {scanning ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    {scanMode === "market" ? "全市场扫描中..." : "扫描中..."}
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" />
                    开始扫描
                  </>
                )}
              </Button>
            </GlassCard>

            {/* 扫描结果面板 */}
            <div className="md:col-span-3 space-y-4">
              {scanMessage && (
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-blue-500" />
                  <span>{scanMessage}</span>
                </div>
              )}

              {scanResults.length > 0 ? (
                <GlassCard className="p-0 overflow-hidden">
                  <div className="p-4 border-b border-black/[0.04] flex items-center justify-between">
                    <CardTitle className="text-base">
                      扫描结果
                      <Badge variant="secondary" className="ml-2">{scanResults.length} 个标的</Badge>
                    </CardTitle>
                    <span className="text-xs text-muted-foreground">
                      {scanMode === "universe" ? "资产池" : "全市场"} · {scanStrategy === "all" ? "全部策略" : scanStrategy} · {scanDate}
                    </span>
                  </div>
                  <div className="max-h-[600px] overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>代码</TableHead>
                          <TableHead>名称</TableHead>
                          <TableHead>触发策略</TableHead>
                          <TableHead className="text-right">收盘价</TableHead>
                          <TableHead className="text-right">操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {scanResults.map((item, idx) => (
                          <TableRow key={`${item.ticker}-${idx}`}>
                            <TableCell className="font-medium font-mono">{item.ticker}</TableCell>
                            <TableCell>{item.name || "-"}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className="text-xs">{item.selector_alias}</Badge>
                            </TableCell>
                            <TableCell className="text-right">{Number(item.last_close).toFixed(2)}</TableCell>
                            <TableCell className="text-right">
                              <Button size="sm" variant="outline" className="h-7 text-xs"
                                onClick={() => {
                                  setActiveTab("paper")
                                  setOrderForm({ ...orderForm, ticker: item.ticker, action: "BUY" })
                                }}
                              >
                                去交易
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </GlassCard>
              ) : (
                <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-muted-foreground bg-muted/10 rounded-xl border border-dashed">
                  <Search className="h-12 w-12 mb-4 opacity-20" />
                  <p className="text-lg font-medium">准备扫描</p>
                  <p className="text-sm opacity-70 mt-1">
                    在左侧选择扫描范围和策略，然后点击"开始扫描"
                  </p>
                  <div className="flex gap-4 mt-6 text-xs">
                    <div className="flex items-center gap-1.5 bg-muted/30 px-3 py-1.5 rounded-full">
                      <div className="h-2 w-2 rounded-full bg-blue-500" />
                      资产池扫描: 快速筛选关注标的
                    </div>
                    <div className="flex items-center gap-1.5 bg-muted/30 px-3 py-1.5 rounded-full">
                      <div className="h-2 w-2 rounded-full bg-amber-500" />
                      全市场扫描: 全A股机会发掘
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* --- Tab: 信号池 --- */}
        <TabsContent value="signals">
             <div className="flex items-center justify-end mb-4 gap-2">
                <span className="text-sm text-muted-foreground">信号回溯周期:</span>
                <Select value={lookbackDays.toString()} onValueChange={(v) => setLookbackDays(parseInt(v))}>
                  <SelectTrigger className="w-[100px] h-9 bg-background/50 border-input">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7">7 天</SelectItem>
                    <SelectItem value="30">30 天</SelectItem>
                    <SelectItem value="90">90 天</SelectItem>
                    <SelectItem value="180">6 个月</SelectItem>
                  </SelectContent>
                </Select>
                <Button size="sm" variant="outline" className="gap-2" onClick={fetchSignals} disabled={loading}>
                  <Zap className="h-4 w-4" /> {loading ? "刷新中..." : "刷新信号"}
                </Button>
             </div>

             <GlassCard className="p-0 overflow-hidden">
                <div className="max-h-[600px] overflow-y-auto overflow-x-auto">
                    <Table className="min-w-[800px]">
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead>时间</TableHead>
                          <TableHead>标的</TableHead>
                          <TableHead>信号</TableHead>
                          <TableHead className="flex items-center">
                            {GLOSSARY.SignalConfidence.term}
                            <HelpTooltip content={GLOSSARY.SignalConfidence.definition} />
                          </TableHead>
                          <TableHead>
                            <div className="flex items-center">
                               {GLOSSARY.SignalStatus.term}
                               <HelpTooltip content={GLOSSARY.SignalStatus.definition} />
                            </div>
                          </TableHead>
                          <TableHead className="text-right">操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {signals.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                              当前时段暂无信号。
                            </TableCell>
                          </TableRow>
                        ) : (
                          signals.map((signal, i) => (
                            <TableRow key={i}>
                              <TableCell className="font-medium text-muted-foreground">
                                {new Date(signal.timestamp).toLocaleString()}
                              </TableCell>
                              <TableCell className="font-semibold">{signal.ticker}</TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <DirectionIcon direction={signal.direction} />
                                  <span className={signal.direction > 0 ? "text-red-500" : signal.direction < 0 ? "text-emerald-500" : "text-gray-500"}>
                                    {signal.signal}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className="w-24 bg-black/[0.05] dark:bg-white/[0.08] rounded-full h-1 overflow-hidden">
                                  <div 
                                    className="bg-foreground/30 h-full rounded-full transition-all" 
                                    style={{ width: `${signal.confidence * 100}%` }}
                                  />
                                </div>
                                <span className="text-xs text-muted-foreground mt-1 inline-block">
                                  {(signal.confidence * 100).toFixed(0)}%
                                </span>
                              </TableCell>
                              <TableCell>
                                <StatusBadge status={signal.status} />
                              </TableCell>
                              <TableCell className="text-right">
                                {signal.status === 'pending' && (
                                  <Button 
                                    size="sm" 
                                    className="h-7 text-xs bg-blue-600 hover:bg-blue-700 rounded-full"
                                    onClick={() => handleExecute(signal)}
                                  >
                                    执行
                                  </Button>
                                )}
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </div>
             </GlassCard>
        </TabsContent>
      </Tabs>
    </div>
  )
}
