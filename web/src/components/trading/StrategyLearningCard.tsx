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
  "BBI-KDJ 低位布局": {
    id: "bbi_kdj",
    name: "BBI-KDJ 低位布局",
    type: "均值回归 / 复合摆动",
    difficulty: 3,
    description: "结合多空指数 (BBI) 与 KDJ 摆动指标，在价格处于长期中轨下方且 J 值极度超卖时寻找左侧低位布局机会。",
    principle: "BBI 用于界定中长期趋势，KDJ 用于捕捉短期超跌。当价格偏离中轨且 J 值 < 15 时，表明出现低位共振。",
    formula: "BBI = (MA(3) + MA(6) + MA(12) + MA(24)) / 4\n当 Price < BBI 且 KDJ.J < j_threshold 时触发买入。",
    pros: ["能捕捉到极佳的左侧建仓点", "在震荡筑底行情中胜率高"],
    cons: ["在单边下跌大熊市中容易频繁接飞刀", "需要严格的止损配合"],
    applicable: ["震荡筑底行情", "中长期超跌反弹"],
    risks: ["单边熊市阴跌", "均线系统整体向下发散时的伪金叉风险"],
    parameters: [
      { name: "j_threshold", default: 15, range: "0-20", desc: "KDJ 的 J 值超卖阈值" }
    ],
  },
  "SuperB1 趋势突破": {
    id: "super_b1",
    name: "SuperB1 趋势突破",
    type: "趋势跟随 / 突破",
    difficulty: 4,
    description: "一种基于价格创阶段新高、配合量能放大与超买修正的强力趋势突破策略。",
    principle: "监控过去 N 日的最高价突破，结合成交量放大以过滤假突破。同时使用修正版的 KDJ 指标确保突破时具备强劲动能。",
    formula: "Close > Max(Close, N) 且 Volume > Vol_Threshold 且 J > j_threshold。",
    pros: ["能抓住主升浪行情", "自动过滤无量假突破"],
    cons: ["在宽幅震荡市中会被来回双向磨损", "买入成本相对较高"],
    applicable: ["单边牛市", "行业板块突破行情"],
    risks: ["突破后迅速回踩夭折", "高位追涨导致的深度回撤"],
    parameters: [
      { name: "lookback_n", default: 10, range: "5-30", desc: "历史最高价回看天数" }
    ],
  },
  "BBI 长短波段": {
    id: "bbi_short_long",
    name: "BBI 长短波段",
    type: "趋势波段",
    difficulty: 3,
    description: "通过长短两个周期的多空指数 (BBI) 的交叉与排布，捕捉中长期波段的趋势起步与转折点。",
    principle: "短周期 BBI 反应灵敏，长周期 BBI 趋势稳健。短周期上穿长周期为买入信号，下穿为卖出信号。",
    formula: "短周期 BBI = (MA(5) + MA(10) + MA(20) + MA(40)) / 4\n长周期 BBI = (MA(10) + MA(20) + MA(40) + MA(80)) / 4\n当 BBI(short) > BBI(long) 且处于低位时买入。",
    pros: ["中长线趋势跟踪能力强", "有效过滤日内噪音"],
    cons: ["趋势转折期会有一定的利润回吐", "震荡横盘期交易频繁"],
    applicable: ["单边多头波段", "大周期趋势跟踪"],
    risks: ["中轨附近反复缠绕磨损", "长周期限制导致的利润大幅回撤"],
    parameters: [
      { name: "n_short", default: 5, range: "3-10", desc: "短周期均线参数" },
      { name: "n_long", default: 21, range: "15-50", desc: "长周期均线参数" }
    ],
  },
  "Peak KDJ 回踩确认": {
    id: "peak_kdj",
    name: "Peak KDJ 回踩确认",
    type: "动量回调",
    difficulty: 3,
    description: "在多头趋势确立的前提下，等待 KDJ 指标回踩超卖区间完成确认后，寻找分批逢低买入的机会。",
    principle: "强势股的回调往往是买点。利用 KDJ 判定短期超跌，结合价格波幅（Fluctuation）过滤无序震荡。",
    formula: "长期均线多头 且 KDJ.J 从高位回踩至 j_threshold 附近。",
    pros: ["买在上升通道的局部低点", "风险收益比（盈亏比）极佳"],
    cons: ["在趋势反转时容易买在第一波大跌起点", "需要对大趋势有极高准确度判定"],
    applicable: ["震荡上行市", "强势股回调"],
    risks: ["趋势彻底破位后的抄底风险", "成交量萎缩下的虚假企稳"],
    parameters: [
      { name: "j_threshold", default: 10, range: "5-20", desc: "超卖回踩确认阈值" }
    ],
  },
  "MA60 放量上穿": {
    id: "ma60_cross",
    name: "MA60 放量上穿",
    type: "均线突破",
    difficulty: 2,
    description: "经典的牛熊生命线突破策略。当价格放量站上 60 日均线，表明中线行情启动，适合长线布局。",
    principle: "60 日均线是中长期牛熊分界线。放量站上表明有主力资金流入，趋势发生质变。",
    formula: "Close > MA(60) 且 Close[1] <= MA(60)[1] 且 Volume > 1.8 * MA(Volume, 25)。",
    pros: ["能抓住大级别行情的起涨点", "规则极其简单，不易过拟合"],
    cons: ["均线走平时会反复站上并跌破", "牛市末期容易产生假金叉"],
    applicable: ["底部启动行情", "中长期牛熊转换"],
    risks: ["放量冲高回落的假突破", "60日均线斜率向下时的压制破位"],
    parameters: [
      { name: "vol_multiple", default: 1.8, range: "1.2-3.0", desc: "放量倍数限制" }
    ],
  },
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
  "MACD 策略": {
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
  "布林带策略": {
    id: "bollinger",
    name: "布林带策略",
    type: "波动率",
    difficulty: 3,
    description: "观察价格相对通道的位置，适合做均值回归或波动收敛后的突破。",
    principle: "价格偏离中轨过多时关注回归，带宽收窄后则留意趋势扩张。",
    formula: "中轨 = MA(20)\n上轨 = 中轨 + 2×标准差\n下轨 = 中轨 - 2×标准差",
    pros: ["能同时观察趋势 and 波动", "图形可视化非常直观"],
    cons: ["单独使用容易误判假突破", "对不同市场要调参数"],
    applicable: ["区间震荡", "波动率收敛后的突破行情"],
    risks: ["单边趋势中逆势接飞刀", "带宽扩张时回归判断失效"],
    parameters: [
      { name: "窗口", default: 20, range: "10-30", desc: "均线与波动率计算窗口" },
      { name: "标准差倍数", default: 2, range: "1.5-3", desc: "通道宽度倍数" },
    ],
  },
  "动量策略": {
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
            <p className="text-sm leading-7 text-foreground/68">{detail.description}</p>
            <div className="flex items-center gap-1">
              <span className="text-[0.82rem] text-foreground/62">理解难度：</span>
              {Array.from({ length: 5 }, (_, idx) => (
                <Star
                  key={idx}
                  className={`h-3.5 w-3.5 ${idx < detail.difficulty ? "fill-[rgb(var(--rgb-ochre))] text-[rgb(var(--rgb-ochre))]" : "text-foreground/24"}`}
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
                    <BookOpen className="h-4 w-4 text-tone-indigo" />
                    核心原理
                  </h4>
                  <p className="text-sm leading-7 text-foreground/68">{detail.principle}</p>
                </section>
              ) : null}

              {detail.formula ? (
                <section className="space-y-2">
                  <h4 className="text-[0.98rem] font-medium text-foreground/84">计算逻辑</h4>
                  <pre className="whitespace-pre-wrap rounded-2xl bg-muted/40 p-4 text-[0.82rem] leading-7 text-foreground/74">{detail.formula}</pre>
                </section>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <section className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium text-tone-celadon">
                    <CheckCircle2 className="h-4 w-4" />
                    优势
                  </h4>
                  <ul className="space-y-1 text-sm leading-7 text-foreground/68">
                    {(detail.pros.length ? detail.pros : ["暂未整理优势说明。"]).map((item) => (
                      <li key={item} className="flex items-start gap-2">
                        <span className="mt-1 text-tone-celadon">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium text-tone-cinnabar">
                    <XCircle className="h-4 w-4" />
                    局限
                  </h4>
                  <ul className="space-y-1 text-sm leading-7 text-foreground/68">
                    {(detail.cons.length ? detail.cons : ["暂未整理局限说明。"]).map((item) => (
                      <li key={item} className="flex items-start gap-2">
                        <span className="mt-1 text-tone-cinnabar">•</span>
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
                    <Badge key={item} variant="outline">
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
                  <ul className="space-y-1 text-sm leading-7 text-foreground/68">
                  {(detail.risks.length ? detail.risks : ["暂未整理风险提醒。"]).map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span className="mt-1 text-tone-ochre">•</span>
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
                          <div className="text-sm leading-7 text-foreground/66">默认值 {param.default}，{param.desc}</div>
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
        <p className="text-center text-sm leading-7 text-foreground/66">至少选择两种策略后，才适合做横向比较。</p>
      </GlassCard>
    )
  }

  return (
    <GlassCard className="p-4">
      <CardTitle className="mb-4">策略对比</CardTitle>
      <div className="space-y-3 lg:hidden">
        {strategies.map((strategy) => {
          const riskLevel = strategy.risks.length > 3 ? "高" : strategy.risks.length > 1 ? "中" : "低"
          const riskClass = riskLevel === "高" ? "text-tone-cinnabar" : riskLevel === "中" ? "text-tone-ochre" : "text-tone-celadon"
          return (
            <div key={`${strategy.id}-mobile`} className="rounded-[24px] border border-border/60 bg-background/72 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="font-medium text-foreground">{strategy.name}</div>
                <Badge variant="secondary">{strategy.type}</Badge>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                <div className="rounded-2xl bg-muted/30 px-3 py-2">
                  <div className="text-xs text-muted-foreground">难度</div>
                  <div className="mt-1">{"★".repeat(Math.max(1, Math.min(5, strategy.difficulty)))}</div>
                </div>
                <div className="rounded-2xl bg-muted/30 px-3 py-2">
                  <div className="text-xs text-muted-foreground">优势</div>
                  <div className="mt-1 font-medium text-tone-celadon">{strategy.pros.length}</div>
                </div>
                <div className="rounded-2xl bg-muted/30 px-3 py-2">
                  <div className="text-xs text-muted-foreground">风险</div>
                  <div className={`mt-1 font-medium ${riskClass}`}>{riskLevel}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      <table className="hidden min-w-[560px] w-full text-sm lg:table">
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
                <Badge variant="secondary">
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
              <td key={`${strategy.id}-pros`} className="px-3 py-2 text-tone-celadon">
                {strategy.pros.length}
              </td>
            ))}
          </tr>
          <tr>
            <td className="py-2 pr-3 font-medium">风险级别</td>
            {strategies.map((strategy) => {
              const level = strategy.risks.length > 3 ? "高" : strategy.risks.length > 1 ? "中" : "低"
              const className = level === "高" ? "text-tone-cinnabar" : level === "中" ? "text-tone-ochre" : "text-tone-celadon"
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
