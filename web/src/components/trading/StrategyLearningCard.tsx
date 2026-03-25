"use client"

import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { AlertTriangle, BarChart3, BookOpen, CheckCircle2, ChevronDown, ChevronUp, Star, Target, XCircle } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { CardTitle, GlassCard } from "@/components/ui/card"

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
}

export const STRATEGY_DETAILS: Record<string, StrategyDetail> = {
  "SMA 金叉策略": {
    id: "sma_cross",
    name: "SMA 金叉策略",
    type: "趋势跟随",
    difficulty: 2,
    description: "短期均线上穿长期均线时买入，下穿时卖出，适合用来跟踪中期趋势。",
    principle: "通过短中期均线的相对位置判断趋势方向，趋势形成后顺势持有。",
    formula: "当 SMA(short) > SMA(long) 时偏多；当 SMA(short) < SMA(long) 时偏空。",
    pros: ["逻辑直观，适合新手理解", "趋势明确时胜率较稳定"],
    cons: ["震荡市容易来回打脸", "存在信号滞后"],
    applicable: ["趋势行情", "中期波段"],
    risks: ["横盘区间频繁假信号", "趋势末端入场可能回撤较大"],
    parameters: [
      { name: "short_window", default: 10, range: "5-20", desc: "短期均线窗口" },
      { name: "long_window", default: 30, range: "20-60", desc: "长期均线窗口" },
    ],
  },
  "MACD Strategy": {
    id: "macd",
    name: "MACD 策略",
    type: "趋势动量",
    difficulty: 2,
    description: "借助 DIF 与 DEA 的交叉识别趋势切换，适合做趋势确认。",
    principle: "DIF 上穿 DEA 视为转强，下穿 DEA 视为转弱；柱体用于衡量动能变化。",
    formula: "DIF = EMA(12) - EMA(26)\nDEA = EMA(DIF, 9)\nMACD = 2 × (DIF - DEA)",
    pros: ["对趋势切换较敏感", "适合与均线、量能配合"],
    cons: ["震荡市噪音较多", "转折点往往并非最早出现"],
    applicable: ["趋势跟随", "波段确认"],
    risks: ["横盘磨损", "信号确认后再入场会有延迟"],
    parameters: [
      { name: "快线周期", default: 12, range: "8-15", desc: "更短会更敏感" },
      { name: "慢线周期", default: 26, range: "20-35", desc: "更长会更稳健" },
      { name: "信号周期", default: 9, range: "6-12", desc: "用于平滑 DIF" },
    ],
  },
  "Bollinger Strategy": {
    id: "bollinger",
    name: "布林带策略",
    type: "波动率",
    difficulty: 3,
    description: "观察价格相对通道的位置，适合做均值回归或波动收敛后的突破。",
    principle: "价格偏离中轨过多时关注回归，带宽收窄后则留意趋势扩张。",
    formula: "中轨 = MA(20)\n上轨 = 中轨 + 2×标准差\n下轨 = 中轨 - 2×标准差",
    pros: ["能同时观察趋势和波动", "图形可视化非常直观"],
    cons: ["单独使用容易误判假突破", "对不同市场要调参数"],
    applicable: ["区间震荡", "波动率收敛后的突破行情"],
    risks: ["单边趋势中逆势接飞刀", "带宽扩张时回归判断失效"],
    parameters: [
      { name: "窗口", default: 20, range: "10-30", desc: "均线与波动率计算窗口" },
      { name: "标准差倍数", default: 2, range: "1.5-3", desc: "通道宽度倍数" },
    ],
  },
  "Momentum Strategy": {
    id: "momentum",
    name: "动量策略",
    type: "因子轮动",
    difficulty: 2,
    description: "比较一段时间内谁涨得更强，优先持有相对强势的资产。",
    principle: "强者恒强的现象会在一定时间内持续，因此用过去表现筛选未来候选。",
    formula: "动量 = (当前价格 - n 日前价格) / n 日前价格",
    pros: ["适合做多资产筛选", "参数含义简单清晰"],
    cons: ["风格反转时回撤可能很快", "换手率通常较高"],
    applicable: ["轮动配置", "中短期排序"],
    risks: ["追涨回撤", "拥挤交易导致的动量崩塌"],
    parameters: [
      { name: "回看周期", default: 20, range: "10-120", desc: "衡量强弱的历史长度" },
      { name: "持有数量", default: 5, range: "1-20", desc: "入选组合的标的数量" },
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
  name: "策略说明",
  type: "通用",
  difficulty: 2,
  description: "当前策略还没有单独整理说明，页面会展示通用解读框架。",
  pros: [],
  cons: [],
  applicable: [],
  risks: [],
  parameters: [],
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
    }
  }, [strategyName])

  const isExpandedState = expanded || isExpanded

  const handleToggle = () => {
    if (!isExpanded) {
      setExpanded((prev) => !prev)
    }
    onToggle?.()
  }

  return (
    <GlassCard className="overflow-hidden p-0">
      <button
        type="button"
        onClick={handleToggle}
        className="w-full p-5 text-left transition-colors hover:bg-muted/20"
        aria-expanded={isExpandedState}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle>{detail.name}</CardTitle>
              <Badge variant="secondary">{detail.type}</Badge>
            </div>
            <p className="text-sm leading-6 text-muted-foreground">{detail.description}</p>
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground">理解难度：</span>
              {Array.from({ length: 5 }, (_, idx) => (
                <Star
                  key={idx}
                  className={`h-3.5 w-3.5 ${idx < detail.difficulty ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/35"}`}
                />
              ))}
            </div>
          </div>
          {isExpandedState ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>

      <AnimatePresence>
        {isExpandedState ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="space-y-5 border-t border-border/60 px-5 pb-5 pt-4">
              {detail.principle ? (
                <section className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium">
                    <BookOpen className="h-4 w-4 text-blue-500" />
                    核心原理
                  </h4>
                  <p className="text-sm leading-6 text-muted-foreground">{detail.principle}</p>
                </section>
              ) : null}

              {detail.formula ? (
                <section className="space-y-2">
                  <h4 className="text-sm font-medium">计算逻辑</h4>
                  <pre className="whitespace-pre-wrap rounded-2xl bg-muted/40 p-4 text-xs leading-6">{detail.formula}</pre>
                </section>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <section className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium text-emerald-600">
                    <CheckCircle2 className="h-4 w-4" />
                    优势
                  </h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {(detail.pros.length ? detail.pros : ["暂未整理优势说明。"]).map((item) => (
                      <li key={item} className="flex items-start gap-2">
                        <span className="mt-1 text-emerald-500">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium text-red-600">
                    <XCircle className="h-4 w-4" />
                    局限
                  </h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {(detail.cons.length ? detail.cons : ["暂未整理局限说明。"]).map((item) => (
                      <li key={item} className="flex items-start gap-2">
                        <span className="mt-1 text-red-500">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>

              <section className="space-y-2">
                <h4 className="flex items-center gap-2 text-sm font-medium text-blue-600">
                  <Target className="h-4 w-4" />
                  适用场景
                </h4>
                <div className="flex flex-wrap gap-2">
                  {(detail.applicable.length ? detail.applicable : ["暂未指定"]).map((item) => (
                    <Badge key={item} variant="outline" className="text-xs">
                      {item}
                    </Badge>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <h4 className="flex items-center gap-2 text-sm font-medium text-orange-600">
                  <AlertTriangle className="h-4 w-4" />
                  风险提醒
                </h4>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {(detail.risks.length ? detail.risks : ["暂未整理风险提醒。"]).map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span className="mt-1 text-orange-500">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {detail.parameters && detail.parameters.length > 0 ? (
                <section className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium">
                    <BarChart3 className="h-4 w-4 text-purple-500" />
                    常用参数
                  </h4>
                  <div className="space-y-2">
                    {detail.parameters.map((param) => (
                      <div
                        key={param.name}
                        className="flex flex-col gap-2 rounded-2xl border border-border/60 bg-muted/20 px-4 py-3 md:flex-row md:items-center md:justify-between"
                      >
                        <div>
                          <div className="text-sm font-medium text-foreground/90">{param.name}</div>
                          <div className="text-xs text-muted-foreground">默认值 {param.default}，{param.desc}</div>
                        </div>
                        <Badge variant="outline">建议范围 {param.range}</Badge>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          </motion.div>
        ) : null}
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
        <p className="text-center text-sm text-muted-foreground">至少选择两种策略后，才适合做横向比较。</p>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="overflow-x-auto p-4">
      <h3 className="mb-4 font-semibold">策略对比</h3>
      <table className="min-w-[560px] w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 pr-3 text-left">维度</th>
            {strategies.map((strategy) => (
              <th key={strategy.id} className="px-3 py-2 text-left">
                {strategy.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b">
            <td className="py-2 pr-3 font-medium">类型</td>
            {strategies.map((strategy) => (
              <td key={`${strategy.id}-type`} className="px-3 py-2">
                <Badge variant="secondary" className="text-xs">
                  {strategy.type}
                </Badge>
              </td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="py-2 pr-3 font-medium">理解难度</td>
            {strategies.map((strategy) => (
              <td key={`${strategy.id}-difficulty`} className="px-3 py-2">
                {"★".repeat(Math.max(1, Math.min(5, strategy.difficulty)))}
              </td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="py-2 pr-3 font-medium">优势数量</td>
            {strategies.map((strategy) => (
              <td key={`${strategy.id}-pros`} className="px-3 py-2 text-emerald-600">
                {strategy.pros.length}
              </td>
            ))}
          </tr>
          <tr>
            <td className="py-2 pr-3 font-medium">风险级别</td>
            {strategies.map((strategy) => {
              const level = strategy.risks.length > 3 ? "高" : strategy.risks.length > 1 ? "中" : "低"
              const className = level === "高" ? "text-red-500" : level === "中" ? "text-orange-500" : "text-emerald-600"
              return (
                <td key={`${strategy.id}-risk`} className={`px-3 py-2 ${className}`}>
                  {level}
                </td>
              )
            })}
          </tr>
        </tbody>
      </table>
    </GlassCard>
  )
}
