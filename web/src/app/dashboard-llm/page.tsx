"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { GlassCard, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { api, type Asset, type LlmDecisionItem, type LlmDashboardSummary, type MarketReviewResponse } from "@/lib/api"
import { Brain, RefreshCw, AlertTriangle, CheckCircle2, BarChart3, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05, delayChildren: 0.08 },
  },
}
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } },
}

export default function DashboardLLMPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [tickerInput, setTickerInput] = useState("")
  const [market, setMarket] = useState("cn")
  const [includeMarketReview, setIncludeMarketReview] = useState(false)
  const [modelOverride, setModelOverride] = useState("")
  const [defaultModel, setDefaultModel] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<{
    results: LlmDecisionItem[]
    summary?: LlmDashboardSummary
    market_review?: MarketReviewResponse
    market_review_error?: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showMarketReview, setShowMarketReview] = useState(true)

  useEffect(() => {
    api.stz.getAssetPool().then((res) => {
      if (res?.length) setAssets(res)
      else
        setAssets([
          { ticker: "600519", name: "贵州茅台", alias: "" },
          { ticker: "000858", name: "五粮液", alias: "" },
        ])
    }).catch(() => setAssets([{ ticker: "600519", name: "贵州茅台", alias: "" }]))
    api.llmAnalysis.getConfig().then((c) => setDefaultModel(c.model ?? null)).catch(() => {})
  }, [])

  const tickers = tickerInput
    ? tickerInput.split(",").map((t) => t.trim()).filter(Boolean)
    : assets.slice(0, 5).map((a) => a.ticker)

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const res = await api.llmAnalysis.dashboard({
        tickers: tickers.length ? tickers : ["600519"],
        market,
        include_market_review: includeMarketReview,
        model: modelOverride.trim() || undefined,
      })
      setData(res)
    } catch (error) {
      const message = error instanceof Error ? error.message : "请求失败"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6 max-w-7xl mx-auto"
    >
      <motion.div variants={item} className="flex justify-between items-end">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">
            决策仪表盘
          </h1>
          <p className="text-[13px] text-foreground/40">
            LLM 智能分析：一句话结论、买卖点位与操作检查清单
          </p>
        </div>
      </motion.div>

      <motion.div variants={item}>
        <GlassCard className="!p-4 flex flex-wrap gap-4 items-end">
          <div className="space-y-1.5 min-w-[240px] flex-1">
            <Label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider">
              标的（逗号分隔或留空用资产池前 5 只）
            </Label>
            <Input
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value)}
              placeholder="如 600519,000858,hk00700"
              className="h-9"
            />
          </div>
          <div className="space-y-1.5 min-w-[120px]">
            <Label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider">
              市场
            </Label>
            <Select value={market} onValueChange={setMarket}>
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cn">A 股</SelectItem>
                <SelectItem value="hk">港股</SelectItem>
                <SelectItem value="us">美股</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="include-review"
              aria-label="附带大盘复盘"
              checked={includeMarketReview}
              onChange={(e) => setIncludeMarketReview(e.target.checked)}
              className="rounded border-border h-4 w-4"
            />
            <Label htmlFor="include-review" className="text-[13px] text-foreground/70 cursor-pointer">
              附带大盘复盘
            </Label>
          </div>
          <div className="space-y-1.5 min-w-[200px]">
            <Label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider">
              模型（可选）
            </Label>
            <Input
              value={modelOverride}
              onChange={(e) => setModelOverride(e.target.value)}
              placeholder={defaultModel ? `留空使用默认: ${defaultModel}` : "留空使用服务端默认"}
              className="h-9 font-mono text-[13px]"
            />
          </div>
          <Button onClick={handleRun} disabled={loading} className="h-9 px-6">
            {loading ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1 }}
                className="mr-2"
              >
                <RefreshCw className="w-4 h-4" />
              </motion.div>
            ) : (
              <Brain className="w-4 h-4 mr-2" />
            )}
            {loading ? "分析中..." : "生成决策"}
          </Button>
        </GlassCard>
      </motion.div>

      {error && (
        <motion.div variants={item}>
          <GlassCard className="p-4 border-red-200 bg-red-50/50 dark:bg-red-950/20">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </GlassCard>
        </motion.div>
      )}

      {data?.summary && data.results?.length > 0 && (
        <motion.div variants={item}>
          <GlassCard className="p-4 flex flex-wrap items-center gap-6">
            <span className="text-[13px] text-foreground/60">汇总</span>
            <span className="text-sm">
              买入 <strong className="text-emerald-600">{data.summary.buy}</strong>
              {" · "}
              观望 <strong className="text-foreground/80">{data.summary.watch}</strong>
              {" · "}
              卖出 <strong className="text-red-600">{data.summary.sell}</strong>
            </span>
            {data.summary.avg_score != null && (
              <span className="text-sm text-foreground/70">
                平均分 <strong>{Number(data.summary.avg_score).toFixed(1)}</strong>
              </span>
            )}
          </GlassCard>
        </motion.div>
      )}

      {data?.results && data.results.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {data.results.map((r) => (
            <motion.div key={r.ticker} variants={item}>
              <DecisionCard item={r} />
            </motion.div>
          ))}
        </div>
      )}

      {data?.market_review && (
        <motion.div variants={item}>
          <GlassCard className="p-4">
            <button
              type="button"
              onClick={() => setShowMarketReview((v) => !v)}
              className="flex items-center gap-2 w-full text-left text-[13px] font-medium text-foreground/80"
            >
              <BarChart3 className="w-4 h-4" />
              大盘复盘 {data.market_review.date}
              {showMarketReview ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
            </button>
            {showMarketReview && (
              <div className="mt-4 pt-4 border-t border-black/[0.06] space-y-3 text-[13px] text-foreground/80">
                {data.market_review.indices && data.market_review.indices.length > 0 && (
                  <div className="flex flex-wrap gap-4">
                    {data.market_review.indices.map((idx) => (
                      <span key={idx.name}>
                        {idx.name} {Number(idx.value).toFixed(2)}{" "}
                        <span className={idx.pct_change >= 0 ? "text-red-500" : "text-emerald-500"}>
                          {(idx.pct_change >= 0 ? "+" : "") + Number(idx.pct_change).toFixed(2)}%
                        </span>
                      </span>
                    ))}
                  </div>
                )}
                {data.market_review.overview && (
                  <p>
                    上涨 {data.market_review.overview.up ?? "—"} 家，下跌 {data.market_review.overview.down ?? "—"} 家
                  </p>
                )}
                {data.market_review.northbound?.description && (
                  <p>{data.market_review.northbound.description}</p>
                )}
              </div>
            )}
          </GlassCard>
        </motion.div>
      )}

      {data?.market_review_error && (
        <motion.div variants={item}>
          <p className="text-[13px] text-amber-600">大盘复盘获取失败：{data.market_review_error}</p>
        </motion.div>
      )}

      {data?.results?.length === 0 && !loading && (
        <motion.div variants={item}>
          <GlassCard className="p-12 flex flex-col items-center justify-center text-muted-foreground gap-4">
            <Brain className="w-16 h-16 opacity-20" />
            <p>请输入标的并点击「生成决策」</p>
          </GlassCard>
        </motion.div>
      )}
    </motion.div>
  )
}

