"use client"

import { useEffect, useState, type ComponentType } from "react"
import { motion } from "framer-motion"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  HardDrive,
  Server,
  XCircle,
} from "lucide-react"

import { EmptyState } from "@/components/data/empty-state"
import { Badge } from "@/components/ui/badge"
import { GlassCard } from "@/components/ui/card"
import { api, type HealthCheckResult } from "@/lib/api"
import { formatDateTimeInBeijing } from "@/lib/time"
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

const checkLabelMap: Record<string, string> = {
  database: "数据目录",
  data_source: "数据源",
  disk_space: "磁盘空间",
  memory: "内存状态",
  api_response_time: "接口响应",
  data_update_latency: "数据更新",
  process_health: "进程健康",
}

const detailLabelMap: Record<string, string> = {
  path: "目录位置",
  writable: "可写入",
  available: "可用数据源",
  timeout: "超时数据源",
  unavailable: "不可用数据源",
  total_gb: "总容量",
  used_gb: "已用容量",
  free_gb: "剩余容量",
  percent: "占用率",
  total_mb: "总内存",
  used_mb: "已用内存",
  available_mb: "可用内存",
  active_mb: "活跃内存",
  last_response_ms: "最近响应",
  threshold_ms: "阈值",
  last_update: "最近更新时间",
  threshold_seconds: "阈值",
  pid: "进程 ID",
  cpu_percent: "CPU 占用",
  memory_mb: "内存占用",
  num_threads: "线程数",
  open_files: "打开文件",
  connections: "连接数",
}

const checkStatusSurface: Record<string, string> = {
  healthy: "surface-tone-celadon",
  degraded: "surface-tone-ochre",
  unhealthy: "surface-tone-cinnabar",
  unknown: "surface-tone-ink",
}

function getStatusInfo(status: string) {
  switch (status) {
    case "healthy":
      return {
        icon: CheckCircle2,
        color: "text-tone-celadon",
        bg: "surface-tone-celadon",
        label: "健康",
        badge: "success" as const,
      }
    case "degraded":
      return {
        icon: AlertTriangle,
        color: "text-tone-ochre",
        bg: "surface-tone-ochre",
        label: "降级",
        badge: "warning" as const,
      }
    case "unhealthy":
      return {
        icon: XCircle,
        color: "text-tone-cinnabar",
        bg: "surface-tone-cinnabar",
        label: "异常",
        badge: "destructive" as const,
      }
    default:
      return {
        icon: Activity,
        color: "text-tone-ink",
        bg: "surface-tone-ink",
        label: "未知",
        badge: "outline" as const,
      }
  }
}

function formatCheckLabel(name: string) {
  return checkLabelMap[name] ?? name.replace(/_/g, " ")
}

function formatDetailLabel(key: string) {
  return detailLabelMap[key] ?? key.replace(/_/g, " ")
}

