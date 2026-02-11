"use client"

import { useState, useEffect } from "react"
import { api as apiClient, SelectorConfig, HistoryRecord } from "@/lib/api"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Layers, Play, Clock, FileText, AlertCircle } from "lucide-react"
import { HelpTooltip } from "@/components/ui/tooltip"
import { useStrategies } from "@/lib/use-strategies"

type StrategyResultRow = {
  ticker: string
  name: string
  selector_alias: string
  last_close: number | string
}

type StrategyResult = {
  status: string
  count?: number
  data?: StrategyResultRow[]
  message: string
}

const normalizeStrategyRows = (data: unknown): StrategyResultRow[] => {
  if (!Array.isArray(data)) return []
  return data
    .map((row) => {
      if (!row || typeof row !== "object") {
        return {
          ticker: "",
          name: "",
          selector_alias: "",
          last_close: 0,
        }
      }
      const record = row as Record<string, unknown>
      return {
        ticker: typeof record.ticker === "string" ? record.ticker : "",
        name: typeof record.name === "string" ? record.name : "",
        selector_alias: typeof record.selector_alias === "string" ? record.selector_alias : "",
        last_close:
          typeof record.last_close === "number" || typeof record.last_close === "string"
            ? record.last_close
            : 0,
      }
    })
    .filter((row) => row.ticker.length > 0)
}

