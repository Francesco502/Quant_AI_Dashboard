"use client"

import { useCallback, useEffect, useState } from "react"
import { KeyRound, RefreshCw, Server, ShieldCheck, Wallet } from "lucide-react"

import { StatusNotice } from "@/components/data/status-notice"
import { Button } from "@/components/ui/button"
import { GlassCard, CardDescription, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HelpTooltip } from "@/components/ui/tooltip"
import { api, getEffectiveApiBaseUrl, type AutoTradingStatusResponse } from "@/lib/api"
import { useSettings } from "@/lib/settings-context"
import { formatDateTimeInBeijing } from "@/lib/time"
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
  return formatDateTimeInBeijing(value, {}, "暂无")
}

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
        initialCapital: Number(autoStatus?.account?.initial_capital ?? autoStatus?.config?.initial_capital ?? 0),
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
        <h1 className="page-title">系统设置</h1>
        <p className="page-subtitle">管理模拟账户、后台任务与统一数据源配置，保持整套研究环境稳定可用。</p>
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

        <TabsContent value="daemon">
          <GlassCard className="space-y-6">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <CardTitle className="flex items-center gap-2">
                  运行状态
                  <HelpTooltip content="聚合显示 API 可达性、发布安全状态，以及后台守护进程的最近执行信息。" />
                </CardTitle>
                <CardDescription>这里是发布前最该先看的页面，健康检查、权限保护和守护进程状态都会集中呈现。</CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void checkHealth()
                  void loadDaemonStatus()
                }}
                disabled={healthLoading}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                {healthLoading ? "检测中…" : "刷新状态"}
              </Button>
            </div>

            <div className="space-y-4">
              <div className={`flex items-center justify-between rounded-2xl border p-4 ${healthStatus.online ? "surface-tone-celadon" : "surface-tone-cinnabar"}`}>
                <div className="flex items-center gap-3">
                  <div className={`h-2.5 w-2.5 rounded-full ${healthStatus.online ? "bg-[rgb(var(--rgb-celadon))]" : "bg-[rgb(var(--rgb-cinnabar))]"}`} />
                  <span className="font-medium">API 服务</span>
                </div>
                <span className="text-sm">
                  {healthLoading ? "检测中…" : healthStatus.online ? `运行中（${healthStatus.latencyMs}ms）` : "离线"}
                </span>
              </div>

              <div className={`flex items-center justify-between rounded-2xl border p-4 ${healthStatus.securityReady ? "surface-tone-celadon" : "surface-tone-cinnabar"}`}>
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-4 w-4" />
                  <span className="font-medium">发布安全</span>
                </div>
                <span className="text-sm">{healthStatus.securityReady ? "已就绪" : "未就绪"}</span>
              </div>

              {healthStatus.securityIssues.length > 0 ? (
                <StatusNotice tone="error" compact title="安全问题">
                  {healthStatus.securityIssues.join("；")}
                </StatusNotice>
              ) : null}

              {healthStatus.errorHint ? (
                <StatusNotice tone="error" compact title="健康检查失败">
                  {healthStatus.errorHint}
                </StatusNotice>
              ) : null}

              <div className="data-note text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-foreground/85">守护进程</span>
                  <span>{daemonStatus.running ? "运行中" : daemonStatus.enabled ? "待调度" : "未启用"}</span>
                </div>
                <div className="mt-3 space-y-1">
                  <div>最近启动：{formatDateTime(daemonStatus.lastStartedAt)}</div>
                  <div>最近自动交易：{formatDateTime(daemonStatus.lastTradingRun)}</div>
                  {daemonStatus.lastError ? <div className="text-tone-cinnabar">最近错误：{daemonStatus.lastError}</div> : null}
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
    </div>
  )
}
