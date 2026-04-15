"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Slider } from "@/components/ui/slider"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Calculator,
  Target,
  TrendingUp,
  TrendingDown,
  Scale,
  PieChart,
  CheckCircle2,
  AlertCircle,
} from "lucide-react"
import { toast } from "sonner"

interface RebalanceItem {
  ticker: string
  name?: string
  currentShares: number
  currentPrice: number
  currentValue: number
  targetWeight: number
  targetValue: number
  suggestedShares: number
  action: "BUY" | "SELL" | "HOLD"
  sharesDiff: number
}

interface RebalancePlanProps {
  accountId: number
  totalAssets: number
  cash: number
  currentPositions: Array<{
    ticker: string
    shares: number
    current_price?: number
    market_value?: number
  }>
  selectedStocks?: Array<{
    ticker: string
    name?: string
    price: number
  }>
  onExecute?: (orders: Array<{ ticker: string; action: "BUY" | "SELL"; shares: number }>) => void
}

type AllocationStrategy = "equal" | "market_cap" | "custom" | "risk_parity"

export function RebalancePlan({
  accountId,
  totalAssets,
  cash,
  currentPositions,
  selectedStocks = [],
  onExecute,
}: RebalancePlanProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [strategy, setStrategy] = useState<AllocationStrategy>("equal")
  const [customWeights, setCustomWeights] = useState<Record<string, number>>({})
  const [rebalanceItems, setRebalanceItems] = useState<RebalanceItem[]>([])
  const [showPreview, setShowPreview] = useState(false)

  const allStocks = useMemo(() => {
    const stockMap = new Map<string, { ticker: string; name?: string; price: number }>()

    currentPositions.forEach((position) => {
      stockMap.set(position.ticker, {
        ticker: position.ticker,
        price: position.current_price || 0,
      })
    })

    selectedStocks.forEach((stock) => {
      stockMap.set(stock.ticker, stock)
    })

    return Array.from(stockMap.values())
  }, [currentPositions, selectedStocks])

  const calculateTargetWeights = (): Record<string, number> => {
    const stockCount = allStocks.length
    if (stockCount === 0) return {}

    switch (strategy) {
      case "equal": {
        const equalWeight = 1 / stockCount
        return allStocks.reduce((weights, stock) => {
          weights[stock.ticker] = equalWeight
          return weights
        }, {} as Record<string, number>)
      }
      case "custom":
        return customWeights
      case "risk_parity":
        return allStocks.reduce((weights, stock) => {
          weights[stock.ticker] = 1 / stockCount
          return weights
        }, {} as Record<string, number>)
      default:
        return {}
    }
  }

  const generatePlan = () => {
    const targetWeights = calculateTargetWeights()
    const investableCash = Math.min(cash, totalAssets * 0.95)

    const items: RebalanceItem[] = allStocks.map((stock) => {
      const currentPos = currentPositions.find((position) => position.ticker === stock.ticker)
      const currentShares = currentPos?.shares || 0
      const currentPrice = stock.price || currentPos?.current_price || 0
      const currentValue = currentShares * currentPrice
      const targetWeight = targetWeights[stock.ticker] || 0
      const targetValue = totalAssets * targetWeight
      const valueDiff = targetValue - currentValue
      const sharesDiff = currentPrice > 0 ? Math.round(valueDiff / currentPrice) : 0
      const suggestedShares = currentShares + sharesDiff

      let action: "BUY" | "SELL" | "HOLD" = "HOLD"
      if (sharesDiff > 0) action = "BUY"
      else if (sharesDiff < 0) action = "SELL"

      return {
        ticker: stock.ticker,
        name: stock.name,
        currentShares,
        currentPrice,
        currentValue,
        targetWeight,
        targetValue,
        suggestedShares,
        action,
        sharesDiff,
      }
    })

    const neededCash = items
      .filter((item) => item.action === "BUY")
      .reduce((sum, item) => sum + item.sharesDiff * item.currentPrice, 0)

    if (neededCash > investableCash) {
      const ratio = investableCash / neededCash
      items.forEach((item) => {
        if (item.action === "BUY") {
          item.sharesDiff = Math.floor(item.sharesDiff * ratio)
          item.suggestedShares = item.currentShares + item.sharesDiff
          item.targetValue = item.suggestedShares * item.currentPrice
          if (item.sharesDiff === 0) item.action = "HOLD"
        }
      })
    }

    setRebalanceItems(items)
    setShowPreview(true)
  }

  const previewSummary = useMemo(() => {
    if (rebalanceItems.length === 0) return null

    const totalBuyValue = rebalanceItems
      .filter((item) => item.action === "BUY")
      .reduce((sum, item) => sum + item.sharesDiff * item.currentPrice, 0)

    const totalSellValue = rebalanceItems
      .filter((item) => item.action === "SELL")
      .reduce((sum, item) => sum + Math.abs(item.sharesDiff) * item.currentPrice, 0)

    return {
      totalBuyValue,
      totalSellValue,
      netCashFlow: totalSellValue - totalBuyValue,
      buyCount: rebalanceItems.filter((item) => item.action === "BUY").length,
      sellCount: rebalanceItems.filter((item) => item.action === "SELL").length,
      holdCount: rebalanceItems.filter((item) => item.action === "HOLD").length,
    }
  }, [rebalanceItems])

  const handleExecute = () => {
    const orders = rebalanceItems
      .filter(
        (item): item is RebalanceItem & { action: "BUY" | "SELL" } =>
          item.action === "BUY" || item.action === "SELL",
      )
      .map((item) => ({
        ticker: item.ticker,
        action: item.action,
        shares: Math.abs(item.sharesDiff),
      }))

    if (orders.length === 0) {
      toast.error("没有需要执行的交易。")
      return
    }

    onExecute?.(orders)
    toast.success(`已生成 ${orders.length} 笔交易委托。`)
    setIsOpen(false)
    setShowPreview(false)
  }

  const handleWeightChange = (ticker: string, weight: number) => {
    setCustomWeights((prev) => ({
      ...prev,
      [ticker]: weight / 100,
    }))
  }

  const totalCustomWeight = useMemo(() => {
    return Object.values(customWeights).reduce((sum, weight) => sum + weight, 0)
  }, [customWeights])

  const summaryTone = previewSummary?.netCashFlow != null && previewSummary.netCashFlow < 0 ? "text-tone-positive" : "text-tone-negative"

  return (
    <>
      <Button variant="outline" className="gap-2" onClick={() => setIsOpen(true)}>
        <Scale className="h-4 w-4" />
        生成调仓计划
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              智能调仓计划
            </DialogTitle>
            <DialogDescription>
              根据目标权重自动计算买卖数量，帮助你更平稳地完成组合调整。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="data-panel-muted rounded-lg p-3">
                <div className="data-metric-label">总资产</div>
                <div className="mt-2 text-lg font-bold">¥{totalAssets.toLocaleString()}</div>
              </div>
              <div className="surface-tone-negative rounded-lg border p-3">
                <div className="data-metric-label">可用现金</div>
                <div className="mt-2 text-lg font-bold">¥{cash.toLocaleString()}</div>
              </div>
              <div className="data-panel-muted rounded-lg p-3">
                <div className="data-metric-label">涉及标的</div>
                <div className="mt-2 text-lg font-bold">{allStocks.length} 只</div>
              </div>
              <div className="data-panel-muted rounded-lg p-3">
                <div className="data-metric-label">账户 ID</div>
                <div className="mt-2 text-lg font-bold">{accountId}</div>
              </div>
            </div>

            <div className="space-y-3">
              <Label>目标权重分配方式</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setStrategy("equal")}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    strategy === "equal"
                      ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.08)]"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <PieChart className="h-4 w-4" />
                    <span className="font-medium">等权分配</span>
                  </div>
                  <p className="mt-1 text-xs text-foreground/68">
                    所有标的均分资金，每只约 {(allStocks.length > 0 ? 100 / allStocks.length : 0).toFixed(1)}%
                  </p>
                </button>

                <button
                  onClick={() => setStrategy("custom")}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    strategy === "custom"
                      ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.08)]"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4" />
                    <span className="font-medium">自定义权重</span>
                  </div>
                  <p className="mt-1 text-xs text-foreground/68">手动设置每只标的的目标权重。</p>
                </button>
              </div>
            </div>

            <AnimatePresence>
              {strategy === "custom" ? (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <Label>自定义目标权重</Label>
                    <Badge variant={Math.abs(totalCustomWeight - 1) < 0.01 ? "success" : "destructive"}>
                      合计：{(totalCustomWeight * 100).toFixed(1)}%
                    </Badge>
                  </div>
                  <div className="max-h-60 space-y-2 overflow-y-auto">
                    {allStocks.map((stock) => (
                      <div key={stock.ticker} className="flex items-center gap-3 rounded-lg bg-muted/30 p-2">
                        <span className="w-20 font-mono text-sm">{stock.ticker}</span>
                        <Slider
                          value={[(customWeights[stock.ticker] || 0) * 100]}
                          onValueChange={([value]) => handleWeightChange(stock.ticker, value)}
                          max={100}
                          step={1}
                          className="flex-1"
                        />
                        <Input
                          type="number"
                          value={((customWeights[stock.ticker] || 0) * 100).toFixed(0)}
                          onChange={(event) => handleWeightChange(stock.ticker, parseFloat(event.target.value) || 0)}
                          className="h-8 w-16 text-sm"
                        />
                        <span className="text-sm text-foreground/64">%</span>
                      </div>
                    ))}
                  </div>
                  {Math.abs(totalCustomWeight - 1) > 0.01 ? (
                    <p className="flex items-center gap-1 text-xs text-tone-positive">
                      <AlertCircle className="h-3 w-3" />
                      权重总和必须等于 100%。
                    </p>
                  ) : null}
                </motion.div>
              ) : null}
            </AnimatePresence>

            <Button
              className="w-full"
              onClick={generatePlan}
              disabled={allStocks.length === 0 || (strategy === "custom" && Math.abs(totalCustomWeight - 1) > 0.01)}
            >
              <Calculator className="mr-2 h-4 w-4" />
              生成调仓计划
            </Button>

            <AnimatePresence>
              {showPreview && rebalanceItems.length > 0 ? (
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-tone-negative" />
                    <h4 className="font-semibold">调仓方案预览</h4>
                  </div>

                  {previewSummary ? (
                    <div className="grid grid-cols-4 gap-3">
                      <div className="surface-tone-ochre rounded-lg border p-3">
                        <div className="data-metric-label">需买入</div>
                        <div className="mt-2 font-bold">¥{previewSummary.totalBuyValue.toLocaleString()}</div>
                        <div className="text-[0.84rem] text-foreground/70">{previewSummary.buyCount} 只</div>
                      </div>
                      <div className="surface-tone-celadon rounded-lg border p-3">
                        <div className="data-metric-label">需卖出</div>
                        <div className="mt-2 font-bold">¥{previewSummary.totalSellValue.toLocaleString()}</div>
                        <div className="text-[0.84rem] text-foreground/70">{previewSummary.sellCount} 只</div>
                      </div>
                      <div className="surface-tone-indigo rounded-lg border p-3">
                        <div className="data-metric-label">净现金流</div>
                        <div className={`mt-2 font-bold ${summaryTone}`}>¥{previewSummary.netCashFlow.toLocaleString()}</div>
                      </div>
                      <div className="data-panel-muted rounded-lg p-3">
                        <div className="data-metric-label">保持不变</div>
                        <div className="mt-2 font-bold">{previewSummary.holdCount} 只</div>
                      </div>
                    </div>
                  ) : null}

                  <div className="overflow-hidden rounded-lg border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>标的</TableHead>
                          <TableHead className="text-right">当前持仓</TableHead>
                          <TableHead className="text-right">目标权重</TableHead>
                          <TableHead className="text-right">建议操作</TableHead>
                          <TableHead className="text-right">变动数量</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {rebalanceItems.map((item) => (
                          <TableRow key={item.ticker}>
                            <TableCell>
                              <div className="font-mono font-medium">{item.ticker}</div>
                              {item.name ? <div className="text-[0.84rem] text-foreground/64">{item.name}</div> : null}
                            </TableCell>
                            <TableCell className="text-right">
                              <div>{item.currentShares} 股</div>
                               <div className="text-[0.84rem] text-foreground/64">¥{item.currentValue.toLocaleString()}</div>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="font-medium">{(item.targetWeight * 100).toFixed(1)}%</div>
                               <div className="text-[0.84rem] text-foreground/64">¥{item.targetValue.toLocaleString()}</div>
                            </TableCell>
                            <TableCell className="text-right">
                              {item.action === "BUY" ? (
                                <Badge className="surface-tone-positive border">
                                  <TrendingUp className="mr-1 h-3 w-3" />
                                  买入
                                </Badge>
                              ) : item.action === "SELL" ? (
                                <Badge className="surface-tone-negative border">
                                  <TrendingDown className="mr-1 h-3 w-3" />
                                  卖出
                                </Badge>
                              ) : (
                                <Badge variant="outline">持有</Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              {item.sharesDiff !== 0 ? (
                                <div className={`font-mono ${item.sharesDiff > 0 ? "text-tone-positive" : "text-tone-negative"}`}>
                                  {item.sharesDiff > 0 ? "+" : ""}
                                  {item.sharesDiff} 股
                                </div>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              取消
            </Button>
            {showPreview ? (
              <Button onClick={handleExecute}>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                确认执行调仓
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default RebalancePlan
