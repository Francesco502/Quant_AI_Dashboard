"use client"

import { useState, useMemo } from "react"
import { GlassCard, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
  Bar
} from "recharts"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table"
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart2,
  Info
} from "lucide-react"
import { cn, formatPercent, formatCurrency } from "@/lib/utils"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"

// Design Constants
const COLORS = {
  equity: "#3B82F6",
  drawdown: "#4D7358",
  grid: "rgba(0, 0, 0, 0.04)",
  tooltipBg: "rgba(255, 255, 255, 0.94)",
  strategy1: "#3B82F6",
  strategy2: "#4D7358",
  strategy3: "#8B5CF6",
  strategy4: "#F59E0B",
  strategy5: "#B6453C"
}

const getStrategyColor = (index: number, strategyName: string) => {
  const colors = [COLORS.strategy1, COLORS.strategy2, COLORS.strategy3, COLORS.strategy4, COLORS.strategy5]
  // Use hash of name for consistent color
  let hash = 0
  for (let i = 0; i < strategyName.length; i++) {
    hash = ((hash << 5) - hash) + strategyName.charCodeAt(i)
    hash |= 0
  }
  return colors[Math.abs(hash) % colors.length]
}

interface StrategyResult {
  id: string
  name: string
  weight?: number
  metrics: {
    total_return: number
    annual_return?: number
    sharpe_ratio: number
    max_drawdown: number
    volatility: number
    information_ratio?: number
    beta?: number
    alpha?: number
  }
  equity_curve: Array<{ date: string; equity: number }>
  trades: Array<unknown>
}

interface ComparativeAnalysisPanelProps {
  results: Record<string, StrategyResult>
  className?: string
}

