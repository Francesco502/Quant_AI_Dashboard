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
  AlertCircle
} from "lucide-react"
import { toast } from "sonner"

// 调仓计划接口
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

// 分配策略类型
type AllocationStrategy = "equal" | "market_cap" | "custom" | "risk_parity"

export function RebalancePlan({
  accountId,
  totalAssets,
  cash,
  currentPositions,
  selectedStocks = [],
  onExecute
}: RebalancePlanProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [strategy, setStrategy] = useState<AllocationStrategy>("equal")
  const [customWeights, setCustomWeights] = useState<Record<string, number>>({})
  const [rebalanceItems, setRebalanceItems] = useState<RebalanceItem[]>([])
  const [showPreview, setShowPreview] = useState(false)

  // 合并当前持仓和选股结果
  const allStocks = useMemo(() => {
    const stockMap = new Map<string, { ticker: string; name?: string; price: number }>()

    // 添加当前持仓
    currentPositions.forEach(pos => {
      stockMap.set(pos.ticker, {
        ticker: pos.ticker,
        price: pos.current_price || 0
      })
    })

    // 添加选股结果
    selectedStocks.forEach(stock => {
      stockMap.set(stock.ticker, stock)
    })

    return Array.from(stockMap.values())
  }, [currentPositions, selectedStocks])

  // 计算目标权重
  const calculateTargetWeights = (): Record<string, number> => {
    const stockCount = allStocks.length
    if (stockCount === 0) return {}

    switch (strategy) {
      case "equal":
        // 等权重分配
        const equalWeight = 1 / stockCount
        return allStocks.reduce((weights, stock) => {
          weights[stock.ticker] = equalWeight
          return weights
        }, {} as Record<string, number>)

      case "custom":
        // 自定义权重
        return customWeights

      case "risk_parity":
        // 风险平价（简化版：根据价格波动性反向分配）
        // 实际应用中应该计算历史波动率
        return allStocks.reduce((weights, stock) => {
          weights[stock.ticker] = 1 / stockCount
          return weights
        }, {} as Record<string, number>)

      default:
        return {}
    }
  }

  // 生成调仓计划
  const generatePlan = () => {
    const targetWeights = calculateTargetWeights()
    const totalValue = totalAssets
    const investableCash = Math.min(cash, totalValue * 0.95) // 保留5%现金

    const items: RebalanceItem[] = allStocks.map(stock => {
      const currentPos = currentPositions.find(p => p.ticker === stock.ticker)
      const currentShares = currentPos?.shares || 0
      const currentPrice = stock.price || currentPos?.current_price || 0
      const currentValue = currentShares * currentPrice
      const targetWeight = targetWeights[stock.ticker] || 0
      const targetValue = totalValue * targetWeight
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
        sharesDiff
      }
    })

    // 根据可用现金调整买入计划
    const neededCash = items
      .filter(i => i.action === "BUY")
      .reduce((sum, i) => sum + i.sharesDiff * i.currentPrice, 0)

    if (neededCash > investableCash) {
      // 按比例缩减买入
      const ratio = investableCash / neededCash
      items.forEach(item => {
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

  // 计算调仓后的预估状态
  const previewSummary = useMemo(() => {
    if (rebalanceItems.length === 0) return null

    const totalBuyValue = rebalanceItems
      .filter(i => i.action === "BUY")
      .reduce((sum, i) => sum + i.sharesDiff * i.currentPrice, 0)

    const totalSellValue = rebalanceItems
      .filter(i => i.action === "SELL")
      .reduce((sum, i) => sum + Math.abs(i.sharesDiff) * i.currentPrice, 0)

    const buyCount = rebalanceItems.filter(i => i.action === "BUY").length
    const sellCount = rebalanceItems.filter(i => i.action === "SELL").length
    const holdCount = rebalanceItems.filter(i => i.action === "HOLD").length

    return {
      totalBuyValue,
      totalSellValue,
      netCashFlow: totalSellValue - totalBuyValue,
      buyCount,
      sellCount,
      holdCount
    }
  }, [rebalanceItems])

  // 执行调仓
  const handleExecute = () => {
    const orders = rebalanceItems
      .filter((item): item is RebalanceItem & { action: "BUY" | "SELL" } => item.action === "BUY" || item.action === "SELL")
      .map(item => ({
        ticker: item.ticker,
        action: item.action,
        shares: Math.abs(item.sharesDiff)
      }))

    if (orders.length === 0) {
      toast.error("没有需要执行的交易")
      return
    }

    onExecute?.(orders)
    toast.success(`已生成 ${orders.length} 笔交易订单`)
    setIsOpen(false)
    setShowPreview(false)
  }

  // 更新自定义权重
  const handleWeightChange = (ticker: string, weight: number) => {
    setCustomWeights(prev => ({
      ...prev,
      [ticker]: weight / 100
    }))
  }

  // 权重总和检查
  const totalCustomWeight = useMemo(() => {
    return Object.values(customWeights).reduce((sum, w) => sum + w, 0)
  }, [customWeights])

  return (
    <>
      <Button
        variant="outline"
        className="gap-2"
        onClick={() => setIsOpen(true)}
      >
        <Scale className="w-4 h-4" />
        生成调仓计划
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Calculator className="w-5 h-5" />
              智能调仓计划
            </DialogTitle>
            <DialogDescription>
              根据目标权重自动计算买卖数量，优化投资组合配置
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* 账户概览 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="text-xs text-muted-foreground">总资产</div>
                <div className="text-lg font-bold">¥{totalAssets.toLocaleString()}</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="text-xs text-muted-foreground">可用现金</div>
                <div className="text-lg font-bold text-emerald-600">
                  ¥{cash.toLocaleString()}
                </div>
              </div>
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="text-xs text-muted-foreground">涉及标的</div>
                <div className="text-lg font-bold">{allStocks.length} 只</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="text-xs text-muted-foreground">账户ID</div>
                <div className="text-lg font-bold">{accountId}</div>
              </div>
            </div>

            {/* 分配策略选择 */}
            <div className="space-y-3">
              <Label>目标权重分配策略</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setStrategy("equal")}
                  className={`p-3 rounded-lg border text-left transition-colors ${
                    strategy === "equal"
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <PieChart className="w-4 h-4" />
                    <span className="font-medium">等权重分配</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    所有标的均分资金，每只 {(100 / allStocks.length).toFixed(1)}%
                  </p>
                </button>

                <button
                  onClick={() => setStrategy("custom")}
                  className={`p-3 rounded-lg border text-left transition-colors ${
                    strategy === "custom"
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    <span className="font-medium">自定义权重</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    手动设置每只标的的目标权重
                  </p>
                </button>
              </div>
            </div>

            {/* 自定义权重设置 */}
            <AnimatePresence>
              {strategy === "custom" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <Label>自定义目标权重</Label>
                    <Badge variant={Math.abs(totalCustomWeight - 1) < 0.01 ? "default" : "destructive"}>
                      总计: {(totalCustomWeight * 100).toFixed(1)}%
                    </Badge>
                  </div>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {allStocks.map(stock => (
                      <div key={stock.ticker} className="flex items-center gap-3 p-2 bg-muted/30 rounded-lg">
                        <span className="font-mono text-sm w-20">{stock.ticker}</span>
                        <Slider
                          value={[(customWeights[stock.ticker] || 0) * 100]}
                          onValueChange={([v]) => handleWeightChange(stock.ticker, v)}
                          max={100}
                          step={1}
                          className="flex-1"
                        />
                        <Input
                          type="number"
                          value={((customWeights[stock.ticker] || 0) * 100).toFixed(0)}
                          onChange={(e) => handleWeightChange(stock.ticker, parseFloat(e.target.value) || 0)}
                          className="w-16 h-8 text-sm"
                        />
                        <span className="text-sm text-muted-foreground">%</span>
                      </div>
                    ))}
                  </div>
                  {Math.abs(totalCustomWeight - 1) > 0.01 && (
                    <p className="text-xs text-red-500 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      权重总和必须等于 100%
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* 生成按钮 */}
            <Button
              className="w-full"
              onClick={generatePlan}
              disabled={allStocks.length === 0 || (strategy === "custom" && Math.abs(totalCustomWeight - 1) > 0.01)}
            >
              <Calculator className="w-4 h-4 mr-2" />
              生成调仓计划
            </Button>

            {/* 调仓预览 */}
            <AnimatePresence>
              {showPreview && rebalanceItems.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-green-500" />
                    <h4 className="font-semibold">调仓方案预览</h4>
                  </div>

                  {/* 汇总信息 */}
                  {previewSummary && (
                    <div className="grid grid-cols-4 gap-3">
                      <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 border border-red-200 dark:border-red-800">
                        <div className="text-xs text-red-600">需买入</div>
                        <div className="font-bold text-red-700">
                          ¥{previewSummary.totalBuyValue.toLocaleString()}
                        </div>
                        <div className="text-xs text-red-500">{previewSummary.buyCount} 只</div>
                      </div>
                      <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-3 border border-emerald-200 dark:border-emerald-800">
                        <div className="text-xs text-emerald-600">需卖出</div>
                        <div className="font-bold text-emerald-700">
                          ¥{previewSummary.totalSellValue.toLocaleString()}
                        </div>
                        <div className="text-xs text-emerald-500">{previewSummary.sellCount} 只</div>
                      </div>
                      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 border border-blue-200 dark:border-blue-800">
                        <div className="text-xs text-blue-600">净现金流</div>
                        <div className={`font-bold ${previewSummary.netCashFlow >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                          ¥{previewSummary.netCashFlow.toLocaleString()}
                        </div>
                      </div>
                      <div className="bg-gray-50 dark:bg-gray-900/20 rounded-lg p-3 border border-gray-200 dark:border-gray-800">
                        <div className="text-xs text-gray-600">保持不变</div>
                        <div className="font-bold text-gray-700">{previewSummary.holdCount} 只</div>
                      </div>
                    </div>
                  )}

                  {/* 详细调仓表 */}
                  <div className="border rounded-lg overflow-hidden">
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
                        {rebalanceItems.map(item => (
                          <TableRow key={item.ticker}>
                            <TableCell>
                              <div className="font-mono font-medium">{item.ticker}</div>
                              {item.name && <div className="text-xs text-muted-foreground">{item.name}</div>}
                            </TableCell>
                            <TableCell className="text-right">
                              <div>{item.currentShares} 股</div>
                              <div className="text-xs text-muted-foreground">
                                ¥{item.currentValue.toLocaleString()}
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="font-medium">{(item.targetWeight * 100).toFixed(1)}%</div>
                              <div className="text-xs text-muted-foreground">
                                ¥{item.targetValue.toLocaleString()}
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              {item.action === "BUY" ? (
                                <Badge className="bg-red-500 hover:bg-red-600">
                                  <TrendingUp className="w-3 h-3 mr-1" />
                                  买入
                                </Badge>
                              ) : item.action === "SELL" ? (
                                <Badge className="bg-emerald-500 hover:bg-emerald-600">
                                  <TrendingDown className="w-3 h-3 mr-1" />
                                  卖出
                                </Badge>
                              ) : (
                                <Badge variant="secondary">持有</Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              {item.sharesDiff !== 0 && (
                                <div className={`font-mono ${item.sharesDiff > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                                  {item.sharesDiff > 0 ? '+' : ''}{item.sharesDiff} 股
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              取消
            </Button>
            {showPreview && (
              <Button onClick={handleExecute}>
                <CheckCircle2 className="w-4 h-4 mr-2" />
                确认执行调仓
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default RebalancePlan
