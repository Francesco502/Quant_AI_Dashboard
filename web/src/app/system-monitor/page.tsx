"use client"

import { useState, useEffect, type ComponentType } from "react"
import { motion } from "framer-motion"
import { SystemMetricsPanel } from "@/components/monitor/SystemMetricsPanel"
import { HealthStatus } from "@/components/monitor/HealthStatus"
import { AlertHistory } from "@/components/monitor/AlertHistory"
import { GlassCard } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
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
            系统监控
          </h1>
          <p className="text-[13px] text-foreground/40">查看运行健康、指标状态与告警记录，便于日常教学与维护。</p>
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge label="运行时长" value={formatUptime(uptime)} icon={Clock} color="ink" />
          <StatusBadge label="指标数" value={metricsCount.toString()} icon={Activity} color="plum" />
          <StatusBadge label="检查项" value={healthChecksCount.toString()} icon={Database} color="celadon" />
          <button
            onClick={loadStatus}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors bg-foreground/5 hover:bg-foreground/10 rounded-lg"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            刷新
          </button>
        </div>
      </div>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground/90 flex items-center gap-2">
            <Activity className="w-4 h-4 text-foreground/40" />
            系统指标
          </h2>
          <Badge variant="outline" className="text-[11px]">
            实时
          </Badge>
        </div>

        <SystemMetricsPanel detailed autoRefresh refreshInterval={15000} />
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground/90 flex items-center gap-2">
            <Database className="w-4 h-4 text-foreground/40" />
            健康检查
          </h2>
          <Badge variant="outline" className="text-[11px]">
            {new Date().toLocaleTimeString("zh-CN", {
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
            告警历史
          </h2>
          <Badge variant="outline" className="text-[11px]">
            最近
          </Badge>
        </div>

        <AlertHistory showFilters showStats autoRefresh refreshInterval={30000} />
      </section>

      <div className="pt-4">
        <GlassCard className="p-4 border-[#6F7C8E]/12 bg-[rgba(111,124,142,0.06)]">
          <div className="flex items-start gap-3">
            <div className="mt-1">
              <Settings className="w-4 h-4" style={{ color: SONG_COLORS.indigo }} />
            </div>
            <div className="space-y-1 flex-1">
              <p className="text-sm font-medium text-foreground/80">告警通道配置</p>
              <p className="text-xs text-foreground/60">
                可通过环境变量配置邮件、Telegram 与飞书告警通道：
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
  color: "ink" | "plum" | "celadon" | "ochre" | "cinnabar"
}

function StatusBadge({ label, value, icon: Icon, color }: StatusBadgeProps) {
  const colorClasses = {
    ink: "border-[#4D4742]/16 bg-[rgba(77,71,66,0.08)] text-[#4D4742]",
    plum: "border-[#7A6973]/18 bg-[rgba(122,105,115,0.10)] text-[#7A6973]",
    celadon: "border-[#4D7358]/18 bg-[rgba(77,115,88,0.10)] text-[#4D7358]",
    ochre: "border-[#B08E61]/18 bg-[rgba(176,142,97,0.10)] text-[#8C724C]",
    cinnabar: "border-[#B6453C]/18 bg-[rgba(182,69,60,0.10)] text-[#B6453C]",
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
