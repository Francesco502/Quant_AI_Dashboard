"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { ChevronDown, LayoutDashboard, RefreshCw, Settings } from "lucide-react"

import { HealthStatus } from "@/components/monitor/HealthStatus"
import { AlertHistory } from "@/components/monitor/AlertHistory"
import { SystemMetricsPanel } from "@/components/monitor/SystemMetricsPanel"
import { NoteBlock } from "@/components/data/note-block"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="data-panel-muted rounded-[22px] px-4 py-3">
      <div className="data-metric-label">{label}</div>
      <div className="mt-2 text-[1.18rem] font-semibold tracking-tight text-foreground/90">{value}</div>
    </div>
  )
}

function SecondarySection({
  title,
  description,
  children,
  defaultOpen = false,
}: {
  title: string
  description: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details
      className="group overflow-hidden rounded-[28px] border border-black/[0.05] bg-[rgba(255,251,245,0.7)]"
      open={defaultOpen}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4">
        <div className="space-y-1">
          <div className="section-title">{title}</div>
          <p className="text-[0.88rem] leading-6 text-foreground/64">{description}</p>
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 text-foreground/50 transition-transform duration-200 group-open:rotate-180" />
      </summary>
      <div className="border-t border-black/[0.05] px-5 py-5">{children}</div>
    </details>
  )
}

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
      className="mx-auto max-w-7xl space-y-6 pb-10"
    >
      <GlassCard className="space-y-4 p-5 md:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl space-y-2">
            <h1 className="page-title flex items-center gap-2">
              <LayoutDashboard className="h-6 w-6" />
              系统监控
            </h1>
            <p className="page-subtitle">
              把运行健康、资源指标与告警记录收在同一处，先判断系统是否平稳，再决定是否继续研究与执行。
            </p>
          </div>

          <Button variant="outline" onClick={() => void loadStatus()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新状态
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <StatTile label="运行时长" value={formatUptime(uptime)} />
          <StatTile label="指标数" value={metricsCount.toString()} />
          <StatTile label="检查项" value={healthChecksCount.toString()} />
        </div>
      </GlassCard>

      <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
        <HealthStatus showDetailed={false} autoRefresh refreshInterval={30000} />

        <section className="space-y-3">
          <div className="space-y-1 px-1">
            <h2 className="section-title">资源结论</h2>
            <p className="text-[0.9rem] leading-7 text-foreground/66">
              先看 CPU、内存与磁盘是否平稳，详细资源与业务延迟放到第二层，避免首屏变成监控数据墙。
            </p>
          </div>
          <SystemMetricsPanel autoRefresh refreshInterval={15000} showHeader={false} showLatency={false} />
        </section>
      </div>

      <div className="space-y-4">
        <SecondarySection
          title="查看资源与健康明细"
          description="需要进一步排查时，再展开完整健康检查、资源细项与业务延迟。"
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <HealthStatus showDetailed autoRefresh refreshInterval={30000} />
            <SystemMetricsPanel detailed autoRefresh refreshInterval={15000} />
          </div>
        </SecondarySection>

        <SecondarySection
          title="查看告警历史与通道说明"
          description="把告警列表和通道配置一起折叠到底层，需要时再展开。"
        >
          <div className="space-y-6">
            <AlertHistory showFilters showStats autoRefresh refreshInterval={30000} />

            <GlassCard className="surface-tone-indigo p-4.5">
              <NoteBlock
                title="告警通道配置"
                icon={<Settings className="h-4 w-4 text-tone-indigo" />}
                tone="accent"
                className="border-0 bg-transparent p-0 shadow-none"
              >
                可通过环境变量配置邮件、Telegram 与飞书告警通道：
                <code className="mx-1 rounded bg-foreground/5 px-1.5 py-0.5 text-[0.76rem]">ALERT_EMAIL_SMTP_SERVER</code>
                <code className="mx-1 rounded bg-foreground/5 px-1.5 py-0.5 text-[0.76rem]">ALERT_TELEGRAM_BOT_TOKEN</code>
                <code className="mx-1 rounded bg-foreground/5 px-1.5 py-0.5 text-[0.76rem]">ALERT_FEISHU_WEBHOOK_URL</code>
              </NoteBlock>
            </GlassCard>
          </div>
        </SecondarySection>
      </div>
    </motion.div>
  )
}
