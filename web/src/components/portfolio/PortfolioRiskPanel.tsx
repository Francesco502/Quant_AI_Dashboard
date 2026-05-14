"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, TrendingUp } from "lucide-react"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { GlassCard } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function formatPct(value: number) {
  return `${(value * 100).toFixed(2)}%`
}

function signedPct(value: number) {
  const sign = value >= 0 ? "+" : ""
  return `${sign}${(value * 100).toFixed(2)}%`
}

function signedClass(value: number) {
  return value >= 0 ? "text-market-up" : "text-market-down"
}

function MetricCard({ label, value, sub, className }: { label: string; value: string; sub?: string; className?: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-xl font-semibold tabular-nums tracking-tight", className)}>{value}</div>
      {sub != null ? <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  )
}

function n(value: unknown, fallback: number = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value
  return fallback
}

export function PortfolioRiskPanel() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.portfolio.analyze>> | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true)
        const overview = await api.user.assets.getOverview(false)
        const assets = overview.assets ?? []
        if (assets.length === 0) {
          setError("尚未添加个人资产，请先在「个人资产」中添加持仓。")
          return
        }
        const holdings = assets.map((a) => ({
          ticker: a.ticker,
          shares: a.units ?? 0,
          cost_price: a.avg_cost,
        }))
        const analysis = await api.portfolio.analyze({ holdings })
        setResult(analysis)
      } catch (err) {
        setError(err instanceof Error ? err.message : "风险分析请求失败")
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const highCorrPairs = useMemo(() => {
    const pairs = result?.highly_correlated_pairs ?? []
    return pairs.filter((c) => {
      const corr = n(c.correlation ?? c.corr)
      return Math.abs(corr) >= 0.7
    })
  }, [result])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <GlassCard key={i}><Skeleton className="h-20 w-full rounded-2xl" /></GlassCard>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <GlassCard className="flex min-h-[240px] flex-col items-center justify-center gap-3 p-8 text-center" role="alert">
        <AlertTriangle className="h-8 w-8 text-tone-cinnabar" />
        <p className="text-sm text-muted-foreground">{error}</p>
        <p className="text-xs text-muted-foreground">添加个人资产后即可使用组合风险分析。</p>
      </GlassCard>
    )
  }

  if (!result) return null

  const summary = result.summary ?? {}
  const annReturn = n(summary.annual_return)
  const annVol = n(summary.annual_volatility)
  const sharpe = n(summary.sharpe_ratio)
  const sortino = n(summary.sortino_ratio)
  const maxDD = n(summary.max_drawdown)
  const var95 = n(summary.var_95 ?? result.risk_metrics?.var_95)
  const cvar95 = n(summary.cvar_95 ?? result.risk_metrics?.cvar_95)
  const totalRet = n(summary.total_return)
  const assetMetrics = (result.asset_metrics ?? []) as Array<Record<string, unknown>>
  const riskContrib = (result.risk_contributions ?? []) as Array<Record<string, unknown>>
  const recommendations = (result.recommendations ?? []) as Array<Record<string, unknown>>

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="年化收益率" value={signedPct(annReturn)} className={signedClass(annReturn)} />
        <MetricCard label="年化波动率" value={formatPct(annVol)} />
        <MetricCard
          label="夏普比率" value={sharpe.toFixed(2)}
          className={sharpe >= 0.5 ? "text-tone-celadon" : sharpe < 0 ? "text-tone-cinnabar" : ""}
        />
        <MetricCard
          label="索提诺比率" value={sortino.toFixed(2)}
          className={sortino >= 0.5 ? "text-tone-celadon" : sortino < 0 ? "text-tone-cinnabar" : ""}
        />
        <MetricCard label="最大回撤" value={formatPct(maxDD)} className="text-tone-cinnabar" />
        <MetricCard label="VaR (95%)" value={formatPct(var95)} className="text-tone-cinnabar" />
        <MetricCard label="CVaR (95%)" value={formatPct(cvar95)} className="text-tone-cinnabar" />
        <MetricCard label="累计收益" value={signedPct(totalRet)} className={signedClass(totalRet)} />
      </div>

      {recommendations.length > 0 ? (
        <GlassCard className="p-5">
          <h3 className="text-sm font-semibold text-foreground/90">建议</h3>
          <ul className="mt-3 space-y-2">
            {recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[rgb(var(--rgb-ochre))]" />
                {String(rec.message ?? rec.text ?? rec)}
              </li>
            ))}
          </ul>
        </GlassCard>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        {assetMetrics.length > 0 ? (
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold text-foreground/90">资产指标</h3>
            <div className="mt-3 overflow-hidden rounded-xl border border-border/60">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60 bg-muted/30">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">标的</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">权重</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">波动率</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">夏普</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">最大回撤</th>
                  </tr>
                </thead>
                <tbody>
                  {assetMetrics.map((m) => (
                    <tr key={String(m.ticker)} className="border-b border-border/40">
                      <td className="px-3 py-2.5">
                        <div className="font-medium">{String(m.ticker)}</div>
                        {m.asset_name ? <div className="text-xs text-muted-foreground">{String(m.asset_name)}</div> : null}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{formatPct(n(m.weight))}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{formatPct(n(m.annual_volatility))}</td>
                      <td className={cn("px-3 py-2.5 text-right tabular-nums", signedClass(n(m.sharpe_ratio)))}>
                        {n(m.sharpe_ratio).toFixed(2)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-tone-cinnabar">{formatPct(n(m.max_drawdown))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        ) : null}

        {riskContrib.length > 0 ? (
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold text-foreground/90">风险贡献</h3>
            <div className="mt-3 overflow-hidden rounded-xl border border-border/60">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60 bg-muted/30">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">标的</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">边际风险</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">风险占比</th>
                  </tr>
                </thead>
                <tbody>
                  {riskContrib.map((rc) => (
                    <tr key={String(rc.ticker)} className="border-b border-border/40">
                      <td className="px-3 py-2.5 font-medium">{String(rc.ticker)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{n(rc.marginal_risk).toFixed(4)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{formatPct(n(rc.risk_pct))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        ) : null}
      </div>

      {highCorrPairs.length > 0 ? (
        <GlassCard className="p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground/90">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            高相关性警告（|ρ| ≥ 0.7）
          </h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {highCorrPairs.map((pair, i) => {
              const t1 = String(pair.ticker_1 ?? pair.t1 ?? "")
              const t2 = String(pair.ticker_2 ?? pair.t2 ?? "")
              const corr = n(pair.correlation ?? pair.corr)
              return (
                <div
                  key={i}
                  className="inline-flex items-center gap-2 rounded-full border border-amber-200/60 bg-amber-50/60 px-3 py-1.5 text-xs dark:border-amber-700/30 dark:bg-amber-900/20"
                >
                  <span className="font-medium">{t1}</span>
                  <TrendingUp className="h-3 w-3 text-amber-600" />
                  <span className="font-medium">{t2}</span>
                  <span className="tabular-nums text-amber-700 dark:text-amber-400">{corr.toFixed(2)}</span>
                </div>
              )
            })}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            这些资产对的相关性较高，同时持有可能无法有效分散风险。
          </p>
        </GlassCard>
      ) : null}
    </div>
  )
}
