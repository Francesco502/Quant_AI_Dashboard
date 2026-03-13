"use client"

import { useState, useEffect, type ComponentType } from "react"
import { motion } from "framer-motion"
import { SystemMetricsPanel } from "@/components/monitor/SystemMetricsPanel"
import { HealthStatus } from "@/components/monitor/HealthStatus"
import { AlertHistory } from "@/components/monitor/AlertHistory"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Activity,
  Bell,
  Settings,
  RefreshCw,
  Clock,
  Database,
} from "lucide-react"

export default function SystemMonitorPage() {
  const [uptime, setUptime] = useState(0)
  const [metricsCount, setMetricsCount] = useState(0)
  const [healthChecksCount, setHealthChecksCount] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setUptime((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const loadStatus = async () => {
    try {
      const res = await api.monitoring.getMonitoringStatus()
      if (res.data) {
        setMetricsCount(res.data.metrics_collected || 0)
        setHealthChecksCount(res.data.health_checks || 0)
      }
    } catch (error) {
      console.error("Failed to load status:", error)
    }
  }

  useEffect(() => {
    const initialTimer = setTimeout(() => {
      void loadStatus()
    }, 0)
    const interval = setInterval(() => {
      void loadStatus()
    }, 30000)

    return () => {
      clearTimeout(initialTimer)
      clearInterval(interval)
    }
  }, [])

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = seconds % 60
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6 max-w-7xl mx-auto pb-8"
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90 flex items-center gap-2">
            <LayoutDashboard className="w-6 h-6" />
            System Monitor
          </h1>
          <p className="text-[13px] text-foreground/40">24/7 runtime health and alert monitoring.</p>
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge label="Uptime" value={formatUptime(uptime)} icon={Clock} color="blue" />
          <StatusBadge label="Metrics" value={metricsCount.toString()} icon={Activity} color="purple" />
          <StatusBadge label="Checks" value={healthChecksCount.toString()} icon={Database} color="emerald" />
          <button
            onClick={loadStatus}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors bg-foreground/5 hover:bg-foreground/10 rounded-lg"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground/90 flex items-center gap-2">
            <Activity className="w-4 h-4 text-foreground/40" />
            System Metrics
          </h2>
          <Badge variant="outline" className="text-[11px]">
            Realtime
          </Badge>
        </div>

        <SystemMetricsPanel detailed autoRefresh refreshInterval={15000} />
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground/90 flex items-center gap-2">
            <Database className="w-4 h-4 text-foreground/40" />
            Health Checks
          </h2>
          <Badge variant="outline" className="text-[11px]">
            {new Date().toLocaleTimeString("en-US", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </Badge>
        </div>

        <HealthStatus showDetailed autoRefresh refreshInterval={30000} />
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground/90 flex items-center gap-2">
            <Bell className="w-4 h-4 text-foreground/40" />
            Alert History
          </h2>
          <Badge variant="outline" className="text-[11px]">
            Recent
          </Badge>
        </div>

        <AlertHistory showFilters showStats autoRefresh refreshInterval={30000} />
      </section>

      <div className="pt-4">
        <GlassCard className="p-4 bg-blue-500/5 dark:bg-blue-900/10 border-blue-500/10">
          <div className="flex items-start gap-3">
            <div className="mt-1">
              <Settings className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            </div>
            <div className="space-y-1 flex-1">
              <p className="text-sm font-medium text-foreground/80">Alert Channel Configuration</p>
              <p className="text-xs text-foreground/60">
                Configure alert routing with env vars:
                <code className="mx-1 bg-foreground/5 px-1 py-0.5 rounded text-[10px]">ALERT_EMAIL_SMTP_SERVER</code>
                <code className="mx-1 bg-foreground/5 px-1 py-0.5 rounded text-[10px]">ALERT_TELEGRAM_BOT_TOKEN</code>
                <code className="mx-1 bg-foreground/5 px-1 py-0.5 rounded text-[10px]">ALERT_FEISHU_WEBHOOK_URL</code>
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </motion.div>
  )
}

interface StatusBadgeProps {
  label: string
  value: string
  icon: ComponentType<{ className?: string }>
  color: "blue" | "purple" | "emerald" | "amber" | "red"
}

function StatusBadge({ label, value, icon: Icon, color }: StatusBadgeProps) {
  const colorClasses = {
    blue: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    purple: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
    emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    red: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
  }

  return (
    <div className={cn("flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium", colorClasses[color])}>
      <Icon className="w-3.5 h-3.5" />
      <span className="flex items-center gap-1.5">
        {label}:
        <span className="font-mono text-[10px]">{value}</span>
      </span>
    </div>
  )
}
