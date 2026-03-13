"use client"

import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { AlertTriangle, BarChart3, BookOpen, CheckCircle2, ChevronDown, ChevronUp, Star, Target, XCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { GlassCard, CardTitle } from "@/components/ui/card"

export type StrategyParameter = {
  name: string
  default: number | string
  range: string
  desc: string
}

export type StrategyDetail = {
  id: string
  name: string
  type: string
  difficulty: number
  description: string
  principle?: string
  formula?: string
  pros: string[]
  cons: string[]
  applicable: string[]
  risks: string[]
  parameters?: StrategyParameter[]
  examples?: string[]
}

export const STRATEGY_DETAILS: Record<string, StrategyDetail> = {
  "MACD Strategy": {
    id: "macd",
    name: "MACD Strategy",
    type: "Technical",
    difficulty: 2,
    description: "Uses MACD crossovers to detect trend transitions.",
    principle: "A bullish signal appears when DIF crosses above DEA; bearish when DIF crosses below DEA.",
    formula: "DIF = EMA(12) - EMA(26)\nDEA = EMA(DIF, 9)\nMACD = 2 * (DIF - DEA)",
    pros: ["Clear signal structure", "Works well in trending markets"],
    cons: ["Lagging by design", "Noisy in range-bound markets"],
    applicable: ["Trend following", "Swing trading"],
    risks: ["Whipsaw in sideways markets", "Late exits after reversals"],
    parameters: [
      { name: "Fast EMA", default: 12, range: "8-15", desc: "Fast EMA window" },
      { name: "Slow EMA", default: 26, range: "20-30", desc: "Slow EMA window" },
      { name: "Signal", default: 9, range: "7-12", desc: "Signal smoothing" },
    ],
  },
  "Bollinger Strategy": {
    id: "bollinger",
    name: "Bollinger Strategy",
    type: "Technical",
    difficulty: 3,
    description: "Combines channel touch and bandwidth signals for mean reversion or breakout setups.",
    principle: "Price near upper/lower bands indicates stretched conditions; shrinking bandwidth often precedes expansion.",
    formula: "Mid = MA(20)\nUpper = Mid + 2 * StdDev\nLower = Mid - 2 * StdDev",
    pros: ["Adapts to volatility", "Good visual risk framing"],
    cons: ["False breaks in chop", "Needs confirmation signals"],
    applicable: ["Range trading", "Volatility breakout setups"],
    risks: ["Trend continuation against mean reversion", "Frequent false entries"],
    parameters: [
      { name: "Window", default: 20, range: "10-30", desc: "Moving average window" },
      { name: "StdDev", default: 2, range: "1.5-3", desc: "Band width multiplier" },
    ],
  },
  "Momentum Strategy": {
    id: "momentum",
    name: "Momentum Strategy",
    type: "Factor",
    difficulty: 2,
    description: "Ranks assets by recent relative strength and follows winners.",
    principle: "Recent winners can continue to outperform for a period due to slow information diffusion.",
    formula: "Momentum = (P_t - P_t-n) / P_t-n",
    pros: ["Simple ranking workflow", "Strong empirical support"],
    cons: ["Momentum crashes", "High turnover cost"],
    applicable: ["Monthly rebalance", "Cross-sectional ranking"],
    risks: ["Style reversal", "Concentrated crowding"],
    parameters: [
      { name: "Lookback (months)", default: 6, range: "3-12", desc: "Momentum measurement period" },
      { name: "Selection (%)", default: 20, range: "10-30", desc: "Top percentile to hold" },
    ],
  },
}

interface StrategyLearningCardProps {
  strategyName?: string
  isExpanded?: boolean
  onToggle?: () => void
}

const DEFAULT_DETAIL: StrategyDetail = {
  id: "strategy",
  name: "Strategy",
  type: "General",
  difficulty: 3,
  description: "No detailed profile is available for this strategy yet.",
  pros: [],
  cons: [],
  applicable: [],
  risks: [],
  parameters: [],
  examples: [],
}

export function StrategyLearningCard({ strategyName, isExpanded = false, onToggle }: StrategyLearningCardProps) {
  const [expanded, setExpanded] = useState(isExpanded)

  const detail = useMemo<StrategyDetail>(() => {
    const fallbackName = Object.keys(STRATEGY_DETAILS)[0]
    const resolvedName = strategyName || fallbackName || DEFAULT_DETAIL.name
    const raw = STRATEGY_DETAILS[resolvedName]

    if (!raw) {
      return {
        ...DEFAULT_DETAIL,
        id: resolvedName.toLowerCase().replace(/\s+/g, "_"),
        name: resolvedName,
      }
    }

    return {
      ...DEFAULT_DETAIL,
      ...raw,
      pros: Array.isArray(raw.pros) ? raw.pros : [],
      cons: Array.isArray(raw.cons) ? raw.cons : [],
      applicable: Array.isArray(raw.applicable) ? raw.applicable : [],
      risks: Array.isArray(raw.risks) ? raw.risks : [],
      parameters: Array.isArray(raw.parameters) ? raw.parameters : [],
      examples: Array.isArray(raw.examples) ? raw.examples : [],
    }
  }, [strategyName])

  const isExpandedState = expanded || isExpanded

  const handleToggle = () => {
    if (!isExpanded) {
      setExpanded((prev) => !prev)
    }
    onToggle?.()
  }

  const difficultyStars = Array.from({ length: 5 }, (_, idx) => (
    <Star
      key={idx}
      className={`h-3 w-3 ${idx < detail.difficulty ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/40"}`}
    />
  ))

  return (
    <GlassCard className="p-0 overflow-hidden">
      <button
        type="button"
        onClick={handleToggle}
        className="w-full p-4 text-left hover:bg-muted/30 transition-colors"
        aria-expanded={isExpandedState}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle>{detail.name}</CardTitle>
              <Badge variant="secondary">{detail.type}</Badge>
            </div>
            <p className="text-sm text-muted-foreground">{detail.description}</p>
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground mr-1">Difficulty:</span>
              {difficultyStars}
            </div>
          </div>
          {isExpandedState ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>

      <AnimatePresence>
        {isExpandedState && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 pt-2 space-y-4 border-t border-border/60">
              {detail.principle && (
                <section className="space-y-2">
                  <h4 className="text-sm font-medium flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-blue-500" /> Principle
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">{detail.principle}</p>
                </section>
              )}

              {detail.formula && (
                <section className="space-y-2">
                  <h4 className="text-sm font-medium">Formula</h4>
                  <pre className="text-xs bg-muted/50 rounded-md p-3 whitespace-pre-wrap">{detail.formula}</pre>
                </section>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <section className="space-y-2">
                  <h4 className="text-sm font-medium flex items-center gap-2 text-green-600">
                    <CheckCircle2 className="h-4 w-4" /> Strengths
                  </h4>
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {(detail.pros.length ? detail.pros : ["No strengths documented yet."]).map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2"><span className="text-green-500">+</span>{item}</li>
                    ))}
                  </ul>
                </section>

                <section className="space-y-2">
                  <h4 className="text-sm font-medium flex items-center gap-2 text-red-600">
                    <XCircle className="h-4 w-4" /> Weaknesses
                  </h4>
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {(detail.cons.length ? detail.cons : ["No weaknesses documented yet."]).map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2"><span className="text-red-500">-</span>{item}</li>
                    ))}
                  </ul>
                </section>
              </div>

              <section className="space-y-2">
                <h4 className="text-sm font-medium flex items-center gap-2 text-blue-600">
                  <Target className="h-4 w-4" /> Suitable Market Context
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {(detail.applicable.length ? detail.applicable : ["Not specified"]).map((item, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">{item}</Badge>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <h4 className="text-sm font-medium flex items-center gap-2 text-orange-600">
                  <AlertTriangle className="h-4 w-4" /> Risk Notes
                </h4>
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {(detail.risks.length ? detail.risks : ["No risk notes documented yet."]).map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2"><span className="text-orange-500">!</span>{item}</li>
                  ))}
                </ul>
              </section>

              {detail.parameters && detail.parameters.length > 0 && (
                <section className="space-y-2">
                  <h4 className="text-sm font-medium flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-purple-500" /> Parameters
                  </h4>
                  <div className="space-y-2">
                    {detail.parameters.map((param) => (
                      <div key={param.name} className="text-xs bg-muted/40 rounded-md px-3 py-2 flex items-center justify-between gap-3">
                        <div>
                          <span className="font-medium">{param.name}</span>
                          <span className="text-muted-foreground ml-2">Default: {param.default}</span>
                        </div>
                        <span className="text-muted-foreground">Range: {param.range}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  )
}

interface StrategyComparisonProps {
  strategyNames: string[]
}

export function StrategyComparison({ strategyNames }: StrategyComparisonProps) {
  const strategies = strategyNames.map((name) => STRATEGY_DETAILS[name]).filter(Boolean)

  if (strategies.length < 2) {
    return (
      <GlassCard className="p-4">
        <p className="text-sm text-muted-foreground text-center">Select at least two strategies to compare.</p>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="p-4 overflow-x-auto">
      <h3 className="font-semibold mb-4">Strategy Comparison</h3>
      <table className="w-full text-sm min-w-[560px]">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 pr-3">Dimension</th>
            {strategies.map((s) => (
              <th key={s.id} className="text-left py-2 px-3">{s.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b">
            <td className="py-2 pr-3 font-medium">Type</td>
            {strategies.map((s) => (
              <td key={`${s.id}-type`} className="py-2 px-3"><Badge variant="secondary" className="text-xs">{s.type}</Badge></td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="py-2 pr-3 font-medium">Difficulty</td>
            {strategies.map((s) => (
              <td key={`${s.id}-difficulty`} className="py-2 px-3">{"★".repeat(Math.max(1, Math.min(5, s.difficulty)))}</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="py-2 pr-3 font-medium">Strength Count</td>
            {strategies.map((s) => (
              <td key={`${s.id}-pros`} className="py-2 px-3 text-green-600">{s.pros.length}</td>
            ))}
          </tr>
          <tr>
            <td className="py-2 pr-3 font-medium">Risk Level</td>
            {strategies.map((s) => {
              const level = s.risks.length > 3 ? "High" : s.risks.length > 1 ? "Medium" : "Low"
              const className = level === "High" ? "text-red-500" : level === "Medium" ? "text-orange-500" : "text-green-500"
              return (
                <td key={`${s.id}-risk`} className={`py-2 px-3 ${className}`}>{level}</td>
              )
            })}
          </tr>
        </tbody>
      </table>
    </GlassCard>
  )
}