function formatDetailValue(key: string, value: unknown) {
  if (value == null) return "未记录"
  if (typeof value === "boolean") return value ? "是" : "否"
  if (Array.isArray(value)) return value.length > 0 ? value.join("、") : "无"
  if (typeof value === "number") {
    if (["pid", "num_threads", "open_files", "connections"].includes(key)) {
      return String(Math.round(value))
    }
    if (key.endsWith("_gb")) return `${value.toFixed(2)} GB`
    if (key.endsWith("_mb")) return `${value.toFixed(2)} MB`
    if (key.endsWith("_ms")) return `${value.toFixed(2)} ms`
    if (key.endsWith("_seconds")) return `${value.toFixed(0)} 秒`
    if (key === "percent" || key.endsWith("_percent")) return `${value.toFixed(2)}%`
    return value.toFixed(2)
  }

  const text = String(value).trim()
  return text.length > 0 ? text : "未记录"
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
      <GlassCard className="p-8">
        <EmptyState
          compact
          title="正在读取健康检查"
          description="系统会在拿到最新检查结果后展示健康概览与明细。"
        />
      </GlassCard>
    )
  }

  if (!health) {
    return (
      <GlassCard className="p-8">
        <EmptyState compact title="暂未获取健康检查" description="当前还没有可展示的健康检查结果。" />
      </GlassCard>
    )
  }

  const statusInfo = getStatusInfo(health.status)
  const StatusIcon = statusInfo.icon
  const checkEntries = Object.entries(health.checks ?? {})
  const healthyCount = checkEntries.filter(([, check]) => check.status === "healthy").length
  const attentionCount = checkEntries.filter(([, check]) => check.status === "degraded" || check.status === "unhealthy").length
  const unknownCount = checkEntries.filter(([, check]) => check.status === "unknown").length
  const verdictText =
    health.status === "healthy"
      ? "当前系统运行平稳，可以继续研究、回测与模拟执行。"
      : health.status === "degraded"
        ? "当前系统可继续运行，但已有检查项提示需要关注。"
        : health.status === "unhealthy"
          ? "当前系统存在异常项，建议先处理健康问题，再继续执行。"
          : "当前系统尚未形成明确结论，建议先查看详细检查。"

  return (
    <div className="space-y-5">
      <GlassCard className="relative overflow-hidden p-5 md:p-6">
        <div className="absolute right-0 top-0 p-4 opacity-[0.05]">
          <StatusIcon className="h-32 w-32" />
        </div>

        <div className="relative z-10 flex items-center gap-4">
          <div className={cn("flex h-14 w-14 items-center justify-center rounded-2xl", statusInfo.bg, statusInfo.color)}>
            <StatusIcon className="h-8 w-8" />
          </div>

          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="section-title">系统健康概览</h3>
              <Badge variant={statusInfo.badge}>{statusInfo.label}</Badge>
            </div>
            <p className="text-[0.92rem] leading-7 text-foreground/82">{verdictText}</p>
            <p className="text-sm leading-7 text-foreground/68">
              最近检查：
              {formatDateTimeInBeijing(health.timestamp, {}, String(health.timestamp))}
            </p>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="data-panel-muted rounded-[18px] px-4 py-3">
            <div className="data-metric-label">通过检查</div>
            <div className="mt-2 text-[1.08rem] font-semibold tracking-tight text-foreground">{healthyCount} 项</div>
          </div>
          <div className="data-panel-muted rounded-[18px] px-4 py-3">
            <div className="data-metric-label">需要关注</div>
            <div className="mt-2 text-[1.08rem] font-semibold tracking-tight text-foreground">{attentionCount} 项</div>
          </div>
          <div className="data-panel-muted rounded-[18px] px-4 py-3">
            <div className="data-metric-label">未定状态</div>
            <div className="mt-2 text-[1.08rem] font-semibold tracking-tight text-foreground">{unknownCount} 项</div>
          </div>
        </div>

        {showDetailed && health.checks ? (
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {Object.entries(health.checks).map(([name, check]) => (
              <div
                key={name}
                className={cn(
                  "rounded-[18px] border px-4 py-3.5",
                  checkStatusSurface[check.status] || "surface-tone-ink",
                )}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                      check.status === "healthy"
                        ? "bg-[rgb(var(--rgb-celadon))]"
                        : check.status === "degraded"
                          ? "bg-[rgb(var(--rgb-ochre))]"
                          : check.status === "unhealthy"
                            ? "bg-[rgb(var(--rgb-cinnabar))]"
                            : "bg-[rgba(var(--rgb-ink),0.4)]",
                    )}
                  />
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="data-metric-label">{formatCheckLabel(name)}</p>
                    <p className="text-[0.9rem] font-medium leading-6 text-foreground/84">{check.message}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </GlassCard>

      {showDetailed && health.checks ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Object.entries(health.checks).map(([name, check], index) => {
            const CheckIcon = checkIconsMap[name] || Activity
            const info = getStatusInfo(check.status)

            return (
              <motion.div
                key={name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <GlassCard className="p-5">
                  <div className="flex items-start gap-3">
                    <div className={cn("shrink-0 rounded-xl p-2.5", info.bg)}>
                      <CheckIcon className="h-4 w-4" />
                    </div>

                    <div className="min-w-0 flex-1 space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[1rem] font-medium text-foreground">{formatCheckLabel(name)}</p>
                        <Badge variant={info.badge}>{info.label}</Badge>
                      </div>

                      <p className="text-sm leading-7 text-foreground/74">{check.message}</p>

                      {check.details && Object.keys(check.details).length > 0 ? (
                        <div className="grid grid-cols-2 gap-3 border-t border-border/50 pt-3">
                          {Object.entries(check.details).map(([key, value]) => (
                            <div key={key} className="data-panel-muted rounded-[16px] px-3.5 py-3">
                              <div className="data-metric-label">{formatDetailLabel(key)}</div>
                              <div className="mt-2 font-mono text-[0.94rem] text-foreground/80">
                                {formatDetailValue(key, value)}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </GlassCard>
              </motion.div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
