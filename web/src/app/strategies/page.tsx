"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, Layers3 } from "lucide-react"

import { api as apiClient } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useStrategies } from "@/lib/use-strategies"
import { StrategyLearningCard } from "@/components/trading/StrategyLearningCard"

type StrategyResultRow = {
  ticker: string
  name: string
  selector_alias: string
  last_close: number | string
}

type StrategyResult = {
  status: "success" | "error"
  message: string
  count?: number
  data?: StrategyResultRow[]
}

type HistoryEntry = {
  date: string
  file: string
  count: number
}

const normalizeRows = (payload: unknown): StrategyResultRow[] => {
  if (!Array.isArray(payload)) return []
  return payload
    .map((row) => {
      if (!row || typeof row !== "object") return null
      const rec = row as Record<string, unknown>
      const ticker = typeof rec.ticker === "string" ? rec.ticker : ""
      if (!ticker) return null
      return {
        ticker,
        name: typeof rec.name === "string" ? rec.name : "",
        selector_alias: typeof rec.selector_alias === "string" ? rec.selector_alias : "",
        last_close:
          typeof rec.last_close === "number" || typeof rec.last_close === "string"
            ? rec.last_close
            : 0,
      }
    })
    .filter((row): row is StrategyResultRow => row !== null)
}

const normalizeHistory = (payload: unknown): HistoryEntry[] => {
  if (!Array.isArray(payload)) return []
  return payload
    .map((item) => {
      if (!item || typeof item !== "object") return null
      const rec = item as Record<string, unknown>
      const date = typeof rec.date === "string" ? rec.date : ""
      const file = typeof rec.file === "string" ? rec.file : ""
      const count = typeof rec.count === "number" ? rec.count : 0
      if (!date) return null
      return { date, file, count }
    })
    .filter((row): row is HistoryEntry => row !== null)
}

