"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { AlertCircle, AlertTriangle, Bell, CheckCircle2, Filter, RefreshCw, XCircle } from "lucide-react"

import { EmptyState } from "@/components/data/empty-state"
import { toast } from "sonner"
import { PanelHeader } from "@/components/data/panel-header"
import { StatusPill } from "@/components/data/status-pill"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { api, type AlertHistoryItem, type AlertStatistics } from "@/lib/api"
import { formatMonthDayInBeijing, formatTimeInBeijing } from "@/lib/time"
import { cn } from "@/lib/utils"

interface AlertHistoryProps {
  showFilters?: boolean
  showStats?: boolean
  autoRefresh?: boolean
  refreshInterval?: number
}

type Severity = "critical" | "error" | "warning" | "info" | "unknown"

const severityMeta: Record<
  Severity,
  { label: string; icon: typeof Bell; tone: "cinnabar" | "ochre" | "indigo" | "ink"; badge: "destructive" | "warning" | "info" | "outline" }
> = {
  critical: { label: "严重", icon: XCircle, tone: "cinnabar", badge: "destructive" },
  error: { label: "错误", icon: AlertCircle, tone: "cinnabar", badge: "destructive" },
  warning: { label: "预警", icon: AlertTriangle, tone: "ochre", badge: "warning" },
  info: { label: "提示", icon: CheckCircle2, tone: "indigo", badge: "info" },
  unknown: { label: "未知", icon: Bell, tone: "ink", badge: "outline" },
}

function toSeverity(value?: string): Severity {
  const normalized = value?.toLowerCase()
  if (normalized === "critical") return "critical"
  if (normalized === "error") return "error"
  if (normalized === "warning") return "warning"
  if (normalized === "info") return "info"
  return "unknown"
}

function SeverityBadge({ severity }: { severity?: string }) {
  const meta = severityMeta[toSeverity(severity)]
  const Icon = meta.icon

  return (
    <Badge variant={meta.badge} className="gap-1.5">
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
    </Badge>
  )
}

function formatTimestamp(timestamp: string) {
  return {
    time: formatTimeInBeijing(timestamp, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }, timestamp),
    date: formatMonthDayInBeijing(timestamp, timestamp),
  }
}

