"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, type AlertHistoryItem, type AlertStatistics } from "@/lib/api"
import { AlertCircle, AlertTriangle, Bell, CheckCircle2, Filter, RefreshCw, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface AlertHistoryProps {
  showFilters?: boolean
  showStats?: boolean
  autoRefresh?: boolean
  refreshInterval?: number
}

type Severity = "critical" | "error" | "warning" | "info" | "unknown"

const severityMeta: Record<Severity, { label: string; textClass: string; bgClass: string; icon: typeof Bell }> = {
  critical: { label: "Critical", textClass: "text-red-600", bgClass: "bg-red-500", icon: XCircle },
  error: { label: "Error", textClass: "text-red-500", bgClass: "bg-red-400", icon: AlertCircle },
  warning: { label: "Warning", textClass: "text-amber-600", bgClass: "bg-amber-500", icon: AlertTriangle },
  info: { label: "Info", textClass: "text-blue-600", bgClass: "bg-blue-500", icon: CheckCircle2 },
  unknown: { label: "Unknown", textClass: "text-gray-600", bgClass: "bg-gray-500", icon: Bell },
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
    <Badge variant="outline" className={cn("px-2 py-0.5 text-[11px] font-medium border", meta.textClass, `${meta.bgClass}/10`)}>
      <Icon className={cn("mr-1 h-3 w-3", meta.textClass)} />
      {meta.label}
    </Badge>
  )
}

function formatTimestamp(timestamp: string) {
  const date = new Date(timestamp)
  return {
    time: date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    date: date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }),
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
      const response = await api.monitoring.getAlertHistory(limit, filterSeverity === "all" ? undefined : filterSeverity)
      setAlerts(response.data ?? [])
    } catch (error: unknown) {
      console.error("Failed to load alerts:", error)
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

  const colorBySeverity = useMemo(
    () => ({
      critical: "bg-red-100 dark:bg-red-900/20",
      error: "bg-red-50 dark:bg-red-900/10",
      warning: "bg-amber-50 dark:bg-amber-900/20",
      info: "bg-blue-50 dark:bg-blue-900/20",
      unknown: "bg-gray-50 dark:bg-gray-900/20",
    }),
    []
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="flex items-center gap-2 text-xl font-semibold tracking-[-0.02em] text-foreground/90">
            <Bell className="h-5 w-5" />
            Alert History
          </h2>
          <p className="text-[13px] text-foreground/40">System alert records and severity distribution.</p>
        </div>

        {showStats && stats && (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-foreground/40">Total</span>
              <span className="font-semibold text-foreground">{stats.total_alerts}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-foreground/40">24h</span>
              <span className="font-semibold text-foreground">{stats.recent_alerts_24h}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-foreground/40">Rules</span>
              <span className="font-semibold text-foreground">{stats.active_rules}</span>
            </div>
          </div>
        )}
      </div>

      {showFilters && (
        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-foreground/40" />
              <span className="text-sm font-medium text-foreground/70">Severity</span>
            </div>
            <div className="flex items-center gap-2">
              {[
                { value: "all", label: "All" },
                { value: "critical", label: "Critical" },
                { value: "error", label: "Error" },
                { value: "warning", label: "Warning" },
                { value: "info", label: "Info" },
              ].map((option) => (
                <button
                  key={option.value}
                  onClick={() => setFilterSeverity(option.value)}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-sm transition-colors",
                    filterSeverity === option.value
                      ? "bg-foreground text-background dark:bg-background dark:text-foreground"
                      : "bg-foreground/5 text-foreground/60 hover:bg-foreground/10 dark:bg-white/5 dark:text-foreground/50 dark:hover:bg-white/10"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </GlassCard>
      )}

      <div className="space-y-3">
        {loading && alerts.length === 0 ? (
          <div className="flex items-center justify-center p-12">
            <RefreshCw className="h-6 w-6 animate-spin text-foreground/50" />
          </div>
        ) : alerts.length === 0 ? (
          <GlassCard className="flex flex-col items-center justify-center p-12 text-center">
            <CheckCircle2 className="mb-4 h-12 w-12 text-emerald-500/20" />
            <p className="text-lg font-medium text-foreground">No Alerts</p>
            <p className="mt-2 text-sm text-foreground/40">
              {filterSeverity === "all" ? "System is running normally." : `No ${filterSeverity} alerts found.`}
            </p>
          </GlassCard>
        ) : (
          <>
            {alerts.map((alert, index) => {
              const severity = toSeverity(alert.severity)

              return (
                <motion.div
                  key={alert.alert_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.01 }}
                >
                  <GlassCard className={cn("p-4 transition-all hover:shadow-lg", colorBySeverity[severity])}>
                    <div className="flex items-start gap-3">
                      <div
                        className={cn(
                          "mt-1 h-2 w-2 shrink-0 rounded-full",
                          severity === "critical"
                            ? "bg-red-500"
                            : severity === "error"
                              ? "bg-red-400"
                              : severity === "warning"
                                ? "bg-amber-500"
                                : "bg-blue-500"
                        )}
                      />

                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="mb-1 flex items-center gap-2">
                              <SeverityBadge severity={alert.severity} />
                              <h4 className="truncate font-medium text-foreground">{alert.rule_name}</h4>
                            </div>
                            <p className="truncate text-sm text-foreground/70">{alert.message}</p>
                          </div>

                          <div className="flex shrink-0 items-center gap-2">
                            {alert.aggregate_count > 1 && (
                              <span className="rounded bg-foreground/10 px-1.5 py-0.5 font-mono text-[10px]">x{alert.aggregate_count}</span>
                            )}
                            <span className="whitespace-nowrap font-mono text-[10px] text-foreground/40">
                              {formatTimestamp(alert.timestamp).time}
                            </span>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2 border-t border-black/5 pt-3 text-xs dark:border-white/5 md:grid-cols-4">
                          <div className="flex items-center justify-between">
                            <span className="text-foreground/40">Metric</span>
                            <span className="max-w-[100px] truncate font-mono text-foreground/70">{alert.metric_name}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-foreground/40">Current</span>
                            <span className="font-mono text-foreground/70">{alert.metric_value.toFixed(2)}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-foreground/40">Threshold</span>
                            <span className="font-mono text-foreground/70">{alert.threshold.toFixed(2)}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-foreground/40">Channels</span>
                            <span className="font-medium text-foreground/80">{alert.channels?.length ?? 0}</span>
                          </div>
                        </div>

                        <div className="text-[10px] text-foreground/30">{formatTimestamp(alert.timestamp).date}</div>
                      </div>
                    </div>
                  </GlassCard>
                </motion.div>
              )
            })}

            <div className="flex justify-center pt-4">
              <button
                onClick={() => setLimit((prev) => prev + 50)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground/60 transition-colors hover:text-foreground"
              >
                <RefreshCw className="h-4 w-4" />
                Load More
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
