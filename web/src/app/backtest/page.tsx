"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { GlassCard, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from "recharts"
import { Play, RotateCcw, Settings2, TrendingUp, AlertTriangle, Layers } from "lucide-react"
import { cn, formatPercent, formatCurrency } from "@/lib/utils"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"

// Design System Constants
const COLORS = {
  equity: "#3B82F6",
  drawdown: "#DC2626",
  grid: "rgba(0, 0, 0, 0.04)",
  tooltipBg: "rgba(255, 255, 255, 0.94)"
}

const tooltipStyle = {
  backgroundColor: COLORS.tooltipBg,
  border: '1px solid rgba(0, 0, 0, 0.06)',
  borderRadius: '10px',
  backdropFilter: 'blur(20px)',
  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
  color: '#1A1A1A',
  fontSize: '12px',
}

// 统一策略类型
interface UnifiedStrategy {
  id: string
  name: string
  description: string
  category: "classic" | "stz"
  default_params: Record<string, any>
  class_name: string
  alias: string
  activate: boolean
}

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<UnifiedStrategy[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState<string>("")
  const [tickers, setTickers] = useState<string>("013281,002611,160615")
  const [startDate, setStartDate] = useState<string>("2024-01-01")
  const [endDate, setEndDate] = useState<string>("")
  const [initialCapital, setInitialCapital] = useState<string>("100000")
  const [params, setParams] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  // --- 从统一端点获取策略列表 ---
  useEffect(() => {
    api.backtest.listStrategies().then((res: any[]) => {
      setStrategies(res || [])
      if (res && res.length > 0) {
        setSelectedStrategy(res[0].id)
        setParams(res[0].default_params || {})
      }
    }).catch(e => console.error("Failed to load strategies:", e))
  }, [])

  const handleStrategyChange = (id: string) => {
    setSelectedStrategy(id)
    const strat = strategies.find(s => s.id === id)
    if (strat) {
      setParams(strat.default_params || {})
    }
  }

  const handleParamChange = (key: string, value: string) => {
    setParams((prev: any) => ({ ...prev, [key]: value }))
  }

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    try {
      const strat = strategies.find(s => s.id === selectedStrategy)

      if (strat && strat.category === "stz") {
        // STZ 策略 → 使用 /stz/run 接口
        const tickerList = tickers.split(",").map(t => t.trim()).filter(Boolean)
        const res = await api.stz.run({
          trade_date: endDate || new Date().toISOString().split('T')[0],
          mode: "universe",
          selector_names: [strat.class_name],
          selector_params: { [strat.class_name]: params },
          tickers: tickerList.length > 0 ? tickerList : undefined
        })
        // 将 STZ 结果适配为回测结果格式
        setResult({
          metrics: {
            total_return: 0,
            sharpe_ratio: 0,
            max_drawdown: 0,
            volatility: 0,
          },
          equity_curve: [],
          trades: [],
          // 额外字段用于展示选股结果
          stz_result: res,
        })
      } else {
        // 经典策略 → 使用 /backtest/run 接口
        const tickerList = tickers.split(",").map(t => t.trim()).filter(Boolean)
        const res = await api.backtest.run({
          strategy_id: selectedStrategy,
          tickers: tickerList,
          start_date: startDate,
          end_date: endDate || undefined,
          initial_capital: parseFloat(initialCapital),
          params: params
        })
        setResult(res)
      }
    } catch (e: any) {
      console.error("Backtest failed", e)
      alert("回测失败: " + (e?.message || "请检查参数或数据"))
    } finally {
      setLoading(false)
    }
  }

  const currentStrategy = strategies.find(s => s.id === selectedStrategy)
  const isSTZ = currentStrategy?.category === "stz"

  // 将 STZ 策略和经典策略分组
  const classicStrategies = strategies.filter(s => s.category === "classic")
  const stzStrategies = strategies.filter(s => s.category === "stz")

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">
            历史回测
          </h1>
          <p className="text-[13px] text-foreground/40">
            基于历史数据验证策略表现，支持经典量化策略与Z哥战法。
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Configuration Panel */}
        <GlassCard className="lg:col-span-1 p-6 space-y-6 h-fit">
          <div className="flex items-center gap-2 mb-2">
            <Settings2 className="w-5 h-5 text-primary" />
            <CardTitle>回测配置</CardTitle>
          </div>

          <div className="space-y-4">
            {/* 策略选择 - 分组 */}
            <div className="space-y-2">
              <Label className="flex items-center gap-1">
                选择策略
                <HelpTooltip content="经典策略支持完整回测（权益曲线+交易记录）；Z哥战法用于选股信号回验。" />
              </Label>
              <Select value={selectedStrategy} onValueChange={handleStrategyChange}>
                <SelectTrigger>
                  <SelectValue placeholder="选择策略" />
                </SelectTrigger>
                <SelectContent>
                  {classicStrategies.length > 0 && (
                    <>
                      <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground bg-muted/50">
                        经典量化策略
                      </div>
                      {classicStrategies.map(s => (
                        <SelectItem key={s.id} value={s.id}>
                          <span className="flex items-center gap-2">
                            {s.name}
                          </span>
                        </SelectItem>
                      ))}
                    </>
                  )}
                  {stzStrategies.length > 0 && (
                    <>
                      <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground bg-muted/50 mt-1">
                        Z哥战法
                      </div>
                      {stzStrategies.map(s => (
                        <SelectItem key={s.id} value={s.id}>
                          <span className="flex items-center gap-2">
                            {s.alias}
                            <span className="text-muted-foreground text-xs">({s.class_name})</span>
                          </span>
                        </SelectItem>
                      ))}
                    </>
                  )}
                </SelectContent>
              </Select>
              {currentStrategy && (
                <div className="flex items-start gap-1.5 mt-1">
                  <Badge
                    variant={isSTZ ? "default" : "secondary"}
                    className="text-xs shrink-0"
                  >
                    {isSTZ ? "Z哥战法" : "经典策略"}
                  </Badge>
                  <p className="flex-1 min-w-0 text-xs text-muted-foreground whitespace-normal break-words">
                    {currentStrategy.description}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>标的 (逗号分隔)</Label>
              <Input value={tickers} onChange={e => setTickers(e.target.value)} placeholder="如 013281,002611" />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <Label>开始日期</Label>
                <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>{isSTZ ? "交易日期" : "结束日期"}</Label>
                <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
              </div>
            </div>

            {!isSTZ && (
              <div className="space-y-2">
                <Label>初始资金</Label>
                <Input type="number" value={initialCapital} onChange={e => setInitialCapital(e.target.value)} />
              </div>
            )}

            {/* Dynamic Params */}
            {currentStrategy && Object.keys(params).length > 0 && (
              <div className="pt-4 border-t border-black/[0.04] space-y-4">
                <Label className="text-[11px] font-medium uppercase tracking-wider text-foreground/40">
                  策略参数
                </Label>
                {Object.entries(params).map(([key, val]) => {
                  // 跳过嵌套对象参数的直接展示
                  if (typeof val === "object" && val !== null) return null
                  return (
                    <div key={key} className="space-y-1">
                      <Label className="text-xs font-mono">{key}</Label>
                      <Input 
                        value={String(val ?? "")} 
                        onChange={e => handleParamChange(key, e.target.value)} 
                        className="h-8"
                      />
                    </div>
                  )
                })}
              </div>
            )}

            <Button 
              className="w-full mt-4" 
              onClick={handleRun} 
              disabled={loading}
            >
              {loading ? (
                <motion.div 
                  animate={{ rotate: 360 }} 
                  transition={{ repeat: Infinity, duration: 1 }}
                  className="mr-2"
                >
                  <RotateCcw className="w-4 h-4" />
                </motion.div>
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              {isSTZ ? "运行选股" : "开始回测"}
            </Button>
          </div>
        </GlassCard>

        {/* Results Panel */}
        <div className="lg:col-span-3 space-y-6">
          {/* STZ 选股结果 */}
          {result?.stz_result && (
            <GlassCard className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="w-5 h-5 text-blue-500" />
                <CardTitle>选股结果</CardTitle>
                <Badge variant="secondary">{result.stz_result.count || 0} 个信号</Badge>
              </div>
              {result.stz_result.data && Array.isArray(result.stz_result.data) && result.stz_result.data.length > 0 ? (
                <div className="rounded-md border overflow-hidden overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-black/[0.04] text-foreground/40 text-[12px] uppercase tracking-wider bg-muted/30">
                        <th className="py-2 px-3 text-left">代码</th>
                        <th className="py-2 px-3 text-left">名称</th>
                        <th className="py-2 px-3 text-left">触发战法</th>
                        <th className="py-2 px-3 text-right">收盘价</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.stz_result.data.map((row: any, idx: number) => (
                        <tr key={idx} className="border-b border-black/[0.03] hover:bg-muted/20">
                          <td className="py-2 px-3 font-mono font-medium">{row.ticker}</td>
                          <td className="py-2 px-3">{row.name || "-"}</td>
                          <td className="py-2 px-3">
                            <Badge variant="outline" className="text-xs">{row.selector_alias}</Badge>
                          </td>
                          <td className="py-2 px-3 text-right">{Number(row.last_close).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-12 text-center text-muted-foreground bg-muted/20 rounded-lg border border-dashed">
                  未找到符合条件的标的
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-3">{result.stz_result.message}</p>
            </GlassCard>
          )}

          {/* 经典回测指标 */}
          {!result?.stz_result && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    总收益率
                    <HelpTooltip content={GLOSSARY.TotalReturn.definition} />
                  </span>
                  <span className={cn("text-2xl font-bold", (result?.metrics?.total_return || 0) >= 0 ? "text-emerald-500" : "text-red-500")}>
                    {result ? formatPercent(result.metrics.total_return) : "---"}
                  </span>
                </GlassCard>
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    夏普比率
                    <HelpTooltip content={GLOSSARY.SharpeRatio.definition} />
                  </span>
                  <span className="text-2xl font-bold">
                    {result ? result.metrics.sharpe_ratio.toFixed(2) : "---"}
                  </span>
                </GlassCard>
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    最大回撤
                    <HelpTooltip content={GLOSSARY.MaxDrawdown.definition} />
                  </span>
                  <span className="text-2xl font-bold text-red-500">
                    {result ? formatPercent(result.metrics.max_drawdown) : "---"}
                  </span>
                </GlassCard>
                <GlassCard className="p-4 flex flex-col justify-center">
                  <span className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                    波动率
                    <HelpTooltip content={GLOSSARY.Volatility.definition} />
                  </span>
                  <span className="text-2xl font-bold">
                    {result ? formatPercent(result.metrics.volatility) : "---"}
                  </span>
                </GlassCard>
              </div>

              {/* Chart */}
              <GlassCard className="p-6 h-[400px]">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="w-5 h-5 text-primary" />
                  <CardTitle className="flex items-center gap-1">
                    权益曲线
                    <HelpTooltip content={GLOSSARY.EquityCurve.definition} />
                  </CardTitle>
                </div>
                {result && result.equity_curve && result.equity_curve.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={result.equity_curve}>
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
                        domain={['auto', 'auto']} 
                        stroke="#888" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false}
                        tickFormatter={(val) => `¥${(val/1000).toFixed(0)}k`}
                      />
                      <Tooltip 
                        contentStyle={tooltipStyle}
                        formatter={(val: any) => [formatCurrency(val), "权益"]}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="equity" 
                        stroke={COLORS.equity} 
                        strokeWidth={2} 
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground opacity-50">
                    暂无数据，请运行回测
                  </div>
                )}
              </GlassCard>

              {/* Trades Table */}
              <GlassCard className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="w-5 h-5 text-primary" />
                  <CardTitle>交易记录 ({result?.trades?.length || 0})</CardTitle>
                </div>
                <div className="max-h-[300px] overflow-auto">
                  <table className="w-full text-[13px] text-left">
                    <thead className="sticky top-0 glass-dropdown z-10">
                      <tr className="border-b border-black/[0.04] text-foreground/40 text-[12px] uppercase tracking-wider">
                        <th className="py-2">时间</th>
                        <th className="py-2">代码</th>
                        <th className="py-2">方向</th>
                        <th className="py-2 text-right">价格</th>
                        <th className="py-2 text-right">数量</th>
                        <th className="py-2 text-right">手续费</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result?.trades?.map((t: any, i: number) => (
                        <tr key={i} className="border-b border-black/[0.03] hover:bg-black/[0.02] transition-colors duration-150">
                          <td className="py-2 font-mono text-xs">{new Date(t.timestamp).toLocaleDateString()}</td>
                          <td className="py-2 font-bold">{t.symbol}</td>
                          <td className={cn("py-2 font-bold", t.side === "BUY" ? "text-red-500" : "text-emerald-500")}>
                            {t.side === "BUY" ? "买入" : "卖出"}
                          </td>
                          <td className="py-2 text-right font-mono">{t.price.toFixed(2)}</td>
                          <td className="py-2 text-right font-mono">{t.quantity}</td>
                          <td className="py-2 text-right font-mono text-muted-foreground">{t.commission.toFixed(2)}</td>
                        </tr>
                      ))}
                      {!result?.trades?.length && !result?.stz_result && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground">无交易记录</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </>
          )}

          {/* 空状态 */}
          {!result && (
            <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground bg-muted/10 rounded-xl border border-dashed">
              <TrendingUp className="h-12 w-12 mb-4 opacity-20" />
              <p className="text-lg font-medium">准备就绪</p>
              <p className="text-sm opacity-70">选择策略并配置参数，然后点击运行</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
