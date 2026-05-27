"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  Archive,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  DatabaseZap,
  History,
  RefreshCw,
  ScanSearch,
  Sparkles,
  WalletCards,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardDescription, CardTitle, GlassCard } from "@/components/ui/card"
import {
  api,
  type AuditEvent,
  type BackupItem,
  type DailyWorkbenchAction,
  type DailyWorkbenchSummary,
  type DataFreshnessItem,
} from "@/lib/api"
import { cn, formatCurrency } from "@/lib/utils"

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatSize(bytes?: number) {
  if (!bytes || bytes <= 0) return "-"
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function priorityVariant(priority: DailyWorkbenchAction["priority"]) {
  if (priority === "high") return "destructive" as const
  if (priority === "medium") return "warning" as const
  return "outline" as const
}

function FreshnessBadge({ item }: { item: DataFreshnessItem }) {
  return (
    <Badge variant={item.is_stale ? "destructive" : "success"}>
      {item.is_stale ? "过期" : "可用"} · {item.source}
    </Badge>
  )
}

function ActionCard({ action }: { action: DailyWorkbenchAction }) {
  const isHigh = action.priority === "high"
  return (
    <GlassCard
      className={cn(
        "group flex h-full flex-col justify-between gap-5 p-6 transition-all duration-300 relative overflow-hidden",
        isHigh && "border-[rgba(var(--rgb-cinnabar),0.18)] dark:border-[rgba(var(--rgb-cinnabar),0.3)] shadow-[0_8px_20px_rgba(182,69,60,0.03)] dark:shadow-[0_8px_24px_rgba(182,69,60,0.08)]"
      )}
    >
      {isHigh && (
        <div className="absolute top-0 left-0 h-1 w-full bg-[rgb(var(--rgb-cinnabar))]" />
      )}
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgba(var(--rgb-indigo),0.1)] text-tone-indigo transition-transform duration-300 group-hover:scale-105 group-hover:rotate-3">
            {action.kind === "scan" ? (
              <ScanSearch className="h-5.5 w-5.5" />
            ) : action.kind === "data" ? (
              <DatabaseZap className="h-5.5 w-5.5" />
            ) : action.kind === "trade" ? (
              <WalletCards className="h-5.5 w-5.5" />
            ) : (
              <Sparkles className="h-5.5 w-5.5" />
            )}
          </div>
          <Badge
            variant={priorityVariant(action.priority)}
            className={cn(isHigh && "animate-pulse")}
          >
            {action.priority === "high" ? "优先任务" : "日常任务"}
          </Badge>
        </div>
        <div className="space-y-1.5">
          <CardTitle className="text-lg tracking-wide font-semibold text-foreground/92">{action.title}</CardTitle>
          <CardDescription className="leading-relaxed text-[13px]">{action.description}</CardDescription>
        </div>
      </div>
      <Button asChild variant={isHigh ? "default" : "outline"} className="w-full justify-between group/btn">
        <Link href={action.href ?? ""}>
          进入处理
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover/btn:translate-x-1" />
        </Link>
      </Button>
    </GlassCard>
  )
}

