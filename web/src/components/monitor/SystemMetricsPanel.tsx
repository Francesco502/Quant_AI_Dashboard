"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Activity, AlertTriangle, Box, Cpu, HardDrive, Server, Wifi, Zap } from "lucide-react"

import { EmptyState } from "@/components/data/empty-state"
import { PanelHeader } from "@/components/data/panel-header"
import { StatusPill } from "@/components/data/status-pill"
import { GlassCard } from "@/components/ui/card"
import { api, type DetailedSystemMetrics, type SystemMetrics } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"

interface SystemMetricsPanelProps {
  detailed?: boolean
  autoRefresh?: boolean
  refreshInterval?: number
  showHeader?: boolean
  showLatency?: boolean
}

function ResourceMetricCard({
  icon: Icon,
  tone,
  title,
  description,
  value,
  status,
  progress,
  detail,
}: {
  icon: typeof Cpu
  tone: "indigo" | "plum" | "ochre"
  title: string
  description: string
  value: string
  status: string
  progress: number
  detail?: string
}) {
  const progressColor =
    progress >= 90
      ? SONG_COLORS.cinnabar
      : progress >= 75
        ? SONG_COLORS.ochre
        : tone === "indigo"
          ? SONG_COLORS.indigo
          : tone === "plum"
            ? SONG_COLORS.plum
            : SONG_COLORS.celadon

  return (
    <GlassCard className="space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`surface-tone-${tone} rounded-xl p-2.5`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <p className="text-[0.98rem] font-medium text-foreground/88">{title}</p>
            <p className="text-[0.88rem] leading-6 text-foreground/70">{description}</p>
          </div>
        </div>
        <StatusPill label="状态" value={status} tone={tone} />
      </div>

      <div className="space-y-2">
        <div className="text-[2rem] font-semibold tracking-[-0.04em] text-foreground">{value}</div>
        {detail ? <p className="text-sm leading-6 text-foreground/68">{detail}</p> : null}
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-foreground/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(0, Math.min(progress, 100))}%` }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ backgroundColor: progressColor }}
        />
      </div>
    </GlassCard>
  )
}

function DetailMetricGrid({
  icon: Icon,
  title,
  tone,
  items,
}: {
  icon: typeof Server
  title: string
  tone: "indigo" | "plum" | "ochre" | "celadon"
  items: Array<{ label: string; value: string }>
}) {
  return (
    <GlassCard className="space-y-4 p-5">
      <div className="flex items-center gap-3">
        <div className={`surface-tone-${tone} rounded-xl p-2`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="text-sm font-medium text-foreground/86">{title}</div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => (
          <div key={item.label} className="data-panel-muted rounded-[18px] px-4 py-3">
            <div className="data-metric-label">{item.label}</div>
            <div className="mt-2 text-[1.08rem] font-semibold tracking-tight text-foreground">{item.value}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}

export function SystemMetricsPanel({
  detailed = false,
  autoRefresh = true,
  refreshInterval = 30000,
  showHeader = true,
  showLatency = true,
}: SystemMetricsPanelProps) {
  const [metrics, setMetrics] = useState<SystemMetrics | DetailedSystemMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadMetrics = useCallback(async () => {
    try {
      setLoading(true)
      const response = detailed ? await api.monitoring.getDetailedMetrics() : await api.monitoring.getMetrics()
      setMetrics(response.data)
      setError(null)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "读取系统指标失败。"
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [detailed])

  useEffect(() => {
    void loadMetrics()

    if (!autoRefresh) {
      return
    }

    const timer = setInterval(() => {
      void loadMetrics()
    }, refreshInterval)

    return () => clearInterval(timer)
  }, [autoRefresh, refreshInterval, loadMetrics])

  const normalized = useMemo(() => {
    if (!metrics) {
      return {
        cpuUsage: 0,
        memoryUsage: 0,
        memoryUsedMb: 0,
        memoryTotalMb: 0,
        diskUsage: 0,
        diskFreeGb: 0,
        dataUpdateLatency: 0,
        orderExecutionLatency: 0,
        apiResponseTime: 0,
        processCpuUsage: 0,
      }
    }

    if ("cpu_usage" in metrics) {
      return {
        cpuUsage: metrics.cpu_usage,
        memoryUsage: metrics.memory_usage,
        memoryUsedMb: metrics.memory_used_mb,
        memoryTotalMb: metrics.memory_used_mb + metrics.memory_available_mb,
        diskUsage: metrics.disk_usage,
        diskFreeGb: metrics.disk_free_gb,
        dataUpdateLatency: metrics.data_update_latency,
        orderExecutionLatency: metrics.order_execution_latency,
        apiResponseTime: metrics.api_response_time,
        processCpuUsage: metrics.process_cpu_usage,
      }
    }

    return {
      cpuUsage: metrics.process.cpu.percent,
      memoryUsage: metrics.system.memory.percent,
      memoryUsedMb: metrics.system.memory.used_mb,
      memoryTotalMb: metrics.system.memory.total_mb,
      diskUsage: metrics.storage.disk.percent,
      diskFreeGb: metrics.storage.disk.free_gb,
      dataUpdateLatency: metrics.business.data_update_latency,
      orderExecutionLatency: metrics.business.order_execution_latency,
      apiResponseTime: metrics.business.api_response_time,
      processCpuUsage: metrics.process.cpu.percent,
    }
  }, [metrics])

  const cpuStatus = normalized.cpuUsage >= 90 ? "高压" : normalized.cpuUsage >= 70 ? "偏高" : "平稳"
  const memoryStatus = normalized.memoryUsage >= 85 ? "紧张" : normalized.memoryUsage >= 70 ? "偏高" : "平稳"
  const diskStatus = normalized.diskUsage >= 90 ? "紧张" : normalized.diskUsage >= 80 ? "预警" : "健康"

  if (loading && !metrics) {
    return (
      <GlassCard className="p-8">
        <EmptyState
          compact
          title="正在读取系统指标"
          description="系统会在拿到最新资源指标后展示 CPU、内存、磁盘与业务延迟。"
        />
      </GlassCard>
    )
  }

  if (error) {
    return (
      <GlassCard className="surface-tone-cinnabar p-5">
        <div className="flex items-center gap-2 text-tone-cinnabar">
          <AlertTriangle className="h-5 w-5" />
          <p className="text-sm leading-7">{error}</p>
        </div>
      </GlassCard>
    )
  }

  return (
    <div className="space-y-5">
      {showHeader ? (
        <PanelHeader
          title={
            <h2 className="section-title flex items-center gap-2">
              <Activity className="h-5 w-5" />
              系统指标
            </h2>
          }
          description="查看 CPU、内存、磁盘与业务延迟，判断当前系统是否适合继续运行。"
          meta={<StatusPill label="刷新" value={autoRefresh ? `${Math.round(refreshInterval / 1000)}s` : "手动"} tone="ink" />}
        />
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <ResourceMetricCard
          icon={Cpu}
          tone="indigo"
          title="CPU 占用"
          description="处理器负载"
          value={`${normalized.cpuUsage.toFixed(1)}%`}
          status={cpuStatus}
          progress={normalized.cpuUsage}
        />
        <ResourceMetricCard
          icon={Box}
          tone="plum"
          title="内存占用"
          description="运行内存"
          value={`${normalized.memoryUsage.toFixed(1)}%`}
          status={memoryStatus}
          progress={normalized.memoryUsage}
          detail={`${normalized.memoryUsedMb.toFixed(0)} MB / ${normalized.memoryTotalMb.toFixed(0)} MB`}
        />
        <ResourceMetricCard
          icon={HardDrive}
          tone="ochre"
          title="磁盘占用"
          description="存储压力"
          value={`${normalized.diskUsage.toFixed(1)}%`}
          status={diskStatus}
          progress={normalized.diskUsage}
          detail={`剩余 ${normalized.diskFreeGb.toFixed(1)} GB`}
        />
      </div>

      {detailed && (metrics as DetailedSystemMetrics | undefined)?.system ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <DetailMetricGrid
            icon={Server}
            title="进程资源"
            tone="indigo"
            items={[
              { label: "驻留内存", value: `${(metrics as DetailedSystemMetrics).process.memory.rss_mb} MB` },
              { label: "CPU 占用", value: `${(metrics as DetailedSystemMetrics).process.cpu.percent}%` },
              { label: "线程数", value: String((metrics as DetailedSystemMetrics).process.cpu.num_threads) },
              { label: "连接数", value: String((metrics as DetailedSystemMetrics).process.connections) },
            ]}
          />
          <DetailMetricGrid
            icon={Wifi}
            title="网络流量"
            tone="celadon"
            items={[
              { label: "发送字节", value: (metrics as DetailedSystemMetrics).network.io.bytes_sent.toLocaleString() },
              { label: "接收字节", value: (metrics as DetailedSystemMetrics).network.io.bytes_recv.toLocaleString() },
              { label: "发送包数", value: (metrics as DetailedSystemMetrics).network.io.packets_sent.toLocaleString() },
              { label: "接收包数", value: (metrics as DetailedSystemMetrics).network.io.packets_recv.toLocaleString() },
            ]}
          />
        </div>
      ) : null}

      {showLatency ? (
        <GlassCard className="space-y-4 p-5">
          <div className="flex items-center gap-3">
            <div className="surface-tone-celadon rounded-xl p-2">
              <Zap className="h-4 w-4" />
            </div>
            <div className="space-y-1">
              <div className="text-sm font-medium text-foreground/86">业务延迟</div>
              <p className="text-[0.88rem] leading-6 text-foreground/70">
                关注数据更新、委托执行和接口响应的节奏是否平稳。
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "数据更新", value: `${normalized.dataUpdateLatency.toFixed(1)} s` },
              { label: "委托执行", value: `${normalized.orderExecutionLatency.toFixed(3)} s` },
              { label: "接口响应", value: `${normalized.apiResponseTime.toFixed(3)} s` },
              { label: "进程 CPU", value: `${normalized.processCpuUsage.toFixed(1)}%` },
            ].map((item) => (
              <div key={item.label} className="data-panel-muted rounded-[18px] px-4 py-3">
                <div className="data-metric-label">{item.label}</div>
                <div className="mt-2 text-[1.08rem] font-semibold tracking-tight text-foreground">{item.value}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      ) : null}
    </div>
  )
}
