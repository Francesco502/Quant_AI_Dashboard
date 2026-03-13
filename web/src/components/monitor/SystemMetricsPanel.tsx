"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, type DetailedSystemMetrics, type SystemMetrics } from "@/lib/api"
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
      const message = err instanceof Error ? err.message : "Failed to fetch system metrics"
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

  const cpuStatus = cpuUsage >= 90 ? "Critical" : cpuUsage >= 70 ? "High" : "Normal"
  const memoryStatus = memoryUsage >= 85 ? "Tight" : memoryUsage >= 70 ? "High" : "Normal"
  const diskStatus = diskUsage >= 90 ? "Low" : diskUsage >= 80 ? "Warning" : "Healthy"

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
            System Metrics
          </h2>
          <p className="text-[13px] text-foreground/40">CPU, memory, storage and business latency in near real-time.</p>
        </div>
        <Badge variant="secondary" className="text-[11px]">
          {autoRefresh ? "Auto Refresh" : "Manual Refresh"}
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <GlassCard className="p-5">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-lg bg-blue-500/10 p-2 text-blue-600 dark:text-blue-400">
              <Cpu className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-foreground/70">CPU Usage</p>
              <p className="text-[11px] text-foreground/40">Processor load</p>
            </div>
          </div>
          <div className="mb-2 flex items-end gap-2">
            <span className="text-3xl font-bold text-foreground">{cpuUsage.toFixed(1)}%</span>
            <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[11px] text-blue-600">{cpuStatus}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${cpuUsage}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full", cpuUsage >= 90 ? "bg-red-500" : cpuUsage >= 70 ? "bg-amber-500" : "bg-blue-500")}
            />
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-lg bg-purple-500/10 p-2 text-purple-600 dark:text-purple-400">
              <Box className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-foreground/70">Memory Usage</p>
              <p className="text-[11px] text-foreground/40">RAM consumption</p>
            </div>
          </div>
          <div className="mb-2 flex items-end gap-2">
            <span className="text-3xl font-bold text-foreground">{memoryUsage.toFixed(1)}%</span>
            <span className="rounded-full bg-purple-500/10 px-2 py-0.5 text-[11px] text-purple-600">{memoryStatus}</span>
          </div>
          <div className="mb-2 text-sm text-foreground/60">
            {normalized.memoryUsedMb.toFixed(0)} MB / {normalized.memoryTotalMb.toFixed(0)} MB
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${memoryUsage}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full", memoryUsage >= 85 ? "bg-red-500" : memoryUsage >= 70 ? "bg-amber-500" : "bg-purple-500")}
            />
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-lg bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400">
              <HardDrive className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-foreground/70">Disk Usage</p>
              <p className="text-[11px] text-foreground/40">Storage pressure</p>
            </div>
          </div>
          <div className="mb-2 flex items-end gap-2">
            <span className="text-3xl font-bold text-foreground">{diskUsage.toFixed(1)}%</span>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-600">{diskStatus}</span>
          </div>
          <div className="mb-2 text-sm text-foreground/60">{normalized.diskFreeGb.toFixed(1)} GB free</div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${diskUsage}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full", diskUsage >= 90 ? "bg-red-500" : diskUsage >= 80 ? "bg-amber-500" : "bg-emerald-500")}
            />
          </div>
        </GlassCard>
      </div>

      {detailed && (metrics as DetailedSystemMetrics | undefined)?.system && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-foreground/40" />
              <p className="text-[13px] font-medium text-foreground/70">Process Resources</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">RSS Memory</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.memory.rss_mb} MB</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">CPU</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.cpu.percent}%</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">Threads</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.cpu.num_threads}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">Connections</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).process.connections}</p>
              </div>
            </div>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Wifi className="h-4 w-4 text-foreground/40" />
              <p className="text-[13px] font-medium text-foreground/70">Network I/O</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">Bytes Sent</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.bytes_sent.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">Bytes Received</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.bytes_recv.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">Packets Sent</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.packets_sent.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-foreground/5 p-3">
                <p className="mb-1 text-[11px] text-foreground/40">Packets Received</p>
                <p className="text-lg font-semibold text-foreground">{(metrics as DetailedSystemMetrics).network.io.packets_recv.toLocaleString()}</p>
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      <GlassCard className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Zap className="h-4 w-4 text-foreground/40" />
          <p className="text-[13px] font-medium text-foreground/70">Business Latency</p>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">Data Update</p>
            <p className="text-lg font-semibold text-foreground">{normalized.dataUpdateLatency.toFixed(1)} s</p>
          </div>
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">Order Execution</p>
            <p className="text-lg font-semibold text-foreground">{normalized.orderExecutionLatency.toFixed(3)} s</p>
          </div>
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">API Response</p>
            <p className="text-lg font-semibold text-foreground">{normalized.apiResponseTime.toFixed(3)} s</p>
          </div>
          <div className="rounded-lg bg-foreground/5 p-3">
            <p className="mb-1 text-[11px] text-foreground/40">Process CPU</p>
            <p className="text-lg font-semibold text-foreground">{normalized.processCpuUsage.toFixed(1)}%</p>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}