function DecisionCard({ item }: { item: LlmDecisionItem }) {
  const d = item.decision || {}
  const action = d.action || "观望"
  const isBuy = action === "买入"
  const isSell = action === "卖出"

  return (
    <GlassCard className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <CardTitle className="text-base">{item.name || item.ticker}</CardTitle>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">{item.ticker}</p>
        </div>
        <Badge
          variant={isBuy ? "default" : isSell ? "destructive" : "secondary"}
          className={cn(
            isBuy && "bg-emerald-600 hover:bg-emerald-700",
            isSell && "bg-red-600 hover:bg-red-700"
          )}
        >
          {action}
        </Badge>
      </div>

      <p className="text-[13px] text-foreground/80 leading-relaxed">{d.conclusion || "—"}</p>

      {(item.meta?.bias_risk as string) && (
        <p className="text-[12px] text-amber-600 dark:text-amber-400 bg-amber-50/50 dark:bg-amber-950/20 px-3 py-2 rounded-lg">
          ⚠ {item.meta?.bias_risk as string}
        </p>
      )}
      {item.meta?.trend_ok != null && (
        <p className="text-[12px] text-foreground/60">
          均线多头排列(MA5&gt;MA10&gt;MA20)：{item.meta.trend_ok ? "是" : "否"}
        </p>
      )}

      <div className="flex items-center gap-4 text-sm">
        <span className="text-muted-foreground">评分</span>
        <span className="font-semibold">{d.score ?? "—"}</span>
        {(d.buy_price != null || d.stop_loss != null || d.target_price != null) && (
          <span className="text-muted-foreground text-xs">
            买 {d.buy_price ?? "—"} / 止损 {d.stop_loss ?? "—"} / 目标 {d.target_price ?? "—"}
          </span>
        )}
      </div>

      {d.checklist && d.checklist.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider">
            检查清单
          </p>
          <ul className="space-y-1">
            {d.checklist.map((c, i) => (
              <li key={i} className="flex items-center gap-2 text-[13px]">
                {c.status === "满足" ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                ) : c.status === "不满足" ? (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                ) : (
                  <span className="w-3.5 h-3.5 rounded-full border border-foreground/30 shrink-0" />
                )}
                <span>{c.item}</span>
                <span className="text-muted-foreground text-xs">{c.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {d.highlights && d.highlights.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider">
            利好
          </p>
          <ul className="text-[13px] text-foreground/80 list-disc list-inside space-y-0.5">
            {d.highlights.slice(0, 3).map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        </div>
      )}

      {d.risks && d.risks.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider">
            风险
          </p>
          <ul className="text-[13px] text-foreground/80 list-disc list-inside space-y-0.5">
            {d.risks.slice(0, 3).map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </GlassCard>
  )
}
