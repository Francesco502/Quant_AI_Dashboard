"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { api as apiClient } from "@/lib/api"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Layers, Play, Clock, FileText, AlertCircle, GraduationCap } from "lucide-react"
import { HelpTooltip } from "@/components/ui/tooltip"
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
    () => activeStrategies.filter((s) => !!s.class_name).map((s) => ({ name: s.alias || s.class_name, className: s.class_name })),
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
        message: `Generated ${rows.length} rows`,
        count: rows.length,
        data: rows,
      })
      void fetchHistory()
    } catch (error) {
      console.error("Strategy run failed", error)
      setLastResult({
        status: "error",
        message: "Run failed. Please check logs.",
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
        message: `Loaded history for ${date}`,
        count: rows.length,
        data: rows,
      })
    } catch (error) {
      console.error("History detail load failed", error)
      setLastResult({
        status: "error",
        message: "Failed to load selected history.",
      })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90 flex items-center gap-2">
            <Layers className="h-5 w-5" />
            Strategy Workbench
            <HelpTooltip content="Run market selectors and inspect historical runs." />
          </h1>
          <p className="text-sm text-muted-foreground">Manual strategy execution and result inspection.</p>
        </div>
      </div>

      <Tabs defaultValue="run" className="space-y-4">
        <TabsList>
          <TabsTrigger value="run" className="flex items-center gap-2">
            <Play className="h-4 w-4" />
            Run
          </TabsTrigger>
          <TabsTrigger value="learn" className="flex items-center gap-2">
            <GraduationCap className="h-4 w-4" />
            Learn
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="run" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-3">
            <GlassCard className="h-fit space-y-4 p-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Trade Date</label>
                <Input type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Mode</label>
                <Select value={mode} onValueChange={(value) => setMode(value as "universe" | "market")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="universe">Asset Pool</SelectItem>
                    <SelectItem value="market">Market Scan</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Strategy</label>
                <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Active Strategies</SelectItem>
                    {selectableStrategies.map((strategy) => (
                      <SelectItem key={strategy.name} value={strategy.name}>
                        {strategy.name} ({strategy.className})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button onClick={runStrategy} disabled={running || strategiesLoading || !tradeDate} className="w-full">
                {running ? "Running..." : "Run Strategy"}
              </Button>
            </GlassCard>

            <div className="md:col-span-2 space-y-4">
              {lastResult ? (
                <GlassCard className="p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold">Run Result</h3>
                      <Badge variant={lastResult.status === "success" ? "default" : "destructive"}>
                        {lastResult.status}
                      </Badge>
                    </div>
                    <span className="text-sm text-muted-foreground">{lastResult.message}</span>
                  </div>

                  {lastResult.data && lastResult.data.length > 0 ? (
                    <div className="rounded-md border overflow-hidden overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Ticker</TableHead>
                            <TableHead>Name</TableHead>
                            <TableHead>Selector</TableHead>
                            <TableHead className="text-right">Last Close</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {lastResult.data.map((row, index) => (
                            <TableRow key={`${row.ticker}-${index}`}>
                              <TableCell className="font-medium">{row.ticker}</TableCell>
                              <TableCell>{row.name}</TableCell>
                              <TableCell>{row.selector_alias}</TableCell>
                              <TableCell className="text-right">{Number(row.last_close).toFixed(2)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <AlertCircle className="h-4 w-4" />
                      No rows matched current settings.
                    </div>
                  )}
                </GlassCard>
              ) : (
                <GlassCard className="p-8 text-center text-muted-foreground">
                  Select parameters and run the strategy.
                </GlassCard>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="learn">
          <StrategyLearningCard />
        </TabsContent>

        <TabsContent value="history">
          <GlassCard className="p-4 space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <FileText className="h-4 w-4" />
              History
            </h3>
            {history.length === 0 ? (
              <div className="text-sm text-muted-foreground">No history available.</div>
            ) : (
              <div className="rounded-md border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>File</TableHead>
                      <TableHead className="text-right">Rows</TableHead>
                      <TableHead className="text-right">Action</TableHead>
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
                            View
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

