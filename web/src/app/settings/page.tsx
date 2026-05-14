"use client"

import { useCallback, useEffect, useState } from "react"
import { Archive, CheckCircle2, CircleDashed, ClipboardCheck, Database, Download, KeyRound, RefreshCw, RotateCcw, Wallet } from "lucide-react"

import { Button } from "@/components/ui/button"
import { GlassCard, CardDescription, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api, type BackupItem } from "@/lib/api"
import { useSettings } from "@/lib/settings-context"
import { formatCurrency } from "@/lib/utils"

type AccountSummary = {
  totalAssets: number
  cash: number
  marketValue: number
  initialCapital: number
}

type RestoreMode = "configs" | "user_files" | "database"
type PendingRestore = { filename: string; mode: RestoreMode } | null

function MetricTile({
  label,
  value,
  toneClass,
}: {
  label: string
  value: string
  toneClass?: string
}) {
  return (
    <div className="data-panel data-metric-card rounded-2xl p-5">
      <div className="data-metric-label">{label}</div>
      <div className={`mt-3 text-2xl font-semibold ${toneClass ?? "text-foreground/92"}`}>{value}</div>
    </div>
  )
}

function formatSize(bytes?: number) {
  if (!bytes) return "-"
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatDateTime(value?: string) {
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

function restoreModeLabel(mode: RestoreMode) {
  if (mode === "database") return "SQLite 数据库"
  if (mode === "configs") return "系统配置"
  return "导出文件与审计日志"
}

export default function SettingsPage() {
  const { dataSources, apiKeyStatus, configurationMode, isLoading } = useSettings()
  const [accountData, setAccountData] = useState<AccountSummary | null>(null)
  const [accountLoading, setAccountLoading] = useState(true)
  const [latestBackup, setLatestBackup] = useState<string | null>(null)
  const [backupCount, setBackupCount] = useState(0)
  const [backups, setBackups] = useState<BackupItem[]>([])
  const [backupLoading, setBackupLoading] = useState(false)
  const [backupMessage, setBackupMessage] = useState("")
  const [pendingRestore, setPendingRestore] = useState<PendingRestore>(null)

  const loadAccountData = useCallback(async () => {
    setAccountLoading(true)
    try {
      const paperAccount = await api.trading.paper.getAccount()
      const portfolio = paperAccount?.portfolio

      if (!portfolio) {
        setAccountData(null)
        return
      }

      setAccountData({
        totalAssets: Number(portfolio.total_assets || 0),
        cash: Number(portfolio.cash || 0),
        marketValue: Number(portfolio.market_value || 0),
        initialCapital: Number(paperAccount?.initial_capital || 0),
      })
    } catch {
      setAccountData(null)
    } finally {
      setAccountLoading(false)
    }
  }, [])

  const loadBackupData = useCallback(async () => {
    try {
      const payload = await api.backup.list()
      setBackupCount(payload.count)
      setBackups(payload.backups)
      setLatestBackup(payload.backups[0]?.filename ?? null)
    } catch {
      setBackupCount(0)
      setBackups([])
      setLatestBackup(null)
    }
  }, [])

  const createBackup = useCallback(async () => {
    setBackupLoading(true)
    setBackupMessage("")
    try {
      const result = await api.backup.create({
        include_database: true,
        include_configs: true,
        include_user_files: true,
      })
      setBackupMessage(`已创建备份：${result.filename}`)
      await loadBackupData()
    } catch (error) {
      setBackupMessage(error instanceof Error ? error.message : "创建备份失败")
    } finally {
      setBackupLoading(false)
    }
  }, [loadBackupData])

  const downloadBackup = useCallback(async (filename: string) => {
    setBackupMessage("")
    try {
      const blob = await api.backup.download(filename)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      setBackupMessage(error instanceof Error ? error.message : "下载备份失败")
    }
  }, [])

  const restoreBackup = useCallback(async () => {
    if (!pendingRestore) return
    setBackupLoading(true)
    setBackupMessage("")
    try {
      const result = await api.backup.restore({
        filename: pendingRestore.filename,
        restore_configs: pendingRestore.mode === "configs",
        restore_user_files: pendingRestore.mode === "user_files",
        restore_database: pendingRestore.mode === "database",
      })
      setBackupMessage(`已恢复 ${result.restored.length} 个文件：${result.filename}`)
      setPendingRestore(null)
      await loadBackupData()
    } catch (error) {
      setBackupMessage(error instanceof Error ? error.message : "恢复备份失败")
    } finally {
      setBackupLoading(false)
    }
  }, [loadBackupData, pendingRestore])

  useEffect(() => {
    void loadAccountData()
    void loadBackupData()
  }, [loadAccountData, loadBackupData])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h1 className="page-title">系统设置</h1>
          <p className="page-subtitle">正在读取设置…</p>
        </div>
        <GlassCard className="space-y-5">
          <CardTitle className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-tone-indigo" />
            初始化向导
          </CardTitle>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {["数据源优先级", "备份管理", "行情 API Key"].map((label) => (
              <div key={label} className="data-panel-muted rounded-2xl px-4 py-4">
                <div className="text-sm font-medium text-foreground/86">{label}</div>
                <div className="mt-3 h-2 w-2/3 animate-pulse rounded-full bg-foreground/10" />
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="page-title">系统设置</h1>
        <p className="page-subtitle">只保留需要配置的账户与数据源项；运行健康看系统监控，自动执行看模拟交易。</p>
      </div>

      <GlassCard className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5 text-tone-indigo" />
              初始化向导
            </CardTitle>
            <CardDescription>
              2.2.1 把首次使用必须确认的事项集中到这里：账号、数据源、密钥、备份和自动纸面执行开关。
            </CardDescription>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {[
            { label: "管理员账户", ok: true, detail: "已进入受保护后台，可继续配置个人系统。" },
            { label: "数据源优先级", ok: dataSources.length > 0, detail: dataSources.length > 0 ? dataSources.join(" / ") : "尚未读取到服务器数据源。" },
            { label: "行情 API Key", ok: apiKeyStatus.Tushare || apiKeyStatus.AlphaVantage, detail: apiKeyStatus.Tushare || apiKeyStatus.AlphaVantage ? "至少一个行情密钥可用。" : "建议配置 Tushare 或 Alpha Vantage。" },
            { label: "备份位置", ok: backupCount > 0, detail: latestBackup ? `最近备份：${latestBackup}` : "尚未发现备份，建议先创建一次。" },
            { label: "LLM/AI 研究", ok: true, detail: "模型连通性在 LLM 研究工作台验证，设置页只保留初始化提醒。" },
            { label: "自动纸面执行", ok: true, detail: "默认不做真实交易；纸面自动执行仍需在模拟交易页显式启用。" },
          ].map((item) => (
            <div key={item.label} className="data-panel-muted rounded-2xl px-4 py-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground/86">
                {item.ok ? <CheckCircle2 className="h-4 w-4 text-tone-celadon" /> : <CircleDashed className="h-4 w-4 text-tone-ochre" />}
                {item.label}
              </div>
              <p className="mt-2 text-xs leading-6 text-muted-foreground">{item.detail}</p>
            </div>
          ))}
        </div>
        {backupMessage ? <div className="rounded-2xl border border-border/60 px-4 py-3 text-sm text-muted-foreground">{backupMessage}</div> : null}
      </GlassCard>

      <GlassCard className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <CardTitle className="flex items-center gap-2">
              <Archive className="h-5 w-5 text-tone-ochre" />
              备份管理
            </CardTitle>
            <CardDescription>
              备份包含 SQLite 数据库、配置文件、导出文件和审计日志。恢复数据库会覆盖当前数据，请先下载当前备份。
            </CardDescription>
          </div>
          <Button onClick={() => void createBackup()} disabled={backupLoading}>
            {backupLoading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
            创建完整备份
          </Button>
        </div>

        {backups.length > 0 ? (
          <div className="space-y-3">
            {backups.slice(0, 5).map((backup) => (
              <div
                key={backup.filename}
                className="rounded-[24px] border border-border/60 bg-background/58 px-4 py-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0">
                    <div className="truncate font-mono text-sm font-semibold text-foreground/88">{backup.filename}</div>
                    <div className="mt-1 text-xs leading-5 text-muted-foreground">
                      {formatSize(backup.size_bytes)} · {formatDateTime(backup.created_at)} · 版本{" "}
                      {backup.manifest?.version ? String(backup.manifest.version) : "-"}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => void downloadBackup(backup.filename)}>
                      <Download className="mr-2 h-4 w-4" />
                      下载
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setPendingRestore({ filename: backup.filename, mode: "configs" })}>
                      <RotateCcw className="mr-2 h-4 w-4" />
                      恢复配置
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setPendingRestore({ filename: backup.filename, mode: "user_files" })}>
                      恢复文件
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => setPendingRestore({ filename: backup.filename, mode: "database" })}>
                      <Database className="mr-2 h-4 w-4" />
                      恢复数据库
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="data-empty">还没有备份。发布前建议先创建一次完整备份。</div>
        )}
      </GlassCard>

      <Tabs defaultValue="account" className="space-y-6">
        <TabsList>
          <TabsTrigger value="account" className="gap-2">
            <Wallet className="h-4 w-4" />
            模拟账户
          </TabsTrigger>
          <TabsTrigger value="data" className="gap-2">
            <KeyRound className="h-4 w-4" />
            数据源
          </TabsTrigger>
        </TabsList>

        <TabsContent value="account">
          <GlassCard className="space-y-6">
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-2">
                模拟账户概览
                <HelpTooltip content="显示当前主模拟账户的总资产、持仓市值、可用现金与初始资金，用于快速确认账户状态。" />
              </CardTitle>
              <CardDescription>优先确认账户权益结构，再决定是否继续执行策略、回测或自动调度。</CardDescription>
            </div>

            {accountLoading ? (
              <div className="data-empty">正在读取账户数据…</div>
            ) : accountData ? (
              <>
                <div className="grid gap-4 md:grid-cols-4">
                  <MetricTile label="总资产" value={formatCurrency(accountData.totalAssets)} />
                  <MetricTile label="持仓市值" value={formatCurrency(accountData.marketValue)} toneClass="text-tone-indigo" />
                  <MetricTile label="可用现金" value={formatCurrency(accountData.cash)} />
                  <MetricTile label="初始资金" value={formatCurrency(accountData.initialCapital)} />
                </div>
                <div className="flex justify-end">
                  <Button variant="outline" onClick={() => void loadAccountData()}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    刷新账户数据
                  </Button>
                </div>
              </>
            ) : (
              <div className="data-empty">当前没有可用的模拟账户，请先前往模拟交易页面创建或恢复账户。</div>
            )}
          </GlassCard>
        </TabsContent>

        <TabsContent value="data">
          <GlassCard className="space-y-6">
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-2">
                服务器统一数据源
                <HelpTooltip content="数据源优先级与 API Key 仅从服务端环境变量读取，前端不再允许用户覆盖。" />
              </CardTitle>
              <CardDescription>这部分不追求可配置性，而追求稳定性和可复现性。</CardDescription>
            </div>

            <div className="space-y-3">
              {dataSources.map((source, index) => (
                <div key={source} className="data-panel-muted flex items-center justify-between rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-black/5 text-xs font-medium text-foreground/70">
                      {index + 1}
                    </span>
                    <span className="font-medium">{source}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">服务器锁定</span>
                </div>
              ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="data-panel rounded-2xl p-4">
                <div className="text-sm font-medium text-foreground/85">配置模式</div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {configurationMode === "env_locked" ? "环境变量锁定模式" : "未知模式"}
                </div>
                <p className="mt-2 text-xs leading-6 text-muted-foreground">
                  如需变更优先级或密钥，请修改服务端 `.env` 并重启后端服务。
                </p>
              </div>

              <div className="data-panel rounded-2xl p-4">
                <div className="text-sm font-medium text-foreground/85">密钥状态</div>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span>Tushare Token</span>
                    <span className={apiKeyStatus.Tushare ? "text-tone-celadon" : "text-tone-cinnabar"}>
                      {apiKeyStatus.Tushare ? "已配置" : "未配置"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Alpha Vantage Key</span>
                    <span className={apiKeyStatus.AlphaVantage ? "text-tone-celadon" : "text-tone-cinnabar"}>
                      {apiKeyStatus.AlphaVantage ? "已配置" : "未配置"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </GlassCard>
        </TabsContent>
      </Tabs>

      <Dialog open={Boolean(pendingRestore)} onOpenChange={(open) => !open && setPendingRestore(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>确认恢复备份</DialogTitle>
            <DialogDescription>
              将从 {pendingRestore?.filename} 恢复 {pendingRestore ? restoreModeLabel(pendingRestore.mode) : ""}。
              {pendingRestore?.mode === "database"
                ? " 这会覆盖当前 SQLite 数据库，建议先创建并下载当前备份。"
                : " 当前操作只恢复所选文件类型。"}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingRestore(null)}>
              取消
            </Button>
            <Button
              variant={pendingRestore?.mode === "database" ? "destructive" : "default"}
              onClick={() => void restoreBackup()}
              disabled={backupLoading}
            >
              {backupLoading ? "恢复中…" : "确认恢复"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