export default function StrategiesPage() {
  // 使用统一策略 Hook（与交易中心、回测共享同一策略源）
  const { strategies, active: activeStrategies, loading: strategiesLoading, refresh: refreshStrategies } = useStrategies()
  const [running, setRunning] = useState(false)
  
  // 运行参数
  const [selectedStrategy, setSelectedStrategy] = useState<string>("all")
  const [tradeDate, setTradeDate] = useState<string>("")
  const [mode, setMode] = useState<"universe" | "market">("universe")
  
  // 结果状态
  const [lastResult, setLastResult] = useState<StrategyResult | null>(null)
  
  // 历史记录
  const [history, setHistory] = useState<HistoryRecord[]>([])

  const fetchHistory = async () => {
    try {
      const res = await apiClient.stz.getHistory()
      if (res) {
        setHistory(res)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    setTradeDate(new Date().toISOString().split('T')[0])
    fetchHistory()
  }, [])

  const handleRun = async () => {
    setRunning(true)
    setLastResult(null)
    try {
      const selectorNames = selectedStrategy === "all" ? undefined : [selectedStrategy]
      const res = await apiClient.stz.run({
        trade_date: tradeDate,
        mode: mode,
        selector_names: selectorNames
      })
      const rows = normalizeStrategyRows(res.data)
      setLastResult({ ...res, data: rows })
      // 刷新历史
      fetchHistory()
    } catch (e) {
      console.error(e)
      setLastResult({ status: "error", message: "运行失败，请查看控制台日志" })
    } finally {
      setRunning(false)
    }
  }

  const loadHistoryDetail = async (date: string) => {
    setRunning(true) // 复用 loading 状态
    try {
      const data = await apiClient.stz.getHistoryDetail(date)
      const rows = normalizeStrategyRows(data)
      setLastResult({
        status: "success",
        count: rows.length,
        data: rows,
        message: `加载历史记录: ${date}`
      })
    } catch (e) {
      console.error(e)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90 flex items-center gap-2">
            量化战法
            <HelpTooltip content="基于Z哥战法体系的量化选股工具，支持全市场扫描与资产池评估。" />
          </h1>
          <p className="text-muted-foreground">
            配置并运行您的选股策略，或查看历史回测结果。
          </p>
        </div>
      </div>

      <Tabs defaultValue="run" className="space-y-4">
        <TabsList>
          <TabsTrigger value="run" className="flex items-center gap-2">
            <Play className="h-4 w-4" /> 运行策略
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <Clock className="h-4 w-4" /> 历史记录
          </TabsTrigger>
        </TabsList>

        <TabsContent value="run" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-3">
            {/* 配置面板 */}
            <GlassCard className="h-fit space-y-6">
              <div className="space-y-2">
                <h3 className="font-semibold text-lg flex items-center gap-2">
                  <Layers className="h-4 w-4 text-blue-500" />
                  策略配置
                </h3>
                <p className="text-xs text-muted-foreground">设置运行参数以开始选股。</p>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    交易日期
                    <HelpTooltip content="选择回测或选股的基准日期（通常为最近一个交易日）。" />
                  </label>
                  <Input 
                    type="date" 
                    value={tradeDate}
                    onChange={(e) => setTradeDate(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    运行模式
                    <HelpTooltip content="资产池：仅扫描您关注的资产；全市场：扫描A股所有标的（耗时较长）。" />
                  </label>
                  <Select value={mode} onValueChange={(v) => setMode(v as "universe" | "market")}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="universe">资产池评估</SelectItem>
                      <SelectItem value="market">全市场扫描</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    选择战法
                    <HelpTooltip content="选择特定的战法进行运算，或选择'所有战法'一次性运行全部。策略列表来自统一配置，修改后全局生效。" />
                  </label>
                  <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">所有激活战法</SelectItem>
                      {activeStrategies.map(s => (
                        <SelectItem key={s.class_name} value={s.class_name}>
                          {s.alias} ({s.class_name})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {strategiesLoading && (
                    <p className="text-xs text-muted-foreground">策略加载中...</p>
                  )}
                </div>

                <Button className="w-full gap-2" onClick={handleRun} disabled={running}>
                  {running ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      运行中...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-current" /> 开始运行
                    </>
                  )}
                </Button>
              </div>
            </GlassCard>

            {/* 结果面板 */}
            <div className="md:col-span-2 space-y-6">
              {lastResult ? (
                <GlassCard>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-lg flex items-center gap-2">
                      运行结果
                      {lastResult.status === "success" ? (
                        <Badge variant="default" className="bg-green-500/10 text-green-500">成功</Badge>
                      ) : (
                        <Badge variant="destructive">失败</Badge>
                      )}
                    </h3>
                    <span className="text-sm text-muted-foreground">{lastResult.message}</span>
                  </div>

                  {lastResult.data && lastResult.data.length > 0 ? (
                    <div className="rounded-md border overflow-hidden overflow-x-auto">
                      <Table className="min-w-[500px]">
                        <TableHeader>
                          <TableRow>
                            <TableHead>代码</TableHead>
                            <TableHead>名称</TableHead>
                            <TableHead>战法</TableHead>
                            <TableHead>收盘价</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {lastResult.data.map((row, idx) => (
                            <TableRow key={idx}>
                              <TableCell className="font-medium">{row.ticker}</TableCell>
                              <TableCell>{row.name}</TableCell>
                              <TableCell>
                                <Badge variant="outline">{row.selector_alias}</Badge>
                              </TableCell>
                              <TableCell>{Number(row.last_close).toFixed(2)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground bg-muted/20 rounded-lg border border-dashed">
                      <AlertCircle className="h-8 w-8 mb-2 opacity-50" />
                      <p>未找到符合条件的标的</p>
                    </div>
                  )}
                </GlassCard>
              ) : (
                <div className="flex flex-col items-center justify-center h-full py-24 text-muted-foreground bg-muted/10 rounded-xl border border-dashed">
                  <Layers className="h-12 w-12 mb-4 opacity-20" />
                  <p className="text-lg font-medium">准备就绪</p>
                  <p className="text-sm opacity-70">请在左侧配置参数并点击“开始运行”</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="history">
          <GlassCard>
            <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Clock className="h-4 w-4" /> 历史选股记录
            </h3>
            
            <div className="rounded-md border overflow-x-auto">
              <Table className="min-w-[600px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>日期</TableHead>
                    <TableHead>文件名</TableHead>
                    <TableHead>信号数量</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                        暂无历史记录
                      </TableCell>
                    </TableRow>
                  ) : (
                    history.map((record) => (
                      <TableRow key={record.file}>
                        <TableCell className="font-medium">{record.date}</TableCell>
                        <TableCell className="text-muted-foreground font-mono text-xs">{record.file}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{record.count} 条信号</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => {
                            // 切换到运行结果页并加载数据
                            const tabTrigger = document.querySelector('[value="run"]') as HTMLElement
                            if (tabTrigger) tabTrigger.click()
                            loadHistoryDetail(record.date)
                          }}>
                            <FileText className="h-4 w-4 mr-1" /> 查看详情
                          </Button>
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