export default function ComparativeAnalysisPanel({
  results,
  className
}: ComparativeAnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<"all" | string>("all")
  const [chartType, setChartType] = useState<"equity" | "returns">("equity")

  // Filtered results
  const visibleResults = useMemo(() => {
    if (activeTab === "all") return results
    return Object.fromEntries(
      Object.entries(results).filter(([id]) => id === activeTab)
    )
  }, [results, activeTab])

  // Prepare comparison data for table
  const comparisonData = useMemo(() => {
    return Object.entries(results).map(([id, result]) => ({
      id,
      name: result.name,
      weight: result.weight,
      total_return: result.metrics.total_return,
      annual_return: result.metrics.annual_return || (Math.pow(1 + result.metrics.total_return, 252 / 252) - 1),
      sharpe: result.metrics.sharpe_ratio,
      max_drawdown: result.metrics.max_drawdown,
      volatility: result.metrics.volatility,
      information_ratio: result.metrics.information_ratio || 0,
      beta: result.metrics.beta || 1,
      alpha: result.metrics.alpha || 0,
      color: getStrategyColor(Object.keys(results).indexOf(id), result.name)
    }))
  }, [results])

  // Prepare combined equity curve data
  const combinedEquityData = useMemo(() => {
    if (!visibleResults || Object.keys(visibleResults).length === 0) return []

    // Get all unique dates
    const allDates = new Set<string>()
    Object.values(visibleResults).forEach(r => {
      r.equity_curve.forEach(point => allDates.add(point.date))
    })

    const sortedDates = Array.from(allDates).sort()

    return sortedDates.map(date => {
      const point: Record<string, string | number | null> = { date }
      Object.entries(visibleResults).forEach(([id, result]) => {
        const equityPoint = result.equity_curve.find(p => p.date === date)
        point[id] = equityPoint ? equityPoint.equity : null
      })
      return point
    })
  }, [visibleResults])

  // Prepare combined returns data
  const combinedReturnsData = useMemo(() => {
    if (!results || Object.keys(results).length === 0) return []

    return combinedEquityData.map((point, idx, all) => {
      const result: Record<string, string | number> = { date: String(point.date) }
      Object.entries(visibleResults).forEach(([id]) => {
        const current = point[id]
        const previous = idx > 0 ? all[idx - 1][id] : current
        if (typeof current === "number" && typeof previous === "number" && previous > 0) {
          result[id] = (current - previous) / previous
        } else {
          result[id] = 0
        }
      })
      return result
    })
  }, [combinedEquityData, visibleResults, results])

  // Best/Worst performers
  const bestPerformer = useMemo(() => {
    return comparisonData.reduce((best, curr) =>
      curr.total_return > best.total_return ? curr : best
    , comparisonData[0] || { name: "-", total_return: 0 })
  }, [comparisonData])

  const worstPerformer = useMemo(() => {
    return comparisonData.reduce((worst, curr) =>
      curr.max_drawdown > worst.max_drawdown ? worst : curr
    , comparisonData[0] || { name: "-", max_drawdown: 0 })
  }, [comparisonData])

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header with Tabs */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl font-semibold text-foreground">策略对比分析</h2>
          <p className="text-sm text-muted-foreground mt-1">
            多策略绩效对比与相对表现分析
          </p>
        </div>

        <div className="flex items-center gap-2 bg-muted/50 p-1 rounded-lg">
          <button
            onClick={() => setChartType("equity")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              chartType === "equity"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            权益曲线
          </button>
          <button
            onClick={() => setChartType("returns")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              chartType === "returns"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            收益率
          </button>
        </div>
      </div>

      {/* Quick Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-market-up" />
            <span className="text-xs font-medium text-muted-foreground">最佳收益</span>
          </div>
          <div className="text-lg font-bold text-market-up">
            {bestPerformer.name}
          </div>
          <div className="text-sm">
            {formatPercent(bestPerformer.total_return)}
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-4 h-4 text-market-down" />
            <span className="text-xs font-medium text-muted-foreground">最小回撤</span>
          </div>
          <div className="text-lg font-bold text-market-down">
            {worstPerformer.name}
          </div>
          <div className="text-sm">
            {formatPercent(worstPerformer.max_drawdown)}
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-blue-500" />
            <span className="text-xs font-medium text-muted-foreground">最高夏普</span>
          </div>
          <div className="text-lg font-bold text-blue-500">
            {comparisonData.reduce((best, curr) =>
              curr.sharpe > best.sharpe ? curr : best
            , comparisonData[0]).name}
          </div>
          <div className="text-sm">
            {comparisonData.reduce((best, curr) =>
              curr.sharpe > best.sharpe ? curr : best
            , comparisonData[0]).sharpe.toFixed(2)}
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <BarChart2 className="w-4 h-4 text-purple-500" />
            <span className="text-xs font-medium text-muted-foreground">策略数量</span>
          </div>
          <div className="text-lg font-bold text-purple-500">
            {Object.keys(results).length}
          </div>
          <div className="text-sm">活跃策略</div>
        </GlassCard>
      </div>

      {/* main Chart */}
      <GlassCard className="p-6 h-[400px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            <CardTitle className="flex items-center gap-1">
              {chartType === "equity" ? "权益曲线对比" : "收益率对比"}
              <HelpTooltip content={
                chartType === "equity"
                  ? "比较各策略的累计收益率"
                  : "比较各策略的分时收益率"
              } />
            </CardTitle>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveTab("all")}
              className={activeTab === "all" ? "bg-primary/10 text-primary border-primary" : ""}
            >
              全部
            </Button>
          </div>
        </div>

        {Object.keys(results).length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            {chartType === "equity" ? (
              <LineChart data={combinedEquityData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                <XAxis
                  dataKey="date"
                  stroke="#888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={50}
                />
                <YAxis
                  stroke="#888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(val) => `¥${(val/1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLES}
                  formatter={(val?: number) => [formatCurrency(Number(val ?? 0)), "权益"]}
                />
                <Legend />
                {Object.entries(visibleResults).map(([id, result], idx) => {
                  if (activeTab !== "all" && id !== activeTab) return null
                  return (
                    <Line
                      key={id}
                      type="monotone"
                      dataKey={id}
                      stroke={getStrategyColor(idx, result.name)}
                      strokeWidth={idx === 0 ? 2 : 1.5}
                      dot={false}
                      name={result.name}
                      connectNulls
                    />
                  )
                })}
              </LineChart>
            ) : (
              <BarChart data={combinedReturnsData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                <XAxis
                  dataKey="date"
                  stroke="#888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={30}
                />
                <YAxis
                  stroke="#888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(val) => `${(val * 100).toFixed(1)}%`}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLES}
                  formatter={(val?: number) => [`${(Number(val ?? 0) * 100).toFixed(2)}%`, "收益率"]}
                />
                <Legend />
                {Object.entries(visibleResults).map(([id, result], idx) => {
                  if (activeTab !== "all" && id !== activeTab) return null
                  return (
                    <Bar
                      key={id}
                      dataKey={id}
                      fill={getStrategyColor(idx, result.name)}
                      name={result.name}
                      opacity={0.7}
                    />
                  )
                })}
              </BarChart>
            )}
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground opacity-50">
            暂无数据，请运行回测
          </div>
        )}
      </GlassCard>

      {/* Metrics Comparison Table */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Table className="w-full text-sm">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[200px]">策略</TableHead>
                <TableHead className="text-right">权重</TableHead>
                <TableHead className="text-right">
                  总收益率
                  <HelpTooltip content={GLOSSARY.TotalReturn.definition} />
                </TableHead>
                <TableHead className="text-right">
                  年化收益
                  <HelpTooltip content="把当前区间收益折算到一年后的收益率口径。" />
                </TableHead>
                <TableHead className="text-right">
                  夏普比率
                  <HelpTooltip content={GLOSSARY.SharpeRatio.definition} />
                </TableHead>
                <TableHead className="text-right">
                  信息比率
                  <HelpTooltip content="信息比率 = 超额收益 / 跟踪误差，用于比较策略相对基准的稳定性。" />
                </TableHead>
                <TableHead className="text-right">
                  最大回撤
                  <HelpTooltip content={GLOSSARY.MaxDrawdown.definition} />
                </TableHead>
                <TableHead className="text-right">
                  波动率
                  <HelpTooltip content={GLOSSARY.Volatility.definition} />
                </TableHead>
                <TableHead className="text-right">Beta</TableHead>
                <TableHead className="text-right">Alpha</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comparisonData.map((row) => (
                <TableRow
                  key={row.id}
                  className="hover:bg-muted/20 cursor-pointer transition-colors"
                  onClick={() => setActiveTab(row.id)}
                >
                  <TableCell className="font-medium flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: row.color }}
                    />
                    {row.name}
                    {row.weight && (
                      <Badge variant="secondary" className="ml-auto text-xs">
                        {(row.weight * 100).toFixed(0)}%
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {row.weight ? (row.weight * 100).toFixed(1) + "%" : "-"}
                  </TableCell>
                  <TableCell className={`text-right font-bold ${row.total_return >= 0 ? "text-market-up" : "text-market-down"}`}>
                    {formatPercent(row.total_return)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatPercent(row.annual_return)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    <span className={cn(
                      row.sharpe > 1 ? "text-market-up" :
                      row.sharpe > 0 ? "text-blue-500" : "text-muted-foreground"
                    )}>
                      {row.sharpe.toFixed(2)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {row.information_ratio.toFixed(2)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-market-down">
                    {formatPercent(row.max_drawdown)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatPercent(row.volatility)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {row.beta.toFixed(2)}
                  </TableCell>
                  <TableCell className={`text-right font-mono ${row.alpha >= 0 ? "text-market-up" : "text-market-down"}`}>
                    {formatPercent(row.alpha)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {comparisonData.length === 0 && (
          <div className="py-8 text-center text-muted-foreground">
            暂无策略数据
          </div>
        )}
      </GlassCard>

      {/* Quick Insights */}
      {comparisonData.length > 1 && (
        <GlassCard className="p-6">
          <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
            <Info className="w-4 h-4 text-primary" />
            关键观察
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-muted/30 border border-muted/50">
              <div className="text-xs text-muted-foreground mb-1">收益分散度</div>
              <div className="text-sm font-medium">
                收益标准差: {Math.std(comparisonData.map(c => c.total_return)).toFixed(4)}
              </div>
            </div>
            <div className="p-4 rounded-lg bg-muted/30 border border-muted/50">
              <div className="text-xs text-muted-foreground mb-1">风险调整后收益</div>
              <div className="text-sm font-medium">
                平均夏普: {formatNumber(comparisonData.reduce((a, c) => a + c.sharpe, 0) / comparisonData.length)}
              </div>
            </div>
            <div className="p-4 rounded-lg bg-muted/30 border border-muted/50">
              <div className="text-xs text-muted-foreground mb-1">回撤相关性</div>
              <div className="text-sm font-medium">
                最大回撤标准差: {formatNumber(Math.std(comparisonData.map(c => c.max_drawdown)))}
              </div>
            </div>
          </div>
        </GlassCard>
      )}
    </div>
  )
}

// Helper functions (in a real app, these would be in utils)
function formatNumber(num: number, decimals: number = 2) {
  return num.toFixed(decimals)
}

// Add std function to Math if not exists
declare global {
  interface Math {
    std(values: number[]): number
  }
}
if (!Math.std) {
  Math.std = (values: number[]): number => {
    if (values.length === 0) return 0
    const avg = values.reduce((a, b) => a + b, 0) / values.length
    const squareDiffs = values.map(value => Math.pow(value - avg, 2))
    return Math.sqrt(squareDiffs.reduce((a, b) => a + b, 0) / values.length)
  }
}

const TOOLTIP_STYLES = {
  backgroundColor: "rgba(255, 255, 255, 0.94)",
  border: '1px solid rgba(0, 0, 0, 0.06)',
  borderRadius: '10px',
  backdropFilter: 'blur(20px)',
  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
  color: '#1A1A1A',
  fontSize: '12px',
}
