"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertCircle, CheckCircle2, ChevronDown, ChevronUp, ShieldAlert, Sparkles, Target, XCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { api, type DecisionDashboardResult } from "@/lib/api"

interface DecisionDashboardProps {
  ticker: string
  compact?: boolean
  showChart?: boolean
}

function scoreTone(score: number) {
  if (score >= 80) return "text-red-500"
  if (score >= 60) return "text-orange-500"
  if (score >= 40) return "text-yellow-500"
  if (score >= 20) return "text-blue-500"
  return "text-muted-foreground"
}

function actionBadgeClass(action: string) {
  if (action.includes("买")) return "bg-red-500 hover:bg-red-600"
  if (action.includes("卖")) return "bg-emerald-500 hover:bg-emerald-600"
  return "bg-slate-500 hover:bg-slate-600"
}

export function DecisionDashboard({ ticker, compact = false, showChart = true }: DecisionDashboardProps) {
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
        if (res) setDecision(res as DecisionDashboardResult)
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : "Failed to load decision"
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    void fetchDecision()
  }, [ticker])

  const checklist = useMemo(() => decision?.checklist ?? [], [decision])

  if (loading) {
    return (
      <GlassCard className="p-6">
        <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">Loading decision...</div>
      </GlassCard>
    )
  }

  if (error || !decision) {
    return (
      <GlassCard className="p-6">
        <div className="flex items-center gap-2 text-red-500">
          <AlertCircle className="h-4 w-4" />
          <span>{error || "No decision data available."}</span>
        </div>
      </GlassCard>
    )
  }

  if (compact && !expanded) {
    return (
      <GlassCard className="p-4">
        <button type="button" className="w-full text-left" onClick={() => setExpanded(true)}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">{ticker}</p>
              <p className="font-semibold line-clamp-1">{decision.conclusion}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-2xl font-bold ${scoreTone(decision.score)}`}>{decision.score}</span>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </div>
          </div>
        </button>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="p-6 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold">{ticker}</span>
            <Badge className={`text-white ${actionBadgeClass(decision.action)}`}>{decision.action}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{decision.conclusion}</p>
          <p className="text-xs text-muted-foreground">{new Date(decision.timestamp).toLocaleString("zh-CN")}</p>
        </div>

        <div className="text-right">
          <p className="text-xs text-muted-foreground">Score</p>
          <p className={`text-3xl font-bold ${scoreTone(decision.score)}`}>{decision.score}</p>
        </div>
      </div>

      {showChart && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Latest Price</div>
            <div className="text-lg font-semibold">{decision.latest_price ? `¥${decision.latest_price.toFixed(2)}` : "N/A"}</div>
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Buy Price</div>
            <div className="text-lg font-semibold">{decision.buy_price ? `¥${decision.buy_price.toFixed(2)}` : "N/A"}</div>
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Stop Loss</div>
            <div className="text-lg font-semibold">{decision.stop_loss ? `¥${decision.stop_loss.toFixed(2)}` : "N/A"}</div>
          </div>
        </div>
      )}

      {checklist.length > 0 && (
        <section className="space-y-2">
          <div className="text-sm font-medium flex items-center gap-2">
            <Target className="h-4 w-4" /> Checklist
          </div>
          <div className="space-y-2">
            {checklist.map((item, idx) => {
              const pass = item.status.includes("满足") || item.status.toLowerCase().includes("pass")
              return (
                <div key={`${item.condition}-${idx}`} className="rounded-md border px-3 py-2 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    {pass ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <XCircle className="h-4 w-4 text-muted-foreground" />}
                    <span>{item.condition}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">{item.value}</div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <section className="space-y-2">
          <div className="text-sm font-medium flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> Highlights
          </div>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {(decision.highlights.length ? decision.highlights : ["No highlights."]).map((item, idx) => (
              <li key={idx}>• {item}</li>
            ))}
          </ul>
        </section>

        <section className="space-y-2">
          <div className="text-sm font-medium flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" /> Risks
          </div>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {(decision.risks.length ? decision.risks : ["No risk notes."]).map((item, idx) => (
              <li key={idx}>• {item}</li>
            ))}
          </ul>
        </section>
      </div>

      {compact && (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={() => setExpanded(false)}>
            Collapse <ChevronUp className="ml-1 h-4 w-4" />
          </Button>
        </div>
      )}
    </GlassCard>
  )
}
