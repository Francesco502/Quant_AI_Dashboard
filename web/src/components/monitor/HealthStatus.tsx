"use client"

import { useEffect, useState, type ComponentType } from "react"
import { motion } from "framer-motion"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, type HealthCheckResult } from "@/lib/api"
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Server,
  Database,
  HardDrive,
  Cpu,
  Activity,
  Clock,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface HealthStatusProps {
  autoRefresh?: boolean
  refreshInterval?: number
  showDetailed?: boolean
}

const checkIconsMap: Record<string, ComponentType<{ className?: string }>> = {
  database: Database,
  data_source: Server,
  disk_space: HardDrive,
  memory: Cpu,
  api_response_time: Clock,
  data_update_latency: Clock,
  process_health: Activity,
}

const checkStatusColors: Record<string, string> = {
  healthy: "border-[#4D7358]/24 bg-[rgba(77,115,88,0.08)]",
  degraded: "border-[#B08E61]/24 bg-[rgba(176,142,97,0.08)]",
  unhealthy: "border-[#B6453C]/24 bg-[rgba(182,69,60,0.08)]",
  unknown: "border-gray-500/30 bg-gray-500/10",
}

function getStatusInfo(status: string) {
  switch (status) {
    case "healthy":
      return { icon: CheckCircle2, color: "text-[#4D7358]", bg: "bg-[rgba(77,115,88,0.14)]", label: "健康" }
    case "degraded":
      return { icon: AlertTriangle, color: "text-[#8C724C]", bg: "bg-[rgba(176,142,97,0.14)]", label: "降级" }
    case "unhealthy":
      return { icon: XCircle, color: "text-[#B6453C]", bg: "bg-[rgba(182,69,60,0.14)]", label: "异常" }
    default:
      return { icon: Activity, color: "text-foreground", bg: "bg-black/[0.08]", label: "未知" }
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "healthy":
      return (
        <Badge variant="outline" className="border-[#4D7358]/18 bg-[rgba(77,115,88,0.10)] text-[#4D7358]">
          健康
        </Badge>
      )
    case "degraded":
      return (
        <Badge variant="outline" className="border-[#B08E61]/18 bg-[rgba(176,142,97,0.10)] text-[#8C724C]">
          降级
        </Badge>
      )
    case "unhealthy":
      return <Badge variant="destructive">异常</Badge>
    default:
      return <Badge variant="secondary">未知</Badge>
  }
}

export function HealthStatus({
  autoRefresh = true,
  refreshInterval = 60000,
  showDetailed = true,
}: HealthStatusProps) {
  const [health, setHealth] = useState<HealthCheckResult | null>(null)
  const [loading, setLoading] = useState(true)

  const loadHealth = async () => {
    try {
      setLoading(true)
      const res = await api.monitoring.getHealth()
      setHealth(res.data)
    } catch (error) {
      console.error("Failed to load health:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadHealth()
    if (autoRefresh) {
      const interval = setInterval(() => {
        void loadHealth()
      }, refreshInterval)
      return () => clearInterval(interval)
    }
    return undefined
  }, [autoRefresh, refreshInterval])

  if (loading && !health) {
    return (
      <GlassCard className="p-6 flex items-center justify-center">
        <RefreshCw className="w-6 h-6 animate-spin text-foreground/50" />
      </GlassCard>
    )
  }

  if (!health) return null

  const statusInfo = getStatusInfo(health.status)
  const StatusIcon = statusInfo.icon

  return (
    <div className="space-y-6">
      <GlassCard className="p-6 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-5">
          <StatusIcon className="w-32 h-32" />
        </div>

        <div className="flex items-center gap-4 relative z-10">
          <div className={cn("w-16 h-16 rounded-xl flex items-center justify-center", statusInfo.bg, statusInfo.color)}>
            <StatusIcon className="w-8 h-8" />
          </div>

          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-xl font-semibold text-foreground">系统健康概览</h3>
              {getStatusBadge(health.status)}
            </div>
            <p className="text-sm text-foreground/60">
              最近检查：{" "}
              {new Date(health.timestamp).toLocaleString("zh-CN", {
                year: "numeric",
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </p>
          </div>
        </div>

        {showDetailed && health.checks && (
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(health.checks).map(([name, check]) => {
              const checkStatusColor = checkStatusColors[check.status] || ""
              return (
                <div key={name} className={cn("p-3 rounded-lg border flex items-center gap-3", checkStatusColor)}>
                  <div
                    className={cn(
                      "w-2 h-2 rounded-full shrink-0",
                      check.status === "healthy"
                        ? "bg-[color:var(--market-down)]"
                        : check.status === "degraded"
                          ? "bg-[#B08E61]"
                          : check.status === "unhealthy"
                            ? "bg-[color:var(--market-up)]"
                            : "bg-gray-500"
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground/80 truncate">{check.message}</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </GlassCard>

      {showDetailed && health.checks && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Object.entries(health.checks).map(([name, check], index) => {
            const CheckIcon = checkIconsMap[name] || Activity
            return (
              <motion.div
                key={name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <GlassCard className="p-4">
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "p-2 rounded-lg shrink-0",
                        check.status === "healthy"
                          ? "bg-[rgba(77,115,88,0.10)] text-[#4D7358]"
                          : check.status === "degraded"
                            ? "bg-[rgba(176,142,97,0.10)] text-[#8C724C]"
                            : check.status === "unhealthy"
                              ? "bg-[rgba(182,69,60,0.10)] text-[#B6453C]"
                              : "bg-gray-500/10 text-gray-600"
                      )}
                    >
                      <CheckIcon className="w-4 h-4" />
                    </div>

                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center justify-between">
                        <p className="font-medium text-foreground">{name.replace(/_/g, " ")}</p>
                        {getStatusBadge(check.status)}
                      </div>

                      <p className="text-sm text-foreground/70">{check.message}</p>

                      {check.details && Object.keys(check.details).length > 0 && (
                        <div className="pt-3 border-t border-black/5 dark:border-white/5">
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            {Object.entries(check.details).map(([key, value]) => (
                              <div key={key} className="flex items-center justify-between">
                                <span className="text-foreground/40 capitalize">{key.replace(/_/g, " ")}</span>
                                <span className="font-mono text-foreground/70">
                                  {typeof value === "number" ? value.toFixed(2) : String(value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </GlassCard>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
