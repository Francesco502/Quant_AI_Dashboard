"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api, type DecisionDashboardResult } from "@/lib/api"
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  AlertTriangle,
} from "lucide-react"

interface DecisionCardProps {
  ticker: string
  compact?: boolean
}

function getScoreTone(score: number) {
  if (score >= 80) return "surface-tone-positive text-tone-positive"
  if (score >= 60) return "surface-tone-ochre text-tone-ochre"
  if (score >= 40) return "surface-tone-indigo text-tone-indigo"
  return "surface-tone-ink text-tone-ink"
}

function getActionTone(action: string) {
  if (action.includes("买入")) return "surface-tone-positive text-tone-positive"
  if (action.includes("卖出")) return "surface-tone-negative text-tone-negative"
  return "surface-tone-ink text-tone-ink"
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
      } catch (requestError) {
        const message = requestError instanceof Error ? requestError.message : "获取决策失败。"
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    void fetchDecision()
  }, [ticker])

  if (loading) {
    return (
      <GlassCard className="p-4">
        <div className="flex items-center justify-center py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="ml-2 text-sm text-foreground/68">分析中…</span>
        </div>
      </GlassCard>
    )
  }

  if (error || !decision) {
    return (
      <GlassCard className="p-4">
        <div className="flex items-center gap-2 text-sm text-tone-positive">
          <AlertCircle className="h-4 w-4" />
          {error || "无法获取决策数据。"}
        </div>
      </GlassCard>
    )
  }

  const scoreToneClass = getScoreTone(decision.score)
  const actionToneClass = getActionTone(decision.action)

  if (compact && !expanded) {
    return (
      <GlassCard
        className="cursor-pointer p-3 transition-[background-color,border-color] hover:bg-muted/50"
        onClick={() => setExpanded(true)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-medium font-mono">{ticker}</span>
            <Badge className={`${actionToneClass} border`}>{decision.action}</Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-sm font-bold ${scoreToneClass.split(" ")[1]}`}>{decision.score} 分</span>
            <ChevronDown className="h-4 w-4 text-foreground/56" />
          </div>
        </div>
      </GlassCard>
    )
  }

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <GlassCard className="space-y-4 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold font-mono">{ticker}</span>
              <Badge className={`${actionToneClass} border px-3 py-1 text-sm`}>{decision.action}</Badge>
            </div>
            <div className="flex items-center gap-3">
              <div className={`rounded-lg border px-3 py-1 ${scoreToneClass}`}>
                <span className="text-sm">评分 </span>
                <span className="text-lg font-bold">{decision.score}</span>
              </div>
              {compact ? (
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => setExpanded(false)}>
                  <ChevronUp className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg bg-muted/30 p-3">
            <p className="text-sm text-foreground/82">{decision.conclusion}</p>
          </div>

          {(decision.buy_price || decision.target_price) ? (
            <div className="grid grid-cols-3 gap-3">
              {decision.buy_price ? (
                <div className="surface-tone-ochre rounded-lg border p-2.5 text-center">
                  <div className="text-[0.84rem] text-foreground/72">参考买点</div>
                  <div className="font-bold">¥{decision.buy_price.toFixed(2)}</div>
                </div>
              ) : null}
              {decision.stop_loss ? (
                <div className="surface-tone-ink rounded-lg border p-2.5 text-center">
                  <div className="text-[0.84rem] text-foreground/72">止损位</div>
                  <div className="font-bold">¥{decision.stop_loss.toFixed(2)}</div>
                </div>
              ) : null}
              {decision.target_price ? (
                <div className="surface-tone-indigo rounded-lg border p-2.5 text-center">
                  <div className="text-[0.84rem] text-foreground/72">目标价</div>
                  <div className="font-bold">¥{decision.target_price.toFixed(2)}</div>
                </div>
              ) : null}
            </div>
          ) : null}

          {decision.checklist && decision.checklist.length > 0 ? (
            <div className="space-y-2">
              <h4 className="flex items-center gap-2 text-sm font-medium">
                <CheckCircle2 className="h-4 w-4 text-tone-indigo" />
                检查清单
              </h4>
              <div className="space-y-1">
                {decision.checklist.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded px-2 py-1 text-sm hover:bg-muted/40"
                  >
                    <span className="text-foreground/70">{item.condition}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[0.84rem] text-foreground/66">{item.value}</span>
                      <Badge
                        variant={item.status === "满足" ? "success" : "outline"}
                        className="text-[0.78rem]"
                      >
                        {item.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            {decision.highlights && decision.highlights.length > 0 ? (
              <div className="space-y-2">
                <h4 className="flex items-center gap-2 text-sm font-medium text-tone-ochre">
                  <Sparkles className="h-4 w-4" />
                  亮点
                </h4>
                <ul className="space-y-1">
                  {decision.highlights.map((highlight, idx) => (
                    <li key={idx} className="flex items-start gap-1 text-[0.88rem] leading-7 text-foreground/76">
                      <span className="mt-0.5 text-tone-ochre">•</span>
                      {highlight}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {decision.risks && decision.risks.length > 0 ? (
              <div className="space-y-2">
                <h4 className="flex items-center gap-2 text-sm font-medium text-tone-positive">
                  <AlertTriangle className="h-4 w-4" />
                  风险提示
                </h4>
                <ul className="space-y-1">
                  {decision.risks.map((risk, idx) => (
                    <li key={idx} className="flex items-start gap-1 text-[0.88rem] leading-7 text-foreground/76">
                      <span className="mt-0.5 text-tone-cinnabar">•</span>
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </GlassCard>
      </motion.div>
    </AnimatePresence>
  )
}
