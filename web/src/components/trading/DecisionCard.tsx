"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api, type DecisionDashboardResult } from "@/lib/api"
import { ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Sparkles, AlertTriangle } from "lucide-react"

interface DecisionCardProps {
  ticker: string
  compact?: boolean
}

export function DecisionCard({ ticker, compact = false }: DecisionCardProps) {
  const [decision, setDecision] = useState<DecisionDashboardResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(!compact)

  useEffect(() => {
    if (!ticker) return

    const fetchDecision = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await api.portfolio.getDecision(ticker)
        if (res) setDecision(res)
      } catch (error) {
        const message = error instanceof Error ? error.message : "获取决策失败"
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    fetchDecision()
  }, [ticker])

  if (loading) {
    return (
      <GlassCard className="p-4">
        <div className="flex items-center justify-center py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="ml-2 text-sm text-muted-foreground">分析中...</span>
        </div>
      </GlassCard>
    )
  }

  if (error || !decision) {
    return (
      <GlassCard className="p-4">
        <div className="text-sm text-red-500 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error || "无法获取决策数据"}
        </div>
      </GlassCard>
    )
  }

  // 根据得分确定颜色
  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-red-500 bg-red-50 border-red-200"
    if (score >= 60) return "text-orange-500 bg-orange-50 border-orange-200"
    if (score >= 40) return "text-yellow-500 bg-yellow-50 border-yellow-200"
    if (score >= 20) return "text-blue-500 bg-blue-50 border-blue-200"
    return "text-gray-500 bg-gray-50 border-gray-200"
  }

  // 根据操作建议确定颜色
  const getActionColor = (action: string) => {
    if (action.includes("买入")) return "bg-red-500 hover:bg-red-600"
    if (action.includes("卖出")) return "bg-emerald-500 hover:bg-emerald-600"
    return "bg-gray-500 hover:bg-gray-600"
  }

  const scoreColorClass = getScoreColor(decision.score)
  const actionColorClass = getActionColor(decision.action)

  // 紧凑模式
  if (compact && !expanded) {
    return (
      <GlassCard className="p-3 cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setExpanded(true)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-medium font-mono">{ticker}</span>
            <Badge className={`${actionColorClass} text-white`}>
              {decision.action}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-sm font-bold ${scoreColorClass.split(" ")[0]}`}>
              {decision.score}分
            </span>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
      </GlassCard>
    )
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <GlassCard className="p-4 space-y-4">
          {/* 头部：代码、操作建议、得分 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold font-mono">{ticker}</span>
              <Badge className={`${actionColorClass} text-white text-sm px-3 py-1`}>
                {decision.action}
              </Badge>
            </div>
            <div className="flex items-center gap-3">
              <div className={`px-3 py-1 rounded-lg border ${scoreColorClass}`}>
                <span className="text-sm">得分: </span>
                <span className="text-lg font-bold">{decision.score}</span>
              </div>
              {compact && (
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => setExpanded(false)}>
                  <ChevronUp className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {/* 一句话结论 */}
          <div className="bg-muted/30 rounded-lg p-3">
            <p className="text-sm text-foreground/80">{decision.conclusion}</p>
          </div>

          {/* 买卖点位 */}
          {(decision.buy_price || decision.target_price) && (
            <div className="grid grid-cols-3 gap-3">
              {decision.buy_price && (
                <div className="text-center p-2 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                  <div className="text-xs text-red-600 dark:text-red-400">建议买入</div>
                  <div className="font-bold text-red-700 dark:text-red-300">¥{decision.buy_price.toFixed(2)}</div>
                </div>
              )}
              {decision.stop_loss && (
                <div className="text-center p-2 bg-gray-50 dark:bg-gray-900/20 rounded-lg border border-gray-200 dark:border-gray-800">
                  <div className="text-xs text-gray-600 dark:text-gray-400">止损位</div>
                  <div className="font-bold text-gray-700 dark:text-gray-300">¥{decision.stop_loss.toFixed(2)}</div>
                </div>
              )}
              {decision.target_price && (
                <div className="text-center p-2 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                  <div className="text-xs text-green-600 dark:text-green-400">目标价</div>
                  <div className="font-bold text-green-700 dark:text-green-300">¥{decision.target_price.toFixed(2)}</div>
                </div>
              )}
            </div>
          )}

          {/* 检查清单 */}
          {decision.checklist && decision.checklist.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-blue-500" />
                检查清单
              </h4>
              <div className="space-y-1">
                {decision.checklist.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm py-1 px-2 rounded hover:bg-muted/50">
                    <span className="text-muted-foreground">{item.condition}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-foreground/60">{item.value}</span>
                      <Badge variant={item.status === "满足" ? "default" : "secondary"} className="text-xs">
                        {item.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 亮点和风险 */}
          <div className="grid grid-cols-2 gap-3">
            {decision.highlights && decision.highlights.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium flex items-center gap-2 text-yellow-600">
                  <Sparkles className="h-4 w-4" />
                  亮点
                </h4>
                <ul className="space-y-1">
                  {decision.highlights.map((highlight, idx) => (
                    <li key={idx} className="text-xs text-foreground/70 flex items-start gap-1">
                      <span className="text-yellow-500 mt-0.5">•</span>
                      {highlight}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {decision.risks && decision.risks.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium flex items-center gap-2 text-orange-600">
                  <AlertTriangle className="h-4 w-4" />
                  风险提示
                </h4>
                <ul className="space-y-1">
                  {decision.risks.map((risk, idx) => (
                    <li key={idx} className="text-xs text-foreground/70 flex items-start gap-1">
                      <span className="text-orange-500 mt-0.5">•</span>
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </GlassCard>
      </motion.div>
    </AnimatePresence>
  )
}
