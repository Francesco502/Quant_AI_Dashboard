"use client"

import { useCallback, useEffect, useState } from "react"
import { KeyRound, RefreshCw, Server, ShieldCheck, Wallet } from "lucide-react"

import { api, getEffectiveApiBaseUrl, type AutoTradingStatusResponse } from "@/lib/api"
import { useSettings } from "@/lib/settings-context"
import { Button } from "@/components/ui/button"
import { GlassCard, CardDescription, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import { formatCurrency } from "@/lib/utils"

type AccountSummary = {
  totalAssets: number
  cash: number
  marketValue: number
  initialCapital: number
}

type HealthSummary = {
  online: boolean
  latencyMs: number
  securityReady: boolean
  securityIssues: string[]
  errorHint?: string
}

type DaemonSummary = {
  running: boolean
  enabled: boolean
  lastStartedAt?: string
  lastTradingRun?: string
  lastError?: string | null
}

const EMPTY_HEALTH: HealthSummary = {
  online: false,
  latencyMs: 0,
  securityReady: false,
  securityIssues: [],
}

function formatDateTime(value?: string | null) {
  if (!value) return "暂无"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

export default function SettingsPage() {
  const { dataSources, apiKeyStatus, configurationMode, isLoading } = useSettings()
  const [accountData, setAccountData] = useState<AccountSummary | null>(null)
  const [accountLoading, setAccountLoading] = useState(true)
  const [healthStatus, setHealthStatus] = useState<HealthSummary>(EMPTY_HEALTH)
  const [healthLoading, setHealthLoading] = useState(true)
  const [daemonStatus, setDaemonStatus] = useState<DaemonSummary>({ running: false, enabled: false })

  const loadAccountData = useCallback(async () => {
    setAccountLoading(true)
    try {
      const paperAccount = await api.trading.paper.getAccount()
      const autoStatus = await api.trading.auto.getStatus().catch(() => null as AutoTradingStatusResponse | null)

      const portfolio = paperAccount?.portfolio
      if (!portfolio) {
        setAccountData(null)
        return
      }

      setAccountData({
        totalAssets: Number(portfolio.total_assets || 0),
        cash: Number(portfolio.cash || 0),
        marketValue: Number(portfolio.market_value || 0),
        initialCapital: Number(
          autoStatus?.account?.initial_capital ??
            autoStatus?.config?.initial_capital ??
            0,
        ),
      })
    } catch {
      setAccountData(null)
    } finally {
      setAccountLoading(false)
    }
  }, [])

  const checkHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      const base = getEffectiveApiBaseUrl()
      const start = performance.now()
      const response = await fetch(`${base}/health`)
      const latencyMs = Math.round(performance.now() - start)
      const payload = (await response.json()) as {
        security?: { ready?: boolean; issues?: string[] }
      }

      setHealthStatus({
        online: response.ok,
        latencyMs,
        securityReady: Boolean(payload.security?.ready),
        securityIssues: payload.security?.issues || [],
      })
    } catch (error) {
      setHealthStatus({
        online: false,
        latencyMs: 0,
        securityReady: false,
        securityIssues: [],
        errorHint: error instanceof Error ? error.message : "网络错误",
      })
    } finally {
      setHealthLoading(false)
    }
  }, [])

  const loadDaemonStatus = useCallback(async () => {
    try {
      const response = await api.trading.auto.getStatus()
      setDaemonStatus({
        running: Boolean(response.daemon?.daemon_running),
        enabled: Boolean(response.config?.enabled),
        lastStartedAt: response.daemon?.last_started_at,
        lastTradingRun: response.daemon?.last_trading_run,
        lastError: response.daemon?.last_trading_error ?? null,
      })
    } catch {
      setDaemonStatus({ running: false, enabled: false })
    }
  }, [])

  useEffect(() => {
    void loadAccountData()
    void checkHealth()
    void loadDaemonStatus()
  }, [checkHealth, loadAccountData, loadDaemonStatus])

  if (isLoading) {
    return <div className="p-10 text-center text-sm text-muted-foreground">正在读取设置…</div>
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">系统设置</h1>
        <p className="text-sm text-muted-foreground">
          查看模拟账户概览、后端运行状态以及由服务器统一管理的数据源配置。
        </p>
      </div>

      <Tabs defaultValue="account" className="space-y-6">
        <TabsList>
          <TabsTrigger value="account" className="gap-2">
            <Wallet className="h-4 w-4" />
            模拟账户
          </TabsTrigger>
          <TabsTrigger value="daemon" className="gap-2">
            <Server className="h-4 w-4" />
            后台任务
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
                <HelpTooltip content="这里显示当前主模拟账户的总资产、持仓市值、可用现金与初始资金，用于快速确认账户状态。" />
              </CardTitle>
              <CardDescription>用于练习、验证策略与观察自动交易结果的虚拟账户。</CardDescription>
            </div>

            {accountLoading ? (
              <div className="py-10 text-center text-sm text-muted-foreground">正在读取账户数据…</div>
            ) : accountData ? (
              <>
                <div className="grid gap-4 md:grid-cols-4">
                  <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-5">
                    <div className="text-sm text-muted-foreground">总资产</div>
                    <div className="mt-2 text-2xl font-semibold">{formatCurrency(accountData.totalAssets)}</div>
                  </div>
                  <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-5">
                    <div className="text-sm text-muted-foreground">持仓市值</div>
                    <div className="mt-2 text-2xl font-semibold text-[#6F7C8E]">
                      {formatCurrency(accountData.marketValue)}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-5">
                    <div className="text-sm text-muted-foreground">可用现金</div>
                    <div className="mt-2 text-2xl font-semibold">{formatCurrency(accountData.cash)}</div>
                  </div>
                  <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-5">
                    <div className="text-sm text-muted-foreground">初始资金</div>
                    <div className="mt-2 text-2xl font-semibold">{formatCurrency(accountData.initialCapital)}</div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button variant="outline" onClick={() => void loadAccountData()}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    刷新账户数据
                  </Button>
                </div>
              </>
            ) : (
              <div className="py-10 text-center text-sm text-muted-foreground">
                当前没有可用的模拟账户，请先前往模拟交易页面创建或恢复账户。
              </div>
            )}
          </GlassCard>
        </TabsContent>

        <TabsContent value="daemon">
          <GlassCard className="space-y-6">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <CardTitle className="flex items-center gap-2">
                  运行状态
                  <HelpTooltip content="这里聚合显示 API 可达性、发布安全就绪状态以及后台守护进程的最近执行信息。" />
                </CardTitle>
                <CardDescription>用于确认发布环境是否在线、是否安全就绪，以及自动交易是否正在调度。</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => { void checkHealth(); void loadDaemonStatus() }} disabled={healthLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {healthLoading ? "检测中…" : "刷新状态"}
              </Button>
            </div>

            <div className="space-y-4">
              <div className={`flex items-center justify-between rounded-2xl border p-4 ${healthStatus.online ? "border-[#4D7358]/20 bg-[#4D7358]/8" : "border-[#B6453C]/20 bg-[#B6453C]/8"}`}>
                <div className="flex items-center gap-3">
                  <div className={`h-2.5 w-2.5 rounded-full ${healthStatus.online ? "bg-[#4D7358]" : "bg-[#B6453C]"}`} />
                  <span className="font-medium">API 服务</span>
                </div>
                <span className="text-sm">
                  {healthLoading ? "检测中…" : healthStatus.online ? `运行中（${healthStatus.latencyMs}ms）` : "离线"}
                </span>
              </div>

              <div className={`flex items-center justify-between rounded-2xl border p-4 ${healthStatus.securityReady ? "border-[#4D7358]/20 bg-[#4D7358]/8" : "border-[#B6453C]/20 bg-[#B6453C]/8"}`}>
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-4 w-4" />
                  <span className="font-medium">发布安全</span>
                </div>
                <span className="text-sm">{healthStatus.securityReady ? "已就绪" : "未就绪"}</span>
              </div>

              {healthStatus.securityIssues.length > 0 ? (
                <div className="rounded-2xl border border-[#B6453C]/15 bg-[#B6453C]/6 px-4 py-3 text-sm text-[#B6453C]">
                  {healthStatus.securityIssues.join("；")}
                </div>
              ) : null}

              {healthStatus.errorHint ? (
                <div className="rounded-2xl border border-[#B6453C]/15 bg-[#B6453C]/6 px-4 py-3 text-sm text-[#B6453C]">
                  健康检查失败：{healthStatus.errorHint}
                </div>
              ) : null}

              <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-4 text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-foreground/85">守护进程</span>
                  <span>{daemonStatus.running ? "运行中" : daemonStatus.enabled ? "待调度" : "未启用"}</span>
                </div>
                <div className="mt-3 space-y-1">
                  <div>最近启动：{formatDateTime(daemonStatus.lastStartedAt)}</div>
                  <div>最近自动交易：{formatDateTime(daemonStatus.lastTradingRun)}</div>
                  {daemonStatus.lastError ? <div className="text-[#B6453C]">最近错误：{daemonStatus.lastError}</div> : null}
                </div>
              </div>
            </div>
          </GlassCard>
        </TabsContent>

        <TabsContent value="data">
          <GlassCard className="space-y-6">
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-2">
                服务器统一数据源
                <HelpTooltip content="数据源优先级与 API Key 只从服务器环境变量读取，所有账户共享同一套配置，前端不再允许用户覆盖。" />
              </CardTitle>
              <CardDescription>当前项目统一使用服务器端 `.env` 中配置好的数据源与密钥。</CardDescription>
            </div>

            <div className="space-y-3">
              {dataSources.map((source, index) => (
                <div key={source} className="flex items-center justify-between rounded-2xl border border-black/[0.06] bg-black/[0.02] px-4 py-3">
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
              <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-4">
                <div className="text-sm font-medium text-foreground/85">配置模式</div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {configurationMode === "env_locked" ? "环境变量锁定模式" : "未知模式"}
                </div>
                <p className="mt-2 text-xs leading-6 text-muted-foreground">
                  如需变更优先级或密钥，请修改服务器端 `.env` 并重启后端服务。
                </p>
              </div>
              <div className="rounded-2xl border border-black/[0.06] bg-black/[0.02] p-4">
                <div className="text-sm font-medium text-foreground/85">密钥状态</div>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span>Tushare Token</span>
                    <span className={apiKeyStatus.Tushare ? "text-[#4D7358]" : "text-[#B6453C]"}>
                      {apiKeyStatus.Tushare ? "已配置" : "未配置"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Alpha Vantage Key</span>
                    <span className={apiKeyStatus.AlphaVantage ? "text-[#4D7358]" : "text-[#B6453C]"}>
                      {apiKeyStatus.AlphaVantage ? "已配置" : "未配置"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </GlassCard>
        </TabsContent>
      </Tabs>
    </div>
  )
}