function WorkbenchLoadingSkeleton() {
  const steps = [
    "资产与收益",
    "数据新鲜度",
    "纸面账户",
    "审计与备份",
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 md:p-10">
      <div className="space-y-2">
        <h1 className="page-title font-serif">日常决策工作台</h1>
        <p className="page-subtitle">正在汇总今日决策上下文...</p>
      </div>
      <GlassCard className="space-y-6 p-6 md:p-8 shadow-neon-ochre">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[rgba(var(--rgb-ochre),0.10)]">
            <RefreshCw className="h-5 w-5 animate-spin text-tone-ochre" />
          </div>
          <div>
            <div className="text-base font-semibold text-foreground tracking-wide">正在汇总今日决策上下文</div>
            <div className="mt-1 text-sm text-muted-foreground">正在并行加载多源资产、AkShare 实时数据、纸面交易账户及系统审计日志。</div>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => (
            <div
              key={step}
              className="rounded-[24px] border border-border/50 bg-background/40 p-5 shadow-[0_4px_16px_rgba(0,0,0,0.02)] dark:shadow-[0_4px_16px_rgba(0,0,0,0.15)] relative overflow-hidden"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-foreground/80">{step}</span>
                <Badge variant={index === 0 ? "warning" : "secondary"} className="text-[10px]">
                  {index === 0 ? "读取中" : "等待中"}
                </Badge>
              </div>
              <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-foreground/5 skeleton" />
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}

export default function DailyWorkbenchPage() {
  const [summary, setSummary] = useState<DailyWorkbenchSummary | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [backups, setBackups] = useState<BackupItem[]>([])
  const [loading, setLoading] = useState(true)
  const [backupLoading, setBackupLoading] = useState(false)
  const [error, setError] = useState("")
  const [backupMessage, setBackupMessage] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const [nextSummary, auditPayload, backupPayload] = await Promise.all([
        api.dailyWorkbench.getSummary(),
        api.audit.listEvents({ limit: 8 }).catch(() => ({ events: [] })),
        api.backup.list().catch(() => ({ backups: [] })),
      ])
      setSummary(nextSummary)
      setEvents(auditPayload.events || [])
      setBackups(backupPayload.backups || [])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "读取日常决策工作台失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const staleItems = useMemo(
    () => summary?.data_freshness.items.filter((item) => item.is_stale) ?? [],
    [summary],
  )
  const freshItems = useMemo(
    () => summary?.data_freshness.items.filter((item) => !item.is_stale) ?? [],
    [summary],
  )
  const latestBackup = backups[0]

  const createBackup = async () => {
    setBackupLoading(true)
    setBackupMessage("")
    try {
      const backup = await api.backup.create({
        include_database: true,
        include_configs: true,
        include_user_files: true,
      })
      setBackupMessage(`已创建备份 ${backup.filename}，大小 ${formatSize(backup.size_bytes)}。`)
      await load()
    } catch (requestError) {
      setBackupMessage(requestError instanceof Error ? requestError.message : "创建备份失败")
    } finally {
      setBackupLoading(false)
    }
  }

  if (loading) {
    return <WorkbenchLoadingSkeleton />
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 md:p-10">
      <section className="overflow-hidden rounded-[32px] border border-[rgba(var(--rgb-ink),0.08)] bg-[linear-gradient(135deg,rgba(var(--rgb-xuan),0.92),rgba(var(--rgb-celadon),0.13),rgba(var(--rgb-ochre),0.12))] p-6 shadow-[0_18px_48px_rgba(41,33,25,0.06)] md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <Badge variant="info" className="w-fit">
              2.2.1 日常入口
            </Badge>
            <h1 className="page-title">日常决策工作台</h1>
            <p className="page-subtitle">
              每天先看数据是否新鲜，再看市场、候选、AI 判断、回测和纸面账户，不再在多个页面之间手动串流程。
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => void load()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新上下文
            </Button>
            <Button asChild>
              <Link href="/market-scanner">
                开始今日扫描
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {error ? (
        <div className="surface-tone-cinnabar rounded-[24px] border px-4 py-3 text-sm leading-7">{error}</div>
      ) : null}

      {summary ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <GlassCard className="p-5">
              <div className="flex items-center justify-between">
                <span className="data-metric-label">资产规模</span>
                <WalletCards className="h-4 w-4 text-tone-celadon" />
              </div>
              <div className="mt-3 text-2xl font-semibold">{formatCurrency(summary.asset_summary?.total_market_value ?? 0)}</div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{summary.asset_summary?.asset_count ?? 0} 个个人资产纳入判断。</p>
            </GlassCard>
            <GlassCard className="p-5">
              <div className="flex items-center justify-between">
                <span className="data-metric-label">数据新鲜度</span>
                {staleItems.length ? (
                  <AlertTriangle className="h-4 w-4 text-tone-cinnabar" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-tone-celadon" />
                )}
              </div>
              <div className="mt-3 text-2xl font-semibold">{staleItems.length ? `${staleItems.length} 个过期` : "可执行"}</div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{freshItems.length} 个标的数据在可接受窗口内。</p>
            </GlassCard>
            <GlassCard className="p-5">
              <div className="flex items-center justify-between">
                <span className="data-metric-label">纸面账户</span>
                <WalletCards className="h-4 w-4 text-tone-indigo" />
              </div>
              <div className="mt-3 text-2xl font-semibold">
                {summary.paper_account?.found ? formatCurrency(summary.paper_account.total_assets) : "未创建"}
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                现金 {formatCurrency(summary.paper_account?.cash ?? 0)}，持仓 {formatCurrency(summary.paper_account?.position_value ?? 0)}。
              </p>
            </GlassCard>
            <GlassCard className="p-5">
              <div className="flex items-center justify-between">
                <span className="data-metric-label">最后汇总</span>
                <ClipboardList className="h-4 w-4 text-tone-ochre" />
              </div>
              <div className="mt-3 text-2xl font-semibold">{formatDateTime(summary.as_of)}</div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">用于今天的看盘、扫描、复盘和备份判断。</p>
            </GlassCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            {summary.next_actions.map((action) => (
              <ActionCard key={`${action.kind}-${action.href}`} action={action} />
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <GlassCard className="space-y-5 p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle>数据来源与新鲜度</CardTitle>
                  <CardDescription className="mt-2">
                    预测、扫描和回测会优先检查这些状态；过期或缺失数据需要先更新，避免用旧样本做决策。
                  </CardDescription>
                </div>
                <Button asChild variant="outline">
                  <Link href="/settings">
                    数据源设置
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
              <div className="space-y-3">
                {(summary.data_freshness.items.length ? summary.data_freshness.items.slice(0, 8) : []).map((item) => (
                  <div key={item.ticker} className="flex flex-col gap-3 rounded-[22px] border border-border/60 bg-background/58 px-4 py-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="font-mono text-sm font-semibold">{item.ticker}</div>
                      <div className="mt-1 text-xs leading-5 text-muted-foreground">
                        最后日期 {item.last_date ?? "-"}，距今 {item.age_days ?? "-"} 天。{item.message}
                      </div>
                    </div>
                    <FreshnessBadge item={item} />
                  </div>
                ))}
                {summary.data_freshness.items.length === 0 ? (
                  <div className="data-empty">当前没有个人资产标的可检查。先维护个人资产或资产池。</div>
                ) : null}
              </div>
            </GlassCard>

            <GlassCard className="space-y-5 p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle>备份与恢复</CardTitle>
                  <CardDescription className="mt-2">
                    个人系统最重要的是可恢复。建议每次大批量导入、策略模板调整或交易复盘后创建备份。
                  </CardDescription>
                </div>
                <Button onClick={() => void createBackup()} disabled={backupLoading}>
                  {backupLoading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
                  一键备份
                </Button>
              </div>
              {backupMessage ? (
                <div className="rounded-[20px] border border-border/60 bg-background/58 px-4 py-3 text-sm leading-6 text-foreground/72">
                  {backupMessage}
                </div>
              ) : null}
              <div className="rounded-[22px] border border-border/60 bg-background/58 px-4 py-3">
                <div className="text-sm font-medium text-foreground/86">最近备份</div>
                <div className="mt-2 text-sm leading-6 text-muted-foreground">
                  {latestBackup
                    ? `${latestBackup.filename} · ${formatSize(latestBackup.size_bytes)} · ${formatDateTime(latestBackup.created_at)}`
                    : "暂无可用备份或当前账号无备份权限。"}
                </div>
              </div>
            </GlassCard>
          </div>

          <GlassCard className="space-y-5 p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>操作审计与复盘日志</CardTitle>
                <CardDescription className="mt-2">
                  资产修改、扫描、预测、回测、备份和纸面订单都会沉淀到同一条复盘时间线。
                </CardDescription>
              </div>
              <Badge variant="outline">{events.length} 条最近记录</Badge>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {events.map((event) => (
                <div key={`${event.timestamp}-${event.action}-${event.resource}`} className="rounded-[22px] border border-border/60 bg-background/58 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <History className="h-4 w-4 text-tone-indigo" />
                      {event.action}
                    </div>
                    <Badge variant={event.success === false ? "destructive" : "outline"}>
                      {event.success === false ? "失败" : "成功"}
                    </Badge>
                  </div>
                  <div className="mt-2 text-sm text-foreground/72">{event.resource}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatDateTime(event.timestamp)}</div>
                </div>
              ))}
              {events.length === 0 ? <div className="data-empty md:col-span-2">暂无复盘日志。执行扫描、预测、回测或资产维护后会自动记录。</div> : null}
            </div>
          </GlassCard>
        </>
      ) : null}
    </div>
  )
}
