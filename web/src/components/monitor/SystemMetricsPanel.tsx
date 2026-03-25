"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, type DetailedSystemMetrics, type SystemMetrics } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { Activity, AlertTriangle, Box, Cpu, HardDrive, RefreshCw, Server, Wifi, Zap } from "lucide-react"
import { cn } from "@/lib/utils"

interface SystemMetricsPanelProps {
  detailed?: boolean
  autoRefresh?: boolean
  refreshInterval?: number
}

export function SystemMetricsPanel({
  detailed = false,
  autoRefresh = true,
  refreshInterval = 30000,
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
      const message = err instanceof Error ? err.message : "读取系统指标失败"
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

  const cpuUsage = normalized.cpuUsage
  const memoryUsage = normalized.memoryUsage
  const diskUsage = normalized.diskUsage

  const cpuStatus = cpuUsage >= 90 ? "高压" : cpuUsage >= 70 ? "偏高" : "平稳"
  const memoryStatus = memoryUsage >= 85 ? "紧张" : memoryUsage >= 70 ? "偏高" : "平稳"
  const diskStatus = diskUsage >= 90 ? "紧张" : diskUsage >= 80 ? "预警" : "健康"

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center p-12">
        <RefreshCw className="h-6 w-6 animate-spin text-foreground/50" />
      </div>
    )
  }

  if (error) {
    return (
      <GlassCard className="border-red-200 bg-red-50/50 p-6 dark:bg-red-950/20">
        <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
          <AlertTriangle className="h-5 w-5" />
          <p>{error}</p>
        </div>
      </GlassCard>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="flex items-center gap-2 text-xl font-semibold tracking-[-0.02em] text-foreground/90">
            <Activity className="h-5 w-5" />
            系统指标
          </h2>
          <p className="text-[13px] text-foreground/40">查看 CPU、内存、磁盘与业务延迟，判断系统是否适合继续运行。</p>
        </div>
        <Badge variant="secondary" className="text-[11px]">
          {autoRefresh ? "自动刷新" : "手动刷新"}
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <GlassCard className="p-5">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-lg p-2" style={{ backgroundColor: "rgba(111,124,142,0.10)", color: SONG_COLORS.indigo }}>
              <Cpu className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-foreground/70">CPU 占用</p>
              <p className="text-[11px] text-foreground/40">处理器负载</p>
            </div>
          </div>
          <div className="mb-2 flex items-end gap-2">
            <span className="text-3xl font-bold text-foreground">{cpuUsage.toFixed(1)}%</span>
            <span className="rounded-full px-2 py-0.5 text-[11px]" style={{ backgroundColor: "rgba(111,124,142,0.10)", color: SONG_COLORS.indigo }}>{cpuStatus}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${cpuUsage}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full", cpuUsage >= 90 ? "bg-[color:var(--market-up)]" : cpuUsage >= 70 ? "bg-[#B08E61]" : "bg-[#6F7C8E]")}
            />
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-lg p-2" style={{ backgroundColor: "rgba(122,105,115,0.10)", color: SONG_COLORS.plum }}>
              <Box className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-foreground/70">内存占用</p>
              <p className="text-[11px] text-foreground/40">运行内存</p>
            </div>
          </div>
          <div className="mb-2 flex items-end gap-2">
            <span className="text-3xl font-bold text-foreground">{memoryUsage.toFixed(1)}%</span>
            <span className="rounded-full px-2 py-0.5 text-[11px]" style={{ backgroundColor: "rgba(122,105,115,0.10)", color: SONG_COLORS.plum }}>{memoryStatus}</span>
          </div>
          <div className="mb-2 text-sm text-foreground/60">
            {normalized.memoryUsedMb.toFixed(0)} MB / {normalized.memoryTotalMb.toFixed(0)} MB
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${memoryUsage}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full", memoryUsage >= 85 ? "bg-[color:var(--market-up)]" : memoryUsage >= 70 ? "bg-[#B08E61]" : "bg-[#7A6973]")}
            />
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-lg p-2" style={{ backgroundColor: "rgba(176,142,97,0.10)", color: SONG_COLORS.ochre }}>
              <HardDrive className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-foreground/70">磁盘占用</p>
              <p className="text-[11px] text-foreground/40">存储压力</p>
            </div>
          </div>
          <div className="mb-2 flex items-end gap-2">
            <span className="text-3xl font-bold text-foreground">{diskUsage.toFixed(1)}%</span>
            <span className="rounded-full px-2 py-0.5 text-[11px]" style={{ backgroundColor: "rgba(176,142,97,0.10)", color: "#8C724C" }}>{diskStatus}</span>
          </div>
          <div className="mb-2 text-sm text-foreground/60">剩余 {normalized.diskFreeGb.toFixed(1)} GB</div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${diskUsage}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full", diskUsage >= 90 ? "bg-[color:var(--market-up)]" : diskUsage >= 80 ? "bg-[#B08E61]" : "bg-[color:var(--market-down)]")}
            />
          </div>
        </GlassCard>
      </div>

      {detailed && (metrics as DetailedSystemMetrics | undefined)?.system && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-foreground/40" />
              <p className="text-[13px] font-medium text-foreground/70">进程资源</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">RSS 内存</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.memory.rss_mb} MB</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">CPU</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.cpu.percent}%</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">线程数</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.cpu.num_threads}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">连接数</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.connections}</p>
              </div>
            </div>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Wifi className="h-4 w-4 text-foreground/40" />
              <p className="text-[13px] font-medium text-foreground/70">网络 I/O</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">发送字节</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.bytes_sent.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">接收字节</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.bytes_recv.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">发送包数</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.packets_sent.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">接收包数</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.packets_recv.toLocaleString()}</p>
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      <GlassCard className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Zap className="h-4 w-4 text-foreground/40" />
          <p className="text-[13px] font-medium text-foreground/70">业务延迟</p>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">数据更新</p>
            <p className="text-lg font-semibold text-foreground">{normalized.dataUpdateLatency.toFixed(1)} s</p>
          </div>
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">委托执行</p>
            <p className="text-lg font-semibold text-foreground">{normalized.orderExecutionLatency.toFixed(3)} s</p>
          </div>
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">接口响应</p>
            <p className="text-lg font-semibold text-foreground">{normalized.apiResponseTime.toFixed(3)} s</p>
          </div>
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">进程 CPU</p>
            <p className="text-lg font-semibold text-foreground">{normalized.processCpuUsage.toFixed(1)}%</p>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}