export function AlertHistory({
  showFilters = true,
  showStats = true,
  autoRefresh = true,
  refreshInterval = 30000,
}: AlertHistoryProps) {
  const [alerts, setAlerts] = useState<AlertHistoryItem[]>([])
  const [stats, setStats] = useState<AlertStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterSeverity, setFilterSeverity] = useState<string>("all")
  const [limit, setLimit] = useState(50)

  const loadAlerts = useCallback(async () => {
    try {
      setLoading(true)
      const response = await api.monitoring.getAlertHistory(
        limit,
        filterSeverity === "all" ? undefined : filterSeverity,
      )
      setAlerts(response.data ?? [])
    } catch (error: unknown) {
      console.error("Failed to load alerts:", error)
      toast.error("加载告警记录失败")
    } finally {
      setLoading(false)
    }
  }, [filterSeverity, limit])

  const loadStats = useCallback(async () => {
    try {
      const response = await api.monitoring.getAlertStatistics()
      setStats(response.data)
    } catch (error: unknown) {
      console.error("Failed to load alert statistics:", error)
      toast.error("加载告警统计失败")
    }
  }, [])

  useEffect(() => {
    void loadAlerts()
    void loadStats()

    if (!autoRefresh) {
      return
    }

    const timer = setInterval(() => {
      void loadAlerts()
      void loadStats()
    }, refreshInterval)

    return () => clearInterval(timer)
  }, [autoRefresh, refreshInterval, loadAlerts, loadStats])

  const headerMeta = useMemo(() => {
    if (!showStats || !stats) return null

    return (
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill label="累计" value={String(stats.total_alerts)} tone="ink" />
        <StatusPill label="24 小时" value={String(stats.recent_alerts_24h)} tone="ochre" />
        <StatusPill label="规则数" value={String(stats.active_rules)} tone="indigo" />
      </div>
    )
  }, [showStats, stats])

  return (
    <div className="space-y-5">
      <PanelHeader
        title={
          <h2 className="section-title flex items-center gap-2">
            <Bell className="h-5 w-5" />
            告警历史
          </h2>
        }
        description="查看系统告警记录、严重度分布与最近变化。"
        meta={headerMeta}
      />

      {showFilters ? (
        <GlassCard className="space-y-3 p-3.5">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground/82">
            <Filter className="h-4 w-4 text-foreground/56" />
            严重度筛选
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { value: "all", label: "全部" },
              { value: "critical", label: "严重" },
              { value: "error", label: "错误" },
              { value: "warning", label: "预警" },
              { value: "info", label: "提示" },
            ].map((option) => {
              const active = filterSeverity === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setFilterSeverity(option.value)}
                  className={cn(
                    "inline-flex min-h-11 items-center rounded-full border px-4 py-2 text-[0.84rem] font-medium transition-[background-color,border-color,color,box-shadow] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] sm:min-h-0 sm:px-3.5 sm:py-1.5",
                    active
                      ? "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.12)] text-foreground shadow-[0_8px_18px_rgba(41,33,25,0.04)]"
                      : "border-black/[0.06] bg-[rgba(var(--rgb-xuan),0.7)] text-foreground/72 hover:bg-[rgba(var(--rgb-xuan),0.94)] hover:text-foreground/88",
                  )}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        </GlassCard>
      ) : null}

      <div className="space-y-3">
        {loading && alerts.length === 0 ? (
          <GlassCard className="p-8">
            <EmptyState
              compact
              title="正在读取告警记录"
              description="系统会在拿到最新告警后显示严重度分布与历史列表。"
            />
          </GlassCard>
        ) : alerts.length === 0 ? (
          <GlassCard className="p-8">
            <EmptyState
              title="暂无告警"
              description={
                filterSeverity === "all"
                  ? "当前系统运行平稳，没有新的监控告警。"
                  : `当前没有“${severityMeta[toSeverity(filterSeverity)].label}”级别的告警。`
              }
            />
          </GlassCard>
        ) : (
          <>
            {alerts.map((alert, index) => {
              const severity = toSeverity(alert.severity)
              const toneClass = `surface-tone-${severityMeta[severity].tone}`
              const time = formatTimestamp(alert.timestamp)

              return (
                <motion.div
                  key={alert.alert_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.01 }}
                >
                  <GlassCard className={cn("space-y-4 p-5", toneClass)}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <SeverityBadge severity={alert.severity} />
                          <h4 className="text-[1rem] font-medium tracking-[0.01em] text-foreground">
                            {alert.rule_name}
                          </h4>
                          {alert.aggregate_count > 1 ? (
                            <Badge variant="outline" className="font-mono">
                              x{alert.aggregate_count}
                            </Badge>
                          ) : null}
                        </div>
                        <p className="text-sm leading-7 text-foreground/76">{alert.message}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="font-mono text-[0.82rem] text-foreground/74">{time.time}</div>
                        <div className="mt-1 text-[0.78rem] text-foreground/58">{time.date}</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 border-t border-black/5 pt-4 md:grid-cols-4">
                      <div className="data-panel-muted rounded-[18px] px-4 py-3">
                        <div className="data-metric-label">指标</div>
                        <div className="mt-2 truncate font-mono text-[0.94rem] text-foreground/80">{alert.metric_name}</div>
                      </div>
                      <div className="data-panel-muted rounded-[18px] px-4 py-3">
                        <div className="data-metric-label">当前值</div>
                        <div className="mt-2 font-mono text-[0.94rem] text-foreground/80">{alert.metric_value.toFixed(2)}</div>
                      </div>
                      <div className="data-panel-muted rounded-[18px] px-4 py-3">
                        <div className="data-metric-label">阈值</div>
                        <div className="mt-2 font-mono text-[0.94rem] text-foreground/80">{alert.threshold.toFixed(2)}</div>
                      </div>
                      <div className="data-panel-muted rounded-[18px] px-4 py-3">
                        <div className="data-metric-label">通道数</div>
                        <div className="mt-2 text-[0.94rem] font-medium text-foreground/80">{alert.channels?.length ?? 0}</div>
                      </div>
                    </div>
                  </GlassCard>
                </motion.div>
              )
            })}

            <div className="flex justify-center pt-4">
              <Button variant="outline" onClick={() => setLimit((prev) => prev + 50)}>
                <RefreshCw className="mr-2 h-4 w-4" />
                加载更多
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