export default function StrategiesPage() {
  const { active: activeStrategies, loading: strategiesLoading } = useStrategies()

  const [selectedStrategy, setSelectedStrategy] = useState<string>("all")
  const [tradeDate, setTradeDate] = useState<string>("")
  const [mode, setMode] = useState<"universe" | "market">("universe")
  const [running, setRunning] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [lastResult, setLastResult] = useState<StrategyResult | null>(null)

  const selectableStrategies = useMemo(
    () =>
      activeStrategies
        .filter((s) => !!s.class_name)
        .map((s) => ({
          value: s.class_name,
          label: s.alias || s.class_name,
          className: s.class_name,
        })),
    [activeStrategies]
  )

  const fetchHistory = useCallback(async () => {
    try {
      const records = await apiClient.stz.getHistory()
      setHistory(normalizeHistory(records))
    } catch (error) {
      console.error("Failed to load strategy history", error)
    }
  }, [])

  useEffect(() => {
    setTradeDate(new Date().toISOString().slice(0, 10))
    void fetchHistory()
  }, [fetchHistory])

  const runStrategy = async () => {
    if (!tradeDate) return
    setRunning(true)
    setLastResult(null)
    try {
      const selectorNames = selectedStrategy === "all" ? undefined : [selectedStrategy]
      const response = await apiClient.stz.run({
        trade_date: tradeDate,
        mode,
        selector_names: selectorNames,
      })
      const rows = normalizeRows((response as { data?: unknown }).data)
      setLastResult({
        status: "success",
        message: `本次共筛出 ${rows.length} 条结果`,
        count: rows.length,
        data: rows,
      })
      void fetchHistory()
    } catch (error) {
      console.error("Strategy run failed", error)
      setLastResult({
        status: "error",
        message: "运行失败，请检查日志或数据源状态。",
      })
    } finally {
      setRunning(false)
    }
  }

  const openHistory = async (date: string) => {
    setRunning(true)
    try {
      const detail = await apiClient.stz.getHistoryDetail(date)
      const rows = normalizeRows(detail)
      setLastResult({
        status: "success",
        message: `已载入 ${date} 的历史结果`,
        count: rows.length,
        data: rows,
      })
    } catch (error) {
      console.error("History detail load failed", error)
      setLastResult({
        status: "error",
        message: "读取历史记录失败。",
      })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="space-y-2">
        <Badge variant="outline" className="w-fit rounded-full px-3 py-1 text-xs">
          量化策略
        </Badge>
        <h1 className="text-3xl font-semibold tracking-[-0.03em] text-foreground/90">量化策略工作台</h1>
      </div>

      <Tabs defaultValue="run" className="space-y-4">
        <TabsList>
          <TabsTrigger value="run">执行策略</TabsTrigger>
          <TabsTrigger value="learn">策略教学</TabsTrigger>
          <TabsTrigger value="history">历史记录</TabsTrigger>
        </TabsList>

        <TabsContent value="run" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
            <GlassCard className="space-y-4 p-5">
              <div className="space-y-1">
                <CardTitle className="flex items-center gap-2">
                  <Layers3 className="h-4 w-4 text-primary" />
                  运行参数
                </CardTitle>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">交易日期</label>
                <Input type="date" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">运行范围</label>
                <Select value={mode} onValueChange={(value) => setMode(value as "universe" | "market")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="universe">资产池</SelectItem>
                    <SelectItem value="market">市场扫描</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">策略</label>
                <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部启用策略</SelectItem>
                    {selectableStrategies.map((strategy) => (
                      <SelectItem key={strategy.className} value={strategy.value}>
                        {strategy.label}
                        {strategy.label !== strategy.className ? ` (${strategy.className})` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button onClick={runStrategy} disabled={running || strategiesLoading || !tradeDate} className="w-full">
                {running ? "运行中..." : "运行策略"}
              </Button>
            </GlassCard>

            <div className="space-y-4">
              {lastResult ? (
                <GlassCard className="space-y-4 p-5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="space-y-1">
                      <CardTitle>运行结果</CardTitle>
                      <CardDescription>{lastResult.message}</CardDescription>
                    </div>
                    <Badge variant={lastResult.status === "success" ? "default" : "destructive"}>
                      {lastResult.status === "success" ? "成功" : "失败"}
                    </Badge>
                  </div>

                  {lastResult.data && lastResult.data.length > 0 ? (
                    <div className="overflow-hidden rounded-2xl border border-border/60">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>代码</TableHead>
                            <TableHead>名称</TableHead>
                            <TableHead>策略别名</TableHead>
                            <TableHead className="text-right">最新价</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {lastResult.data.map((row, index) => (
                            <TableRow key={`${row.ticker}-${index}`}>
                              <TableCell className="font-medium">{row.ticker}</TableCell>
                              <TableCell>{row.name || "-"}</TableCell>
                              <TableCell>{row.selector_alias || "-"}</TableCell>
                              <TableCell className="text-right">{Number(row.last_close).toFixed(2)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-2xl border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
                      <AlertCircle className="h-4 w-4" />
                      当前条件下没有命中结果。
                    </div>
                  )}
                </GlassCard>
              ) : (
                <GlassCard className="space-y-2 p-8 text-center text-muted-foreground">
                  <div className="text-base font-medium text-foreground/80">等待运行</div>
                  <p className="text-sm leading-6">选好参数后点击“运行策略”，结果会显示在这里。</p>
                </GlassCard>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="learn">
          <StrategyLearningCard strategyName={selectableStrategies[0]?.label} />
        </TabsContent>

        <TabsContent value="history">
          <GlassCard className="space-y-4 p-5">
            <div className="space-y-1">
              <CardTitle>历史记录</CardTitle>
              <CardDescription>查看以往运行结果，适合做复盘与对照。</CardDescription>
            </div>
            {history.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无历史记录。</div>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-border/60">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>文件</TableHead>
                      <TableHead className="text-right">条数</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.map((entry) => (
                      <TableRow key={`${entry.date}-${entry.file}`}>
                        <TableCell className="font-medium">{entry.date}</TableCell>
                        <TableCell className="text-muted-foreground">{entry.file}</TableCell>
                        <TableCell className="text-right">{entry.count}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => void openHistory(entry.date)}>
                            查看
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </GlassCard>
        </TabsContent>
      </Tabs>
    </div>
  )
}
